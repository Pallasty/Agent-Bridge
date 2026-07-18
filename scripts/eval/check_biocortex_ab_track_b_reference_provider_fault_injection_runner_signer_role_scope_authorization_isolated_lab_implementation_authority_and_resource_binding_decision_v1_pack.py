#!/usr/bin/env python3
"""Independent checker for the T06 signer role/scope authority decision pack.

The source reviewer is deliberately treated as the subject under review.  This
checker owns its filesystem decoder, frozen byte anchors, domain hashes,
semantic assertions, receipt reconstruction, source-AST policy, predecessor
grounding, and mutation suite.  It never imports expected constants from the
subject module.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[2]
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024

SOURCE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_signer_role_scope_authorization_isolated_lab_implementation_"
    "authority_and_resource_binding_decision_v1.py"
)
CHECKER_REL = (
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_signer_role_scope_authorization_isolated_lab_"
    "implementation_authority_and_resource_binding_decision_v1_pack.py"
)
DECISION_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_signer_role_scope_authorization_isolated_lab_"
    "implementation_authority_and_resource_binding_decision_v1_pack_owner_"
    "decision_v0.json"
)
EXPECTED_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_signer_role_scope_authorization_isolated_lab_"
    "implementation_authority_and_resource_binding_decision_v1_pack.expected."
    "v0.tsv"
)
MANIFEST_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_signer_role_scope_authorization_isolated_lab_"
    "implementation_authority_and_resource_binding_decision_v1_pack_v0.json"
)
REPORT_REL = (
    "docs/reports/goal-c-u/2026-07-18-biocortex-track-b-reference-provider-"
    "fault-injection-runner-signer-role-scope-authorization-isolated-lab-"
    "implementation-authority-and-resource-binding-decision-v1-pack.md"
)
GATE_REL = (
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-signer-role-scope-authorization-isolated-lab-implementation-"
    "authority-and-resource-binding-decision-v1-pack.sh"
)

SOURCE_RAW_SHA256 = (
    "3cd07ed34e3aa9a9b6933ccba69a2da1f20c302c5e7f510f13e539b326f16db5"
)
DECISION_RAW_SHA256 = (
    "ba9bf671ec4985c14089e6e68b0bda5a09c0b4b09df1582ba6b8305f5fee4ee6"
)
EXPECTED_RAW_SHA256 = (
    "6da905a6d05660647ba92b9acf1d494fa277f66bc31b6d0afa07faef9e9e7d45"
)
DECISION_CANONICAL_SHA256 = (
    "d2340df61901a57390df43d833b9e2ec66a88f34c17c7e065b320517bb0ab699"
)
DECISION_DOMAIN_SHA256 = (
    "397fea33b75e1e24b9e4394e8a8d37d48d65c4b44836aa8dfea93ec50378cd4c"
)
RECEIPT_CONTENT_SHA256 = (
    "ebe31214b4a9028916fb4bb851a990250948fb2fd1ec3113574a02c14abadfa4"
)

RECORD_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_signer_role_scope_authorization_isolated_lab_implementation_"
    "authority_and_resource_binding_decision.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_signer_role_scope_authorization_isolated_lab_implementation_"
    "authority_and_resource_binding_decision_v1.receipt.v0"
)
MANIFEST_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_signer_role_scope_authorization_isolated_lab_implementation_"
    "authority_and_resource_binding_decision_v1_pack_manifest.v0"
)
DATE = "2026-07-18"
STATUS = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_"
    "AND_RESOURCE_SCOPE_RECORDED_ZERO_EXTERNAL_SPEND_NO_RUNTIME_OR_PROVIDER_"
    "AUTHORITY"
)
DECISION = (
    "AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_SIGNER_ROLE_SCOPE_AUTHORIZATION_"
    "ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED"
)
MODE = "ISOLATED_LAB_FIRST"
CURRENT_STATE = (
    "AUTHORIZED_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_EXACT_UNIT"
)
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "SIGNER_ROLE_SCOPE_AUTHORIZATION_SYNTHETIC_EXACT_OWNER_CLASS_EVIDENCE_"
    "CLASS_TRACK_SUBJECT_AUDIENCE_AND_NONCE_POLICY_VERIFIER_ISOLATED_LAB_"
    "IMPLEMENTATION"
)

PREDECESSOR_MANIFEST_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_"
    "exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_"
    "pack_v0.json"
)
PREDECESSOR_GATE_REL = (
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-bootstrap-trust-authentication-synthetic-trust-chain-exact-key-"
    "version-declared-role-and-revocation-verifier-isolated-lab-v1-pack.sh"
)
PREDECESSOR_EXPECTED_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_"
    "exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_"
    "pack.expected.v0.tsv"
)
T06_SPEC_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_runtime_prerequisite_evidence_packet_offline_"
    "integration_and_production_evidence_ingestion_boundary_review_v1_pack_"
    "synthetic_v0.json"
)

PREDECESSOR_RAW_SHA256 = {
    (
        "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-"
        "injection-runner-bootstrap-trust-authentication-isolated-lab-v1."
        "schema.json"
    ): "d078513da9cabad07fb000485fdcb663ede13993341917d56792a8a1c909901c",
    (
        "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-"
        "provider-fault-injection-runner-bootstrap-trust-authentication-"
        "synthetic-trust-chain-exact-key-version-declared-role-and-"
        "revocation-verifier-isolated-lab-v1-pack.md"
    ): "9da0b11bfc86011ca792a6c0b2836c53c55837c17ac680296f5ad595b1a32ef0",
    PREDECESSOR_GATE_REL: (
        "aaa66cd7b2045571a766839aea8e2f269bbaab9c15ba7607da0d57fe253fb061"
    ),
    (
        "scripts/eval/biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_bootstrap_trust_authentication_synthetic_trust_"
        "chain_exact_key_version_declared_role_and_revocation_verifier_"
        "isolated_lab_v1.py"
    ): "f483200c34ab570b3da8f45d6e4d0adb8e382f5d6fa815112a2c0b62c0431341",
    (
        "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_bootstrap_trust_authentication_synthetic_trust_"
        "chain_exact_key_version_declared_role_and_revocation_verifier_"
        "isolated_lab_v1_pack.py"
    ): "bcfe18cb20733392fb4f494e9783ca99d90afc52429024f2f88cfd2163d29e20",
    PREDECESSOR_EXPECTED_REL: (
        "0085ddde9579cfaa0050cd71c07bc26fd0dc34d2c144400ad16535dd480aaa36"
    ),
    (
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_bootstrap_trust_authentication_synthetic_trust_"
        "chain_exact_key_version_declared_role_and_revocation_verifier_"
        "isolated_lab_v1_pack_synthetic_v0.json"
    ): "31959b02f20278d126be3a7e18e44e220b47cffb41804f69e3ace5c93277923e",
    PREDECESSOR_MANIFEST_REL: (
        "bd0cca68c7edf8d992a7ec27cb4c700cd97cf61c4a2557ad56aca5f996a6744b"
    ),
}
T06_SPEC_RAW_SHA256 = (
    "3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6"
)
PREDECESSOR_RECEIPT_CONTENT_SHA256 = (
    "899a27ce565d0a8159334513edba2c166b6b6d56f8b74587a6d5e89be6408715"
)

DOMAIN_PREFIXES = {
    "authorized_component_contract": (
        "AB_TRACK_B_SIGNER_ROLE_SCOPE_AUTHORIZATION_COMPONENT_CONTRACT_V1"
    ),
    "boundary": "AB_TRACK_B_SIGNER_ROLE_SCOPE_AUTHORIZATION_BOUNDARY_V1",
    "decision_provenance": (
        "AB_TRACK_B_SIGNER_ROLE_SCOPE_AUTHORIZATION_DECISION_PROVENANCE_V1"
    ),
    "decision_record": (
        "AB_TRACK_B_SIGNER_ROLE_SCOPE_AUTHORIZATION_DECISION_RECORD_V1"
    ),
    "implementation_authority": (
        "AB_TRACK_B_SIGNER_ROLE_SCOPE_IMPLEMENTATION_AUTHORITY_SCOPE_V1"
    ),
    "nonclaims": "AB_TRACK_B_SIGNER_ROLE_SCOPE_AUTHORIZATION_NONCLAIMS_V1",
    "owner_implementation_actor": (
        "AB_TRACK_B_SIGNER_ROLE_SCOPE_OWNER_IMPLEMENTATION_ACTOR_V1"
    ),
    "receipt": "AB_TRACK_B_SIGNER_ROLE_SCOPE_AUTHORIZATION_DECISION_RECEIPT_V1",
    "resource_binding": (
        "AB_TRACK_B_SIGNER_ROLE_SCOPE_ISOLATED_LAB_RESOURCE_BINDING_V1"
    ),
    "rollback": "AB_TRACK_B_SIGNER_ROLE_SCOPE_AUTHORIZATION_ROLLBACK_V1",
    "state_machine": (
        "AB_TRACK_B_SIGNER_ROLE_SCOPE_AUTHORIZATION_STATE_MACHINE_V1"
    ),
}
HASHED_SECTIONS = (
    "authorized_component_contract",
    "boundary",
    "decision_provenance",
    "implementation_authority",
    "nonclaims",
    "owner_implementation_actor",
    "resource_binding",
    "rollback",
    "state_machine",
)
FROZEN_SECTION_HASHES = {
    "authorized_component_contract_sha256": (
        "bebce75276859b58b82e34dc4b3ad60e07c377a05a2829fa03424ea4b2779a94"
    ),
    "boundary_sha256": (
        "515d338ebe0a8f2af683b7aaef2805b12d6bb834edb8d0abe1db5afe13ac07f7"
    ),
    "decision_provenance_sha256": (
        "2d84fb0d264ba4858dccfd2218da8837e346ec83a9928a3b24c1d253879fe196"
    ),
    "implementation_authority_sha256": (
        "bec28e3ce48ff1f5535cf121fa07cc63ba66323081832146b1268fb683d47494"
    ),
    "nonclaims_sha256": (
        "8fa50b57a241b47be8a291f64568d3ecf353a56c008c5ad5861d67b434426124"
    ),
    "owner_implementation_actor_sha256": (
        "a6d5661f0abc41fd98dc43a1629e167d0e3d26e9725ea8ccfc83dd40511a612f"
    ),
    "resource_binding_sha256": (
        "61390d880dcd1104d056f607e02937d351d7d2cac29e0249d928ea5941f91fc1"
    ),
    "rollback_sha256": (
        "4fcdb2515eb7369d5629f947f263ec33f2b1625a03b7cce36bdb721952da1da1"
    ),
    "state_machine_sha256": (
        "8127fc90991f7e70c2624ee0acb8a105538c883177fcdce32f34306b6eadcace"
    ),
}

SCOPE_FIELDS = (
    "owner_class",
    "evidence_class",
    "track_id",
    "subject",
    "audience",
    "nonce_scope",
)
FORBIDDEN_REQUEST_SIGNER_FIELDS = (
    "declared_role_class",
    "predecessor_receipt_content_sha256",
    "signer_key_id",
    "signer_key_version",
    "signer_role",
)
EXPECTED_TRACKS = ("MANAGED_SPANNER_CLOUD_KMS", "SELF_HOSTED_ETCD_OPENBAO")
COMMON_OWNER_CLASS = "SYNTHETIC_KAT_EVIDENCE_REVIEW_OWNER_CLASS_V1"
COMMON_EVIDENCE_CLASS = "SYNTHETIC_PRODUCTION_EVIDENCE_ENVELOPE_KAT"

ALLOWED_OPERATIONS = (
    "ADD_CLOSED_WORLD_SYNTHETIC_SIGNER_AUTHORIZATION_POLICY_REQUEST_AND_RECEIPT_SCHEMAS",
    "ADD_EXACT_TWO_PROFILE_DEFAULT_DENY_AUTHORIZATION_REGISTRY_KATS",
    "ADD_PURE_SIGNER_ROLE_SCOPE_REFERENCE_VERIFIER_FOR_FIXED_PUBLIC_ONLY_KATS",
    "COMPOSE_EXACTLY_ONCE_WITH_FROZEN_T05_PREDECESSOR_PUBLIC_REVIEW_API",
    "BIND_T05_SIGNER_TUPLE_AND_RECEIPT_TO_EXACT_SIX_DIMENSION_SYNTHETIC_SCOPE",
    "ADD_PREOBSERVATION_SYNTHETIC_PRODUCTION_MODE_GUARDS",
    "ADD_DETERMINISTIC_NONSECRET_PUBLIC_ONLY_ADVERSARIAL_KATS",
    "ADD_PURE_REVIEWER_INDEPENDENT_CONTRACT_AND_SECURITY_GATE_LANES_REPORT_AND_SOURCE_BOUND_GATE",
)
FORBIDDEN_OPERATIONS = (
    "ACCESS_CREDENTIAL_OR_SECRET_MATERIAL",
    "ACCEPT_CALLER_SUPPLIED_PREDECESSOR_RECEIPT",
    "ACCEPT_OR_PERSIST_REAL_EVIDENCE",
    "ADD_ACTION_OR_RESOURCE_CAPABILITY_AUTHORIZATION",
    "ADD_CRYPTOGRAPHIC_SIGNING_KEY_GENERATION_OR_PRIVATE_SEED_API",
    "ADD_OR_FETCH_UNPINNED_CRYPTOGRAPHIC_DEPENDENCY",
    "ALLOW_AMBIGUOUS_OR_MULTIPLE_MATCHING_GRANTS",
    "ALLOW_DEFAULT_ALLOW_EXPLICIT_DENY_WILDCARD_PREFIX_OR_HIERARCHICAL_MATCH",
    "ALLOW_GROUP_ROLE_OR_PARENT_SCOPE_INHERITANCE",
    "AUTHORIZE_OR_INJECT_FAULT",
    "AUTHORIZE_OUTPUT_OR_CLAIM",
    "BIND_PRODUCTION_OWNER_EVIDENCE_TRACK_SUBJECT_AUDIENCE_OR_NONCE",
    "BIND_PROVIDER_OR_PRODUCTION_ENDPOINT",
    "CALL_PROVIDER_OR_ATTEMPT_WIRE",
    "CLAIM_NONCE_FRESHNESS_SINGLE_USE_OR_REPLAY_PROTECTION",
    "CLAIM_PRODUCTION_SIGNER_AUTHORIZATION_OR_MITIGATION",
    "CLAIM_SCOPE_LABEL_AS_OWNER_SUBJECT_PROVIDER_OR_AUDIENCE_TRUTH",
    "COMMIT_PRIVATE_KEY_TEST_SEED_OR_SECRET_SHAPED_MATERIAL",
    "CREATE_RUNTIME_OR_EXPERIMENT_ROW",
    "DEPLOY_OR_ENABLE_PRODUCTION_INGESTION",
    "DERIVE_AUTHORIZATION_POLICY_FROM_FRAME_BUNDLE_OR_REQUEST",
    "ESTABLISH_DURABLE_CUSTODY_OR_REPLAY_LEDGER",
    "IMPLEMENT_T07_TRACK_PROFILE_OR_T08_END_TO_END_SUBJECT_BINDING",
    "LAUNCH_RUNNER_OR_BACKGROUND_DAEMON",
    "PERSIST_AUTHORIZATION_POLICY_REQUEST_OR_RESULT",
    "PROVISION_PAID_OR_EXTERNAL_RESOURCE",
    "READ_AMBIENT_DEFAULT_OR_SYSTEM_TRUST_OR_CREDENTIAL_CHAIN",
    "REGISTER_OR_IMPORT_INTO_PRODUCTION_RUNTIME",
    "REPRESENT_RUNTIME_OWNER_DECISION",
    "SATISFY_RUNTIME_PREREQUISITE",
    "USE_AMBIENT_OR_PRODUCTION_TRUSTED_TIME",
)

COMPONENT_LIMITS = {
    "max_array_items": 64,
    "max_authorization_grants": 2,
    "max_authorization_policy_bytes": 65536,
    "max_authorization_request_bytes": 16384,
    "max_authentication_bundle_bytes": 65536,
    "max_input_frame_bytes": 1048576,
    "max_json_depth": 32,
    "max_json_nodes": 4096,
    "max_object_members": 256,
    "max_parallel_workers": 1,
    "max_predecessor_review_calls": 1,
    "max_private_scratch_bytes": 67108864,
    "max_scope_string_utf8_bytes": 256,
    "max_trust_policy_bytes": 65536,
    "public_input_count": 6,
}

TSV_FIELDS = tuple(
    """schema status decision date mode next_unit current_state
authorization_effective_only_after_integrated_full_gate
implementation_authority_recorded implementation_scope_decision_recorded
implementation_resource_binding_recorded
implementation_authority_single_use_consumed
predecessor_authorization_consumption_state
predecessor_implementation_authority_single_use_consumed
authorized_candidate_surface_component_count
authorized_local_threat_specification_count
authorized_local_threat_specifications authorization_profile_count
default_effect wildcards_allowed request_scope_dimension_count
public_input_count bootstrap_trust_authentication_implemented
signer_role_scope_authorization_implemented track_subject_binding_implemented
local_t06_specification_exercised local_t07_specification_exercised
future_successor_candidate_surface_component_total
future_successor_candidate_surface_components_authorized
current_decision_candidate_surface_components_implemented
isolated_lab_predecessor_surface_components_implemented
local_predecessor_threat_specifications_covered
future_successor_minimum_independent_reviewer_lane_count
production_security_reviewer_bound owner_semantic_actor_label
owner_semantic_actor_binding_recorded owner_cryptographic_identity_verified
owner_signature_observed owner_supplied_numeric_budget_cap
external_paid_spend_cap allowed_operation_count forbidden_operation_count
provider_endpoint_count component_runtime_network global_single_use_proved
nonce_freshness_proved nonce_replay_protection_proved
production_environment_implementation_authorized
production_ingestion_implemented production_ingestion_enabled
production_ingestion_controls_implemented
production_ingestion_controls_runtime_exercised real_evidence_items_present
production_validated_evidence_items runtime_evidence_accepted
runtime_prerequisites_satisfied runtime_owner_identity_bound
runtime_owner_decision_recorded runtime_admission_ready
runtime_admission_granted runtime_authority provider_authority
downstream_gates_authorized runtime_side_effects_unlocked
implementation_side_effects_unlocked nonclaim_field_count
all_nonclaims_explicit authorized_component_contract_sha256
implementation_authority_sha256 resource_binding_sha256
state_machine_sha256 rollback_sha256 boundary_sha256 nonclaims_sha256
decision_record_sha256 predecessor_integration_commit
predecessor_receipt_content_sha256 t06_semantic_specification_raw_sha256
content_sha256""".split()
)
INTEGER_RECEIPT_FIELDS = {
    "authorized_candidate_surface_component_count",
    "authorized_local_threat_specification_count",
    "authorization_profile_count",
    "request_scope_dimension_count",
    "public_input_count",
    "future_successor_candidate_surface_component_total",
    "future_successor_candidate_surface_components_authorized",
    "current_decision_candidate_surface_components_implemented",
    "isolated_lab_predecessor_surface_components_implemented",
    "local_predecessor_threat_specifications_covered",
    "future_successor_minimum_independent_reviewer_lane_count",
    "external_paid_spend_cap",
    "allowed_operation_count",
    "forbidden_operation_count",
    "provider_endpoint_count",
    "production_ingestion_controls_implemented",
    "production_ingestion_controls_runtime_exercised",
    "real_evidence_items_present",
    "production_validated_evidence_items",
    "runtime_evidence_accepted",
    "runtime_prerequisites_satisfied",
    "downstream_gates_authorized",
    "nonclaim_field_count",
}

PACK_PATHS = (
    SOURCE_REL,
    CHECKER_REL,
    DECISION_REL,
    EXPECTED_REL,
    MANIFEST_REL,
    REPORT_REL,
    GATE_REL,
)
PACK_MODES = {
    SOURCE_REL: "100644",
    CHECKER_REL: "100644",
    DECISION_REL: "100644",
    EXPECTED_REL: "100644",
    MANIFEST_REL: "100644",
    REPORT_REL: "100644",
    GATE_REL: "100755",
}


class CheckError(ValueError):
    """Fail-closed checker error."""


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise CheckError(f"{code}: {message}")


def exact_keys(value: Any, expected: Iterable[str], code: str) -> None:
    require(type(value) is dict, code, "not an object")
    require(set(value) == set(expected), code, "closed-world key set drift")


def exact_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(
            exact_equal(left[key], right[key]) for key in left
        )
    if type(left) is list:
        return len(left) == len(right) and all(
            exact_equal(a, b) for a, b in zip(left, right)
        )
    return bool(left == right)


def validate_json_value(value: Any, depth: int = 0) -> None:
    require(depth <= 64, "E_JSON_DEPTH", "nesting exceeds 64")
    require(type(value) is not float, "E_JSON_FLOAT", "floats forbidden")
    if type(value) is int:
        require(-(2**63) <= value <= 2**63 - 1, "E_JSON_INT", "out of range")
        return
    if type(value) in (str, bool) or value is None:
        return
    if type(value) is list:
        for item in value:
            validate_json_value(item, depth + 1)
        return
    require(type(value) is dict, "E_JSON_TYPE", type(value).__name__)
    for key, item in value.items():
        require(type(key) is str, "E_JSON_KEY", "non-string key")
        validate_json_value(item, depth + 1)


def canonical_bytes(value: Any) -> bytes:
    validate_json_value(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def domain_sha256(domain: str, value: Any) -> str:
    require(type(domain) is str and domain.isascii(), "E_DOMAIN", domain)
    return hashlib.sha256(
        domain.encode("ascii") + b"\0" + canonical_bytes(value)
    ).hexdigest()


def checked_path(relative: str) -> Path:
    require(
        type(relative) is str
        and relative
        and not relative.startswith("/")
        and "\\" not in relative,
        "E_PATH",
        str(relative),
    )
    parts = relative.split("/")
    require(
        all(part not in ("", ".", "..") for part in parts),
        "E_PATH",
        relative,
    )
    path = ROOT.joinpath(*parts)
    root_resolved = ROOT.resolve()
    require(
        path.resolve().is_relative_to(root_resolved), "E_PATH_ESCAPE", relative
    )
    metadata = path.lstat()
    require(stat.S_ISREG(metadata.st_mode), "E_PATH_TYPE", relative)
    require(not path.is_symlink(), "E_PATH_SYMLINK", relative)
    require(metadata.st_size <= MAX_ARTIFACT_BYTES, "E_PATH_SIZE", relative)
    return path


def read_bytes(relative: str) -> bytes:
    return checked_path(relative).read_bytes()


def read_text(relative: str) -> str:
    raw = read_bytes(relative)
    require(not raw.startswith(b"\xef\xbb\xbf"), "E_BOM", relative)
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise CheckError(f"E_UTF8: {relative}") from error


def raw_sha256(relative: str) -> str:
    return hashlib.sha256(read_bytes(relative)).hexdigest()


def duplicate_safe_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(key not in value, "E_JSON_DUPLICATE", key)
        value[key] = item
    return value


def bounded_integer(token: str) -> int:
    value = int(token, 10)
    require(-(2**63) <= value <= 2**63 - 1, "E_JSON_INT", token)
    return value


def reject_float(token: str) -> float:
    raise CheckError(f"E_JSON_FLOAT: {token}")


def reject_constant(token: str) -> None:
    raise CheckError(f"E_JSON_CONSTANT: {token}")


def parse_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    require(len(raw) <= MAX_ARTIFACT_BYTES, "E_JSON_SIZE", label)
    require(not raw.startswith(b"\xef\xbb\xbf"), "E_JSON_BOM", label)
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=duplicate_safe_object,
            parse_int=bounded_integer,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except UnicodeDecodeError as error:
        raise CheckError(f"E_UTF8: {label}") from error
    require(type(value) is dict, "E_JSON_ROOT", label)
    validate_json_value(value)
    return value


def read_json(relative: str) -> dict[str, Any]:
    return parse_json_bytes(read_bytes(relative), relative)


def expected_section_hashes(record: Mapping[str, Any]) -> dict[str, str]:
    return {
        f"{section}_sha256": domain_sha256(DOMAIN_PREFIXES[section], record[section])
        for section in HASHED_SECTIONS
    }


def validate_exact_tree(actual: Any, expected: Any, path: str = "record") -> None:
    require(type(actual) is type(expected), "E_FROZEN_TYPE", path)
    if type(expected) is dict:
        exact_keys(actual, expected, "E_FROZEN_KEYS")
        for key in sorted(expected):
            validate_exact_tree(actual[key], expected[key], f"{path}.{key}")
        return
    if type(expected) is list:
        require(len(actual) == len(expected), "E_FROZEN_LENGTH", path)
        for index, item in enumerate(expected):
            validate_exact_tree(actual[index], item, f"{path}[{index}]")
        return
    require(actual == expected, "E_FROZEN_VALUE", path)


def verify_frozen_inputs() -> None:
    require(raw_sha256(SOURCE_REL) == SOURCE_RAW_SHA256, "E_SOURCE_RAW", SOURCE_REL)
    require(
        raw_sha256(DECISION_REL) == DECISION_RAW_SHA256,
        "E_DECISION_RAW",
        DECISION_REL,
    )
    require(
        raw_sha256(EXPECTED_REL) == EXPECTED_RAW_SHA256,
        "E_EXPECTED_RAW",
        EXPECTED_REL,
    )


def verify_predecessor_artifacts(record: Mapping[str, Any]) -> None:
    require(len(PREDECESSOR_RAW_SHA256) == 8, "E_T05_COUNT", "eight artifacts")
    for relative, expected_hash in PREDECESSOR_RAW_SHA256.items():
        require(raw_sha256(relative) == expected_hash, "E_T05_RAW", relative)
    predecessor = record["predecessor"]
    require(
        exact_equal(predecessor["artifact_raw_sha256"], PREDECESSOR_RAW_SHA256),
        "E_T05_BINDING",
        "artifact map",
    )
    require(
        predecessor["integration_commit"]
        == "7df72e2d49bbc25580d4dcb63bc1a183120bba77"
        and predecessor["integration_tree"]
        == "7fc4786b814d81d97e8672bcae484c07e180f04a"
        and predecessor["integration_parents"]
        == [
            "2707996e0616885fa51da9b908764f017a67299f",
            "2a26de5b99886922240350fadefa07bc8f4c5dcd",
        ]
        and predecessor["source_commit"]
        == "2a26de5b99886922240350fadefa07bc8f4c5dcd"
        and predecessor["source_tree"]
        == "596c6b7d8bdf18b844c6e24a664213fc23fd9772"
        and predecessor["source_parent"]
        == "61585e655f7bfd537f8a123141e4e39a590a66d8",
        "E_T05_TOPOLOGY",
        "integration/source lineage",
    )
    require(
        predecessor["authorization_consumption_state"] == "CONSUMED_SCOPE_COMPLETE"
        and predecessor["implementation_authority_single_use_consumed"] is True
        and predecessor["bootstrap_trust_authentication_implemented"] is True
        and predecessor["local_t05_specification_exercised"] is True
        and predecessor["local_t06_specification_exercised"] is False
        and predecessor["signer_role_scope_authorization_implemented"] is False
        and predecessor["fast_stdout_line_count"] == 95
        and predecessor["fast_stdout_sha256"]
        == "3881e2fbeacfa584098233cae7f7b8cbb56e4f5abb6d7dfb7c75fc59420b7f1b"
        and predecessor["full_stdout_line_count"] == 96
        and predecessor["full_stdout_sha256"]
        == "baf76dca1f7ff58da7c352665b88ef39503a5765d102f885d29777a3c7d1e0ed",
        "E_T05_STATE",
        "consumption/gate result",
    )
    receipt_lines = read_text(PREDECESSOR_EXPECTED_REL).splitlines()
    require(len(receipt_lines) == 44, "E_T05_RECEIPT_LINES", str(len(receipt_lines)))
    require(
        receipt_lines[-1]
        == "content_sha256\t" + PREDECESSOR_RECEIPT_CONTENT_SHA256,
        "E_T05_RECEIPT_CONTENT",
        "receipt binding",
    )
    predecessor_manifest = read_json(PREDECESSOR_MANIFEST_REL)
    require(
        predecessor_manifest["next_unit"]
        == (
            "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_"
            "V1_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_IMPLEMENTATION_"
            "AUTHORITY_AND_RESOURCE_BINDING_DECISION"
        )
        and predecessor_manifest["next_unit_authorized_by_this_pack"] is False
        and predecessor_manifest["state"][
            "implementation_authority_consumed_only_by_exact_integrated_full_gate"
        ]
        is True
        and predecessor_manifest["state"][
            "implementation_authority_single_use_consumed_before_integrated_full_gate"
        ]
        is False
        and predecessor_manifest["state"]["source_fast_consumes_implementation_authority"]
        is False
        and predecessor_manifest["state"]["integrated_fast_consumes_implementation_authority"]
        is False
        and predecessor_manifest["boundary"]["local_t05_specification_exercised"]
        is True
        and predecessor_manifest["boundary"]["local_t06_specification_exercised"]
        is False
        and predecessor_manifest["boundary"]["local_t07_specification_exercised"]
        is False,
        "E_T05_MANIFEST",
        "successor/consumption boundary",
    )


def verify_t06_specification(record: Mapping[str, Any]) -> None:
    require(raw_sha256(T06_SPEC_REL) == T06_SPEC_RAW_SHA256, "E_T06_RAW", T06_SPEC_REL)
    require(
        record["predecessor"]["t06_semantic_specification_path"] == T06_SPEC_REL
        and record["predecessor"]["t06_semantic_specification_raw_sha256"]
        == T06_SPEC_RAW_SHA256,
        "E_T06_BINDING",
        "record path/hash",
    )
    specification = read_json(T06_SPEC_REL)
    controls = [
        row
        for row in specification["production_ingestion_controls"]
        if row.get("control_id") == "SIGNER_ROLE_SCOPE_AUTHORIZATION"
    ]
    threats = [
        row for row in specification["threat_cases"] if row.get("case_id") == "T06"
    ]
    require(len(controls) == 1 and len(threats) == 1, "E_T06_ROWS", "exact rows")
    control = controls[0]
    threat = threats[0]
    require(
        control["mandatory_check"]
        == (
            "Authorize signer identity to the exact owner class, evidence class, "
            "track, subject, audience, and nonce scope."
        )
        and control["primary_failure_code"]
        == "E_PRODUCTION_SIGNER_AUTHORIZATION_FAILED"
        and control["implemented"] is False
        and control["runtime_exercised"] is False
        and control["satisfiable_by_offline"] is False
        and threat["expected_disposition"] == "REJECTED_FAIL_CLOSED"
        and threat["expected_reason_code"]
        == "E_PRODUCTION_SIGNER_AUTHORIZATION_FAILED"
        and threat["threat_class"] == "AUTHORIZATION",
        "E_T06_SEMANTICS",
        "six-dimensional production boundary",
    )


def validate_semantics(record: Mapping[str, Any]) -> None:
    exact_keys(
        record,
        {
            "authorized_component_contract",
            "boundary",
            "date",
            "decision",
            "decision_provenance",
            "implementation_authority",
            "next_unit",
            "nonclaims",
            "owner_implementation_actor",
            "predecessor",
            "resource_binding",
            "rollback",
            "schema",
            "schema_version",
            "section_sha256",
            "state_machine",
            "status",
        },
        "E_RECORD_KEYS",
    )
    require(
        record["schema"] == RECORD_SCHEMA
        and record["schema_version"] == 1
        and type(record["schema_version"]) is int
        and record["date"] == DATE
        and record["status"] == STATUS
        and record["decision"] == DECISION
        and record["next_unit"] == NEXT_UNIT,
        "E_IDENTITY",
        "record identity",
    )
    hashes = expected_section_hashes(record)
    require(exact_equal(hashes, FROZEN_SECTION_HASHES), "E_SECTION_FROZEN", "hashes")
    require(exact_equal(record["section_sha256"], hashes), "E_SECTION_HASH", "hashes")
    require(
        hashlib.sha256(canonical_bytes(record)).hexdigest()
        == DECISION_CANONICAL_SHA256,
        "E_CANONICAL_HASH",
        "decision",
    )
    require(
        domain_sha256(DOMAIN_PREFIXES["decision_record"], record)
        == DECISION_DOMAIN_SHA256,
        "E_DOMAIN_HASH",
        "decision",
    )

    component = record["authorized_component_contract"]
    model = component["authorization_model"]
    require(
        model
        == {
            "allow_grant_count": 2,
            "default_effect": "DENY",
            "deny_on_multiple_matches": True,
            "deny_on_zero_matches": True,
            "explicit_deny_grants_allowed": False,
            "group_inheritance_allowed": False,
            "hierarchical_match_allowed": False,
            "matching_profile": "EXACT_ALL_FIELDS_ASCII_BYTE_EQUAL",
            "prefix_match_allowed": False,
            "role_inheritance_allowed": False,
            "wildcards_allowed": False,
        },
        "E_AUTHZ_MODEL",
        "closed-world default deny",
    )
    topology = component["input_topology"]
    require(
        topology["public_input_tuple"]
        == [
            "frame",
            "detached_authentication_bundle",
            "separately_injected_synthetic_trust_policy",
            "separately_injected_synthetic_signer_authorization_policy",
            "detached_authorization_request",
            "mode",
        ]
        and topology["review_order"]
        == [
            "MODE_PREOBSERVATION_GUARD",
            "T05_BOOTSTRAP_TRUST_AUTHENTICATION_REVIEW",
            "SEPARATE_SIGNER_AUTHORIZATION_POLICY_REVIEW",
            "DETACHED_AUTHORIZATION_REQUEST_REVIEW",
        ]
        and topology["signer_identity_source"] == "T05_PREDECESSOR_RECEIPT_ONLY"
        and topology["predecessor_reviewer_call_count_per_success"] == 1
        and topology["caller_supplied_predecessor_receipt_allowed"] is False
        and topology["production_and_unknown_mode_rejected_before_any_input_observation"]
        is True
        and topology["authorization_request_observed_after_policy"] is True
        and topology["authorization_policy_may_be_sourced_from_bundle"] is False
        and topology["authorization_policy_may_be_sourced_from_frame"] is False
        and topology["authorization_policy_may_be_sourced_from_request"] is False,
        "E_INPUT_TOPOLOGY",
        "six inputs and T05-first review",
    )
    policy = component["policy_profile"]
    require(
        policy["profile_count"] == 2
        and policy["profile_order"] == list(EXPECTED_TRACKS)
        and policy["request_scope_fields"] == list(SCOPE_FIELDS)
        and policy["request_signer_fields_forbidden"]
        == list(FORBIDDEN_REQUEST_SIGNER_FIELDS)
        and policy["scope_dimension_count"] == 6
        and policy["authorization_registry_is_production_policy"] is False,
        "E_POLICY_PROFILE",
        "exact six dimensions",
    )
    profiles = policy["authorization_profiles"]
    require(len(profiles) == 2, "E_PROFILE_COUNT", "two grants")
    require([row["track_id"] for row in profiles] == list(EXPECTED_TRACKS), "E_TRACKS", "order")
    for index, profile in enumerate(profiles):
        require(profile["effect"] == "ALLOW", "E_PROFILE_EFFECT", str(index))
        require(
            profile["owner_class"] == COMMON_OWNER_CLASS
            and profile["evidence_class"] == COMMON_EVIDENCE_CLASS,
            "E_PROFILE_COMMON_SCOPE",
            str(index),
        )
        for field in SCOPE_FIELDS:
            value = profile[field]
            require(
                type(value) is str
                and value
                and value.isascii()
                and len(value.encode("utf-8")) <= 256
                and "*" not in value,
                "E_SCOPE_VALUE",
                f"{index}:{field}",
            )
        require(
            profile["declared_role_class"]
            == "SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY"
            and profile["predecessor_receipt_content_sha256"]
            in {
                "46a923e510a29ed144d0de092b8346585a4a857e009d042bb68da1003f681803",
                "72d1e5c86fc99027427c78f1b2792d51e02461a6cc9b120f1d8baf877472e1c1",
            }
            and profile["trust_policy_sha256"]
            == "882f37d4862ed83bb8d91b218dec8c9b40861b35e3785620f873d9250f9d51b0",
            "E_T05_SIGNER_TUPLE",
            str(index),
        )
    track_specific = (
        "authorization_policy_revision",
        "audience",
        "frame_sha256",
        "grant_id",
        "nonce_scope",
        "predecessor_receipt_content_sha256",
        "revocation_snapshot_revision",
        "signer_key_id",
        "signer_key_version",
        "signer_role",
        "subject",
        "track_id",
        "vector_set_id",
    )
    require(
        {profiles[0][key] for key in track_specific}.isdisjoint(
            {profiles[1][key] for key in track_specific}
        ),
        "E_CROSS_TRACK_ALIAS",
        "track-specific tuple overlap",
    )
    require(
        component["nonce_boundary"]
        == {
            "fixed_public_kat_equality_only": True,
            "freshness_proved": False,
            "generation_authorized": False,
            "single_use_proved": False,
            "t09_durable_replay_cas_implemented": False,
        }
        and all(value is False for value in component["scope_truth_boundary"].values())
        and component["reviewer_topology"]["minimum_independent_reviewer_lane_count"]
        == 2
        and component["reviewer_topology"]["required_reviewer_lanes"]
        == [
            "CONTRACT_CONFORMANCE_REVIEW",
            "SECURITY_AND_SOURCE_BOUND_GATE_REVIEW",
        ]
        and component["reviewer_topology"]["lane_identity_distinctness_required"]
        is True,
        "E_TRUTH_REVIEW_BOUNDARY",
        "nonce/truth/reviewer closure",
    )

    authority = record["implementation_authority"]
    require(
        authority["allowed_operations"] == list(ALLOWED_OPERATIONS)
        and authority["forbidden_operations"] == list(FORBIDDEN_OPERATIONS)
        and authority["authorized_local_threat_specifications"] == ["T06"]
        and authority["current_state"] == CURRENT_STATE
        and authority["mode"] == MODE
        and authority["exact_next_unit_authorized"] is True
        and authority["default_off_required"] is True
        and authority["non_transitive"] is True
        and authority["subdelegation_authorized"] is False
        and authority["runtime_import_authorized"] is False
        and authority["runtime_registration_authorized"] is False
        and authority["production_environment_implementation_authorized"] is False,
        "E_AUTHORITY",
        "T06-only local authority",
    )
    resources = record["resource_binding"]
    require(
        resources["component_limits"] == COMPONENT_LIMITS
        and resources["component_runtime_network"] is False
        and resources["ambient_or_system_trust_store_allowed"] is False
        and resources["credential_handles"] == []
        and resources["credential_paths"] == []
        and resources["provider_endpoints"] == []
        and resources["effective_external_paid_spend_cap"] == 0
        and resources["private_key_or_seed_material_authorized"] is False
        and resources["signing_or_key_generation_authorized"] is False
        and resources["production_resource_authority_bound"] is False
        and resources["dependency_scope"]
        == "PYTHON_STANDARD_LIBRARY_REFERENCE_KAT_ONLY_NO_FETCH",
        "E_RESOURCES",
        "offline zero-spend limits",
    )
    state_machine = record["state_machine"]
    require(
        state_machine["current_state"] == CURRENT_STATE
        and len(state_machine["states"]) == 5
        and len(state_machine["transitions"]) == 4
        and state_machine["transitions"][2]["event"]
        == "EXACT_AUTHORIZED_T06_SUCCESSOR_INTEGRATED_AND_FULL_GATE_PASSES"
        and state_machine["decision_full_gate_consumes_new_authority"] is False
        and state_machine["global_single_use_proved"] is False
        and state_machine["runtime_authority_state_representable"] is False
        and state_machine["positive_provider_authority_state_representable"]
        is False,
        "E_STATE",
        "fail-closed lifecycle",
    )
    boundary = record["boundary"]
    require(
        boundary["authorized_future_local_threat_specifications"] == ["T06"]
        and boundary["bootstrap_trust_authentication_isolated_lab_implemented"]
        is True
        and boundary["signer_role_scope_authorization_isolated_lab_implemented"]
        is False
        and boundary["local_t06_specification_exercised"] is False
        and boundary["local_t07_specification_exercised"] is False
        and boundary["isolated_lab_predecessor_surface_components_implemented"]
        == 3
        and boundary["local_predecessor_threat_specifications_covered"] == 5
        and boundary["future_successor_candidate_surface_component_total"] == 4
        and boundary["future_successor_candidate_surface_components_authorized"]
        == 1
        and boundary["production_ingestion_control_count"] == 14
        and boundary["production_ingestion_controls_implemented"] == 0
        and boundary["production_threat_specification_count"] == 20
        and boundary["production_threat_specifications_runtime_exercised"] == 0
        and boundary["runtime_prerequisite_count"] == 16
        and boundary["runtime_prerequisites_satisfied"] == 0
        and boundary["runtime_authority"] is False
        and boundary["provider_authority"] is False
        and boundary["track_subject_binding_implemented"] is False,
        "E_BOUNDARY",
        "component/production accounting",
    )
    require(
        len(record["nonclaims"]) == 71
        and all(value is False for value in record["nonclaims"].values()),
        "E_NONCLAIMS",
        "71 explicit false claims",
    )
    provenance = record["decision_provenance"]
    actor = record["owner_implementation_actor"]
    require(
        provenance["directive_observed_in_owner_session"] is True
        and provenance["explicit_production_runtime_authority_observed"] is False
        and provenance["explicit_provider_authority_observed"] is False
        and provenance["owner_supplied_numeric_budget_cap"] is False
        and actor["semantic_actor_label"] == "pallasting"
        and actor["semantic_actor_role"] == "PROJECT_OWNER"
        and actor["semantic_actor_binding_recorded"] is True
        and actor["cryptographic_identity_verified"] is False
        and actor["signature_observed"] is False
        and actor["delegated_runtime_authority"] is False,
        "E_OWNER_BOUNDARY",
        "semantic owner only",
    )
    verify_predecessor_artifacts(record)
    verify_t06_specification(record)


def validate_record(record: dict[str, Any], expected: Mapping[str, Any]) -> None:
    validate_json_value(record)
    validate_exact_tree(record, expected)
    validate_semantics(record)


def parse_expected_receipt() -> dict[str, Any]:
    lines = read_text(EXPECTED_REL).splitlines()
    require(len(lines) == len(TSV_FIELDS) == 79, "E_TSV_LINES", str(len(lines)))
    receipt: dict[str, Any] = {}
    for index, line in enumerate(lines):
        parts = line.split("\t")
        require(len(parts) == 2, "E_TSV_COLUMNS", str(index))
        field, rendered = parts
        require(field == TSV_FIELDS[index] and field not in receipt, "E_TSV_FIELD", field)
        if field in INTEGER_RECEIPT_FIELDS:
            require(rendered == str(int(rendered, 10)), "E_TSV_INTEGER", field)
            value: Any = int(rendered, 10)
        elif rendered in ("true", "false"):
            value = rendered == "true"
        else:
            value = rendered
        receipt[field] = value
    return receipt


def render_tsv(receipt: Mapping[str, Any]) -> str:
    exact_keys(receipt, TSV_FIELDS, "E_RECEIPT_KEYS")
    lines: list[str] = []
    for field in TSV_FIELDS:
        value = receipt[field]
        require(type(value) in (str, int, bool), "E_RECEIPT_TYPE", field)
        rendered = "true" if value is True else "false" if value is False else str(value)
        require("\t" not in rendered and "\n" not in rendered, "E_TSV_INJECT", field)
        lines.append(f"{field}\t{rendered}")
    return "\n".join(lines) + "\n"


def validate_receipt(receipt: dict[str, Any], record: Mapping[str, Any]) -> str:
    expected = parse_expected_receipt()
    validate_exact_tree(receipt, expected, "receipt")
    require(receipt["schema"] == RECEIPT_SCHEMA, "E_RECEIPT_SCHEMA", "schema")
    require(
        receipt["decision_record_sha256"] == DECISION_DOMAIN_SHA256
        and receipt["content_sha256"] == RECEIPT_CONTENT_SHA256
        and receipt["authorized_component_contract_sha256"]
        == FROZEN_SECTION_HASHES["authorized_component_contract_sha256"]
        and receipt["implementation_authority_sha256"]
        == FROZEN_SECTION_HASHES["implementation_authority_sha256"]
        and receipt["resource_binding_sha256"]
        == FROZEN_SECTION_HASHES["resource_binding_sha256"]
        and receipt["state_machine_sha256"]
        == FROZEN_SECTION_HASHES["state_machine_sha256"]
        and receipt["rollback_sha256"]
        == FROZEN_SECTION_HASHES["rollback_sha256"]
        and receipt["boundary_sha256"]
        == FROZEN_SECTION_HASHES["boundary_sha256"]
        and receipt["nonclaims_sha256"]
        == FROZEN_SECTION_HASHES["nonclaims_sha256"]
        and receipt["allowed_operation_count"] == len(ALLOWED_OPERATIONS)
        and receipt["forbidden_operation_count"] == len(FORBIDDEN_OPERATIONS)
        and receipt["nonclaim_field_count"] == len(record["nonclaims"])
        and receipt["authorization_profile_count"] == 2
        and receipt["request_scope_dimension_count"] == 6
        and receipt["public_input_count"] == 6,
        "E_RECEIPT_BINDING",
        "derived bindings",
    )
    unsigned = dict(receipt)
    del unsigned["content_sha256"]
    require(
        domain_sha256(DOMAIN_PREFIXES["receipt"], unsigned)
        == RECEIPT_CONTENT_SHA256,
        "E_RECEIPT_CONTENT",
        "domain hash",
    )
    rendered = render_tsv(receipt)
    require(rendered == read_text(EXPECTED_REL), "E_RECEIPT_TSV", "exact bytes")
    return rendered


def load_source() -> ModuleType:
    path = checked_path(SOURCE_REL).resolve()
    name = "_signer_role_scope_authority_source_under_review"
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "E_IMPORT", name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    require(Path(module.__file__).resolve() == path, "E_IMPORT_PATH", name)
    return module


def check_source_ast_text(text: str) -> None:
    tree = ast.parse(text, filename=SOURCE_REL)
    allowed_imports = {"__future__", "hashlib", "json", "typing"}
    forbidden_calls = {"__import__", "compile", "eval", "exec", "input", "open"}
    forbidden_attributes = {
        "chdir",
        "connect",
        "environ",
        "fork",
        "getenv",
        "import_module",
        "listdir",
        "mkdir",
        "now",
        "open",
        "Popen",
        "putenv",
        "randbytes",
        "read",
        "read_bytes",
        "read_text",
        "recv",
        "remove",
        "rename",
        "replace",
        "request",
        "rmdir",
        "run",
        "send",
        "sleep",
        "socket",
        "spawn",
        "system",
        "time",
        "today",
        "token_bytes",
        "token_hex",
        "unlink",
        "urandom",
        "urlopen",
        "utcnow",
        "walk",
        "write",
        "write_bytes",
        "write_text",
    }
    public_functions: set[str] = set()
    classes: list[tuple[str, tuple[str, ...]]] = []
    review_nodes: list[ast.FunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".", 1)[0] in allowed_imports, "E_AST_IMPORT", alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            require(node.level == 0 and module.split(".", 1)[0] in allowed_imports, "E_AST_IMPORT", module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in forbidden_calls, "E_AST_CALL", node.func.id)
            elif isinstance(node.func, ast.Attribute):
                require(node.func.attr not in forbidden_attributes, "E_AST_CALL", node.func.attr)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            raise CheckError("E_AST_MUTABLE_SCOPE: global/nonlocal")
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom)):
            raise CheckError("E_AST_ASYNC: async/generator")
        elif isinstance(node, ast.Dict):
            literal_keys: set[str] = set()
            for key in node.keys:
                if isinstance(key, ast.Constant) and type(key.value) is str:
                    require(key.value not in literal_keys, "E_AST_DUPLICATE_KEY", key.value)
                    literal_keys.add(key.value)
        elif isinstance(node, ast.FunctionDef):
            if not node.name.startswith("_"):
                public_functions.add(node.name)
            if node.name == "review_decision":
                review_nodes.append(node)
        elif isinstance(node, ast.ClassDef):
            bases = tuple(base.id for base in node.bases if isinstance(base, ast.Name))
            classes.append((node.name, bases))
    require(
        public_functions
        == {
            "build_owner_decision_record",
            "canonical_bytes",
            "domain_sha256",
            "exact_equal",
            "exact_keys",
            "expected_section_hashes",
            "render_tsv",
            "require",
            "review_decision",
        },
        "E_AST_PUBLIC",
        str(sorted(public_functions)),
    )
    require(
        classes == [("SignerRoleScopeAuthorityDecisionReviewError", ("ValueError",))],
        "E_AST_CLASS",
        str(classes),
    )
    require(len(review_nodes) == 1, "E_AST_REVIEW_COUNT", str(len(review_nodes)))
    args = review_nodes[0].args
    require(
        [argument.arg for argument in args.args] == ["record"]
        and not args.posonlyargs
        and not args.kwonlyargs
        and args.vararg is None
        and args.kwarg is None
        and not args.defaults,
        "E_AST_REVIEW_SIGNATURE",
        "review_decision(record)",
    )


def check_source_ast() -> None:
    check_source_ast_text(read_text(SOURCE_REL))


def expect_rejected(action: Callable[[], Any], label: str) -> None:
    try:
        action()
    except (CheckError, ValueError, TypeError, KeyError, IndexError, SyntaxError):
        return
    raise CheckError(f"E_MUTATION_ACCEPTED: {label}")


def mutate_scalar(value: Any) -> Any:
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is str:
        return "0" * 64 if len(value) == 64 and all(c in "0123456789abcdef" for c in value) else value + "_MUTATED"
    if value is None:
        return 0
    if type(value) is list:
        return ["MUTATED"] if not value else list(reversed(value))
    if type(value) is dict:
        candidate = copy.deepcopy(value)
        candidate["extra"] = False
        return candidate
    raise CheckError("E_MUTATOR_TYPE: unsupported")


def leaf_paths(value: Any, prefix: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    if type(value) is dict:
        if not value:
            return [prefix]
        result: list[tuple[Any, ...]] = []
        for key in sorted(value):
            result.extend(leaf_paths(value[key], prefix + (key,)))
        return result
    if type(value) is list:
        if not value:
            return [prefix]
        result = []
        for index, item in enumerate(value):
            result.extend(leaf_paths(item, prefix + (index,)))
        return result
    return [prefix]


def get_path(value: Any, path: tuple[Any, ...]) -> Any:
    cursor = value
    for component in path:
        cursor = cursor[component]
    return cursor


def set_path(value: Any, path: tuple[Any, ...], replacement: Any) -> None:
    cursor = value
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = replacement


def rehash_record(record: dict[str, Any]) -> None:
    record["section_sha256"] = expected_section_hashes(record)


def reject_record_both(
    candidate: dict[str, Any],
    expected: Mapping[str, Any],
    module: ModuleType,
    label: str,
) -> None:
    expect_rejected(lambda: validate_record(copy.deepcopy(candidate), expected), label + ":checker")
    expect_rejected(lambda: module.review_decision(copy.deepcopy(candidate)), label + ":source")


def exercise_paths(
    paths: Iterable[tuple[Any, ...]],
    category: str,
    record: Mapping[str, Any],
    expected: Mapping[str, Any],
    module: ModuleType,
) -> int:
    count = 0
    for path in paths:
        candidate = copy.deepcopy(record)
        set_path(candidate, path, mutate_scalar(get_path(candidate, path)))
        rehash_record(candidate)
        reject_record_both(candidate, expected, module, category + ":" + "/".join(map(str, path)))
        count += 1
    return count


def prefixed_leaves(record: Mapping[str, Any], prefix: tuple[Any, ...]) -> list[tuple[Any, ...]]:
    return [prefix + suffix for suffix in leaf_paths(get_path(record, prefix))]


def check_json_guards() -> int:
    probes = (
        b'{"a":1,"a":2}',
        b'{"v":NaN}',
        b'{"v":Infinity}',
        b'{"v":-Infinity}',
        b'{"v":9223372036854775808}',
        b'{"v":-9223372036854775809}',
        b'{"v":1.5}',
        b'\xef\xbb\xbf{"v":1}',
    )
    for index, raw in enumerate(probes):
        expect_rejected(lambda raw=raw: parse_json_bytes(raw, f"probe-{index}"), f"json-{index}")
    return len(probes)


def run_self_test(
    module: ModuleType,
    record: dict[str, Any],
    expected: Mapping[str, Any],
    receipt: dict[str, Any],
) -> dict[str, int]:
    counts = {
        "json_guard_negatives": check_json_guards(),
        "closed_world_negatives": 0,
        "grounding_matrix_negatives": 0,
        "scope_dimension_negatives": 0,
        "overclaim_negatives": 0,
        "section_hash_negatives": 0,
        "receipt_negatives": 0,
        "source_ast_negatives": 0,
    }
    source_text = read_text(SOURCE_REL)
    snippets = (
        "\nimport os\n",
        "\nimport socket\n",
        "\nfrom pathlib import Path\n",
        "\ndef public_extra():\n    pass\n",
        "\ndef _open_probe():\n    return open('x')\n",
        "\ndef _import_probe():\n    return __import__('os')\n",
        "\ndef _global_probe():\n    global MUTABLE\n",
        "\nasync def _async_probe():\n    pass\n",
        "\ndef _read_probe():\n    return value.read_text()\n",
        "\ndef review_decision(extra):\n    pass\n",
        "\n_DUPLICATE_LITERAL = {'x': 1, 'x': 2}\n",
        "\ndef _time_probe():\n    return value.utcnow()\n",
    )
    for index, snippet in enumerate(snippets):
        expect_rejected(lambda snippet=snippet: check_source_ast_text(source_text + snippet), f"ast-{index}")
        counts["source_ast_negatives"] += 1

    for key in sorted(record):
        candidate = copy.deepcopy(record)
        del candidate[key]
        reject_record_both(candidate, expected, module, "drop:" + key)
        counts["closed_world_negatives"] += 1
    candidate = copy.deepcopy(record)
    candidate["extra"] = False
    reject_record_both(candidate, expected, module, "extra:record")
    counts["closed_world_negatives"] += 1
    for section in sorted(key for key, value in record.items() if type(value) is dict):
        candidate = copy.deepcopy(record)
        candidate[section]["extra"] = False
        if section != "section_sha256":
            rehash_record(candidate)
        reject_record_both(candidate, expected, module, "extra:" + section)
        counts["closed_world_negatives"] += 1
        candidate = copy.deepcopy(record)
        first = sorted(candidate[section])[0]
        del candidate[section][first]
        if section != "section_sha256":
            rehash_record(candidate)
        reject_record_both(candidate, expected, module, "drop:" + section + ":" + first)
        counts["closed_world_negatives"] += 1

    grounding_paths = [
        path
        for path in leaf_paths(record)
        if path and path[0] != "section_sha256"
    ]
    counts["grounding_matrix_negatives"] = exercise_paths(
        grounding_paths, "grounding", record, expected, module
    )

    profile_base = (
        "authorized_component_contract",
        "policy_profile",
        "authorization_profiles",
    )
    scope_mutations: list[dict[str, Any]] = []
    for profile_index in range(2):
        other_index = 1 - profile_index
        for field in SCOPE_FIELDS:
            original = record["authorized_component_contract"]["policy_profile"]["authorization_profiles"][profile_index][field]
            cross_track = record["authorized_component_contract"]["policy_profile"]["authorization_profiles"][other_index][field]
            if cross_track == original:
                cross_track = original + "_CROSS_TRACK_DRIFT"
            for replacement in (
                cross_track,
                "*",
            ):
                candidate = copy.deepcopy(record)
                candidate_profile = get_path(candidate, profile_base + (profile_index,))
                candidate_profile[field] = replacement
                rehash_record(candidate)
                scope_mutations.append(candidate)
    candidate = copy.deepcopy(record)
    profiles = get_path(candidate, profile_base)
    profiles[1] = copy.deepcopy(profiles[0])
    rehash_record(candidate)
    scope_mutations.append(candidate)
    for field in SCOPE_FIELDS:
        candidate = copy.deepcopy(record)
        get_path(candidate, ("authorized_component_contract", "policy_profile"))["request_scope_fields"] = [
            item for item in SCOPE_FIELDS if item != field
        ]
        rehash_record(candidate)
        scope_mutations.append(candidate)
    for index, candidate in enumerate(scope_mutations):
        reject_record_both(candidate, expected, module, f"six-dimension:{index}")
        counts["scope_dimension_negatives"] += 1

    sentinel_strings = {
        "NONE",
        "NONE_PRODUCTION_SECURITY_REVIEWER_UNBOUND",
        "NOT_APPLICABLE_NOT_ENABLED",
        "FIXED_KAT_LABELS_ONLY_NOT_TRUSTED_TIME",
    }
    overclaim_paths: list[tuple[Any, ...]] = []
    for section in HASHED_SECTIONS:
        for path in prefixed_leaves(record, (section,)):
            value = get_path(record, path)
            if (
                value is False
                or (type(value) is int and value == 0)
                or (type(value) is list and not value)
                or value in sentinel_strings
            ):
                overclaim_paths.append(path)
    require(len(overclaim_paths) == len(set(overclaim_paths)), "E_OVERCLAIM_PATHS", "duplicates")
    counts["overclaim_negatives"] = exercise_paths(
        overclaim_paths, "overclaim", record, expected, module
    )

    for key in sorted(FROZEN_SECTION_HASHES):
        candidate = copy.deepcopy(record)
        candidate["section_sha256"][key] = "0" * 64
        reject_record_both(candidate, expected, module, "hash:" + key)
        counts["section_hash_negatives"] += 1

    for field in TSV_FIELDS:
        candidate = copy.deepcopy(receipt)
        candidate[field] = mutate_scalar(candidate[field])
        if field != "content_sha256":
            unsigned = dict(candidate)
            del unsigned["content_sha256"]
            candidate["content_sha256"] = domain_sha256(DOMAIN_PREFIXES["receipt"], unsigned)
        expect_rejected(lambda candidate=candidate: validate_receipt(candidate, record), "receipt:" + field)
        counts["receipt_negatives"] += 1

    counts["directed_negative_tests"] = sum(
        value for key, value in counts.items() if key.endswith("_negatives")
    )
    return counts


def manifest_oracle(counts: Mapping[str, int]) -> dict[str, Any]:
    return {
        "closed_world_negative_tests": counts["closed_world_negatives"],
        "directed_negative_tests": counts["directed_negative_tests"],
        "grounding_matrix_negative_tests": counts["grounding_matrix_negatives"],
        "json_guard_negative_tests": counts["json_guard_negatives"],
        "overclaim_negative_tests": counts["overclaim_negatives"],
        "predecessor_artifact_hashes_frozen": 8,
        "predecessor_exact_fast_receipt": "PASS",
        "predecessor_exact_full_receipt": "PASS",
        "receipt_negative_tests": counts["receipt_negatives"],
        "scope_profile_negative_tests": counts["scope_dimension_negatives"],
        "section_hash_negative_tests": counts["section_hash_negatives"],
        "source_ast_negative_tests": counts["source_ast_negatives"],
        "source_ast_purity": "PASS",
        "t06_semantic_specification_hashes_frozen": 1,
    }


def verify_manifest(record: Mapping[str, Any], receipt: Mapping[str, Any], counts: Mapping[str, int]) -> None:
    manifest = read_json(MANIFEST_REL)
    exact_keys(
        manifest,
        {
            "authorized_component_summary",
            "boundary",
            "date",
            "decision",
            "evidence_sha256",
            "logical_baseline_commit",
            "logical_baseline_parents",
            "logical_baseline_tree",
            "next_unit",
            "owner_semantics",
            "packet",
            "predecessor",
            "resource_binding",
            "results",
            "schema",
            "status",
            "t06_semantic_specification",
            "test_oracle",
        },
        "E_MANIFEST_KEYS",
    )
    require(
        manifest["schema"] == MANIFEST_SCHEMA
        and manifest["date"] == DATE
        and manifest["status"] == STATUS
        and manifest["decision"] == DECISION
        and manifest["next_unit"] == NEXT_UNIT
        and manifest["logical_baseline_commit"]
        == "7df72e2d49bbc25580d4dcb63bc1a183120bba77"
        and manifest["logical_baseline_tree"]
        == "7fc4786b814d81d97e8672bcae484c07e180f04a"
        and manifest["logical_baseline_parents"]
        == [
            "2707996e0616885fa51da9b908764f017a67299f",
            "2a26de5b99886922240350fadefa07bc8f4c5dcd",
        ],
        "E_MANIFEST_IDENTITY",
        "identity/baseline",
    )
    evidence_paths = {SOURCE_REL, CHECKER_REL, DECISION_REL, EXPECTED_REL}
    exact_keys(manifest["evidence_sha256"], evidence_paths, "E_MANIFEST_EVIDENCE_KEYS")
    require(
        manifest["evidence_sha256"]
        == {relative: raw_sha256(relative) for relative in evidence_paths},
        "E_MANIFEST_EVIDENCE",
        "dynamic checker and frozen evidence hashes",
    )
    packet = manifest["packet"]
    exact_keys(packet, {"all_add_required", "modes", "path_count", "paths"}, "E_PACKET_KEYS")
    require(
        packet["all_add_required"] is True
        and packet["path_count"] == 7
        and len(packet["paths"]) == 7
        and set(packet["paths"]) == set(PACK_PATHS)
        and packet["modes"] == PACK_MODES,
        "E_PACKET",
        "exact seven paths/modes",
    )
    require(manifest["test_oracle"] == manifest_oracle(counts), "E_MANIFEST_ORACLE", "self-test counts")
    results = manifest["results"]
    exact_keys(
        results,
        {
            "all_nonclaims_explicit",
            "allowed_operation_count",
            "authorization_profile_count",
            "authorized_component_contract_sha256",
            "boundary_sha256",
            "content_sha256",
            "decision_provenance_sha256",
            "decision_record_sha256",
            "forbidden_operation_count",
            "implementation_authority_sha256",
            "nonclaim_field_count",
            "nonclaims_sha256",
            "owner_implementation_actor_sha256",
            "request_scope_dimension_count",
            "resource_binding_sha256",
            "rollback_sha256",
            "state_count",
            "state_machine_sha256",
            "transition_count",
        },
        "E_RESULTS_KEYS",
    )
    require(
        results
        == {
            "all_nonclaims_explicit": True,
            "allowed_operation_count": 8,
            "authorization_profile_count": 2,
            "authorized_component_contract_sha256": FROZEN_SECTION_HASHES["authorized_component_contract_sha256"],
            "boundary_sha256": FROZEN_SECTION_HASHES["boundary_sha256"],
            "content_sha256": RECEIPT_CONTENT_SHA256,
            "decision_provenance_sha256": FROZEN_SECTION_HASHES["decision_provenance_sha256"],
            "decision_record_sha256": DECISION_DOMAIN_SHA256,
            "forbidden_operation_count": 31,
            "implementation_authority_sha256": FROZEN_SECTION_HASHES["implementation_authority_sha256"],
            "nonclaim_field_count": 71,
            "nonclaims_sha256": FROZEN_SECTION_HASHES["nonclaims_sha256"],
            "owner_implementation_actor_sha256": FROZEN_SECTION_HASHES["owner_implementation_actor_sha256"],
            "request_scope_dimension_count": 6,
            "resource_binding_sha256": FROZEN_SECTION_HASHES["resource_binding_sha256"],
            "rollback_sha256": FROZEN_SECTION_HASHES["rollback_sha256"],
            "state_count": 5,
            "state_machine_sha256": FROZEN_SECTION_HASHES["state_machine_sha256"],
            "transition_count": 4,
        },
        "E_RESULTS",
        "receipt/record result binding",
    )
    predecessor = manifest["predecessor"]
    exact_keys(
        predecessor,
        {
            "artifact_raw_sha256",
            "authorization_consumption_state",
            "bootstrap_trust_authentication_implemented",
            "fast_stdout_line_count",
            "fast_stdout_sha256",
            "full_stdout_line_count",
            "full_stdout_sha256",
            "gate_path",
            "gate_raw_sha256",
            "implementation_authority_single_use_consumed",
            "integration_commit",
            "integration_parents",
            "integration_tree",
            "local_t05_specification_exercised",
            "local_t06_specification_exercised",
            "manifest_path",
            "manifest_raw_sha256",
            "receipt_content_sha256",
            "signer_role_scope_authorization_implemented",
            "source_commit",
            "source_parent",
            "source_tree",
        },
        "E_MANIFEST_PREDECESSOR_KEYS",
    )
    require(
        predecessor["artifact_raw_sha256"] == PREDECESSOR_RAW_SHA256
        and predecessor["integration_commit"]
        == record["predecessor"]["integration_commit"]
        and predecessor["integration_tree"] == record["predecessor"]["integration_tree"]
        and predecessor["integration_parents"] == record["predecessor"]["integration_parents"]
        and predecessor["receipt_content_sha256"] == PREDECESSOR_RECEIPT_CONTENT_SHA256
        and predecessor["authorization_consumption_state"] == "CONSUMED_SCOPE_COMPLETE"
        and predecessor["implementation_authority_single_use_consumed"] is True
        and predecessor["bootstrap_trust_authentication_implemented"] is True,
        "E_MANIFEST_PREDECESSOR",
        "T05 binding",
    )
    summary = manifest["authorized_component_summary"]
    exact_keys(
        summary,
        {
            "authorization_profile_count",
            "authorization_profiles",
            "authorized_candidate_surface_component_count",
            "authorized_candidate_surface_components",
            "authorized_component_contract_sha256",
            "authorized_local_threat_specification_count",
            "authorized_local_threat_specifications",
            "bootstrap_trust_authentication_implemented",
            "current_decision_candidate_surface_components_implemented",
            "default_effect",
            "future_successor_minimum_independent_reviewer_lane_count",
            "request_scope_dimension_count",
            "request_scope_fields",
            "required_reviewer_lanes",
            "signer_role_scope_authorization_implemented",
            "target_production_control",
            "wildcards_allowed",
        },
        "E_MANIFEST_SUMMARY_KEYS",
    )
    require(
        summary["authorized_candidate_surface_component_count"] == 1
        and summary["authorized_candidate_surface_components"]
        == ["SIGNER_ROLE_SCOPE_AUTHORIZATION_SYNTHETIC_VERIFIER"]
        and summary["authorized_local_threat_specifications"] == ["T06"]
        and summary["target_production_control"] == "SIGNER_ROLE_SCOPE_AUTHORIZATION"
        and summary["authorization_profile_count"] == 2
        and summary["authorization_profiles"] == list(EXPECTED_TRACKS)
        and summary["request_scope_dimension_count"] == 6
        and summary["request_scope_fields"] == list(SCOPE_FIELDS)
        and summary["default_effect"] == "DENY"
        and summary["wildcards_allowed"] is False
        and summary["bootstrap_trust_authentication_implemented"] is True
        and summary["signer_role_scope_authorization_implemented"] is False
        and summary["authorized_component_contract_sha256"]
        == FROZEN_SECTION_HASHES["authorized_component_contract_sha256"],
        "E_MANIFEST_SUMMARY",
        "T06 component summary",
    )
    boundary = manifest["boundary"]
    exact_keys(
        boundary,
        {
            "authorization_effective_only_after_integrated_full_gate",
            "bootstrap_trust_authentication_implemented",
            "decision_full_gate_consumes_new_authority",
            "downstream_gate_count",
            "downstream_gates_authorized",
            "future_successor_candidate_surface_component_total",
            "implementation_authority_single_use_consumed",
            "isolated_lab_predecessor_surface_components_implemented",
            "local_predecessor_threat_specifications_covered",
            "local_t06_specification_exercised",
            "local_t07_specification_exercised",
            "owner_handoff_eligible",
            "predecessor_implementation_authority_consumed",
            "production_environment_implementation_authorized",
            "production_ingestion_control_count",
            "production_ingestion_controls_implemented",
            "production_ingestion_controls_runtime_exercised",
            "production_ingestion_enabled",
            "production_ingestion_implemented",
            "production_security_reviewer_bound",
            "production_threat_specification_count",
            "production_threat_specifications_runtime_exercised",
            "production_validated_evidence_items",
            "provider_authority",
            "real_evidence_items_present",
            "runtime_admission_granted",
            "runtime_admission_ready",
            "runtime_authority",
            "runtime_evidence_accepted",
            "runtime_owner_decision_recorded",
            "runtime_owner_identity_bound",
            "runtime_prerequisite_count",
            "runtime_prerequisites_satisfied",
            "runtime_side_effects_unlocked",
            "signer_role_scope_authorization_isolated_lab_implementation_authorized",
            "signer_role_scope_authorization_isolated_lab_implemented",
            "track_subject_binding_implemented",
        },
        "E_MANIFEST_BOUNDARY_KEYS",
    )
    require(
        boundary["bootstrap_trust_authentication_implemented"] is True
        and boundary["signer_role_scope_authorization_isolated_lab_implemented"] is False
        and boundary["local_t06_specification_exercised"] is False
        and boundary["local_t07_specification_exercised"] is False
        and boundary["runtime_authority"] is False
        and boundary["provider_authority"] is False
        and boundary["production_ingestion_controls_implemented"] == 0,
        "E_MANIFEST_BOUNDARY",
        "no runtime/provider authority",
    )
    resources = manifest["resource_binding"]
    exact_keys(
        resources,
        {
            "allowed_resource_classes",
            "component_runtime_network",
            "credential_handle_count",
            "credential_path_count",
            "currency_scope",
            "effective_external_paid_spend_cap",
            "max_authentication_bundle_bytes",
            "max_authorization_grants",
            "max_authorization_policy_bytes",
            "max_authorization_request_bytes",
            "max_input_frame_bytes",
            "max_parallel_workers",
            "max_private_scratch_bytes",
            "max_trust_policy_bytes",
            "owner_supplied_numeric_budget_cap",
            "private_key_or_seed_material_authorized",
            "production_resource_authority_bound",
            "provider_endpoint_count",
            "public_input_count",
            "signing_or_key_generation_authorized",
            "test_data_scope",
        },
        "E_MANIFEST_RESOURCE_KEYS",
    )
    require(
        resources["component_runtime_network"] is False
        and resources["effective_external_paid_spend_cap"] == 0
        and resources["provider_endpoint_count"] == 0
        and resources["credential_handle_count"] == 0
        and resources["credential_path_count"] == 0
        and resources["max_authorization_grants"] == 2
        and resources["max_authorization_policy_bytes"] == 65536
        and resources["max_authorization_request_bytes"] == 16384
        and resources["max_private_scratch_bytes"] == 67108864,
        "E_MANIFEST_RESOURCE",
        "bounded resource summary",
    )
    owner = manifest["owner_semantics"]
    exact_keys(
        owner,
        {
            "binding_basis",
            "cryptographic_identity_verified",
            "directive_observed_in_owner_session",
            "directive_semantics",
            "implementation_authority_effective_only_after_integrated_full_gate",
            "owner_supplied_numeric_budget_cap",
            "runtime_owner_decision_recorded",
            "runtime_owner_identity_bound",
            "semantic_actor_binding_recorded",
            "semantic_actor_label",
            "semantic_actor_role",
            "signature_observed",
            "source_or_fast_replay_effective_authority",
        },
        "E_MANIFEST_OWNER_KEYS",
    )
    require(
        owner["semantic_actor_label"] == "pallasting"
        and owner["semantic_actor_role"] == "PROJECT_OWNER"
        and owner["semantic_actor_binding_recorded"] is True
        and owner["directive_observed_in_owner_session"] is True
        and owner["cryptographic_identity_verified"] is False
        and owner["signature_observed"] is False
        and owner["runtime_owner_identity_bound"] is False
        and owner["runtime_owner_decision_recorded"] is False
        and owner["source_or_fast_replay_effective_authority"] is False,
        "E_MANIFEST_OWNER",
        "semantic-only owner binding",
    )
    t06 = manifest["t06_semantic_specification"]
    exact_keys(
        t06,
        {
            "control_id",
            "mandatory_scope_dimensions",
            "path",
            "primary_failure_code",
            "raw_sha256",
            "satisfiable_by_offline",
            "threat_case_id",
        },
        "E_MANIFEST_T06_KEYS",
    )
    require(
        t06
        == {
            "control_id": "SIGNER_ROLE_SCOPE_AUTHORIZATION",
            "mandatory_scope_dimensions": [
                "owner_class",
                "evidence_class",
                "track",
                "subject",
                "audience",
                "nonce_scope",
            ],
            "path": T06_SPEC_REL,
            "primary_failure_code": "E_PRODUCTION_SIGNER_AUTHORIZATION_FAILED",
            "raw_sha256": T06_SPEC_RAW_SHA256,
            "satisfiable_by_offline": False,
            "threat_case_id": "T06",
        },
        "E_MANIFEST_T06",
        "semantic specification binding",
    )
    require(receipt["content_sha256"] == results["content_sha256"], "E_MANIFEST_RECEIPT", "content")


def evaluate(mode: str) -> str:
    check_json_guards()
    verify_frozen_inputs()
    expected_record = read_json(DECISION_REL)
    validate_semantics(expected_record)
    record = read_json(DECISION_REL)
    validate_record(record, expected_record)
    check_source_ast()
    module = load_source()
    require(
        exact_equal(module.build_owner_decision_record(), expected_record),
        "E_SOURCE_BUILD",
        "source builder differs from frozen owner record",
    )
    source_receipt = module.review_decision(copy.deepcopy(record))
    require(type(source_receipt) is dict, "E_SOURCE_RECEIPT", "not object")
    rendered = validate_receipt(source_receipt, record)
    require(module.render_tsv(copy.deepcopy(source_receipt)) == rendered, "E_SOURCE_RENDER", "TSV")

    if mode == "candidate":
        return rendered
    counts = run_self_test(module, record, expected_record, copy.deepcopy(source_receipt))
    if mode == "normal":
        verify_manifest(record, source_receipt, counts)
        return rendered
    ordered = (
        "directed_negative_tests",
        "json_guard_negatives",
        "closed_world_negatives",
        "grounding_matrix_negatives",
        "scope_dimension_negatives",
        "overclaim_negatives",
        "section_hash_negatives",
        "receipt_negatives",
        "source_ast_negatives",
    )
    lines = ["self_test\tPASS"]
    lines.extend(f"{key}\t{counts[key]}" for key in ordered)
    lines.extend(
        (
            "predecessor_artifact_hashes_frozen\t8",
            "predecessor_exact_receipt_lines\t44",
            "t06_scope_dimensions\t6",
            "source_ast_purity\tPASS",
            "manifest_evidence_validation\tDEFAULT_ONLY",
        )
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--candidate", action="store_true")
    group.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    mode = "candidate" if args.candidate else "self-test" if args.self_test else "normal"
    try:
        print(evaluate(mode), end="")
    except (
        CheckError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        OSError,
        SyntaxError,
    ) as error:
        print("signer role/scope authority decision pack check failed: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
