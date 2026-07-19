#!/usr/bin/env python3
"""Independent checker for the T08 end-to-end subject-binding decision pack.

The source reviewer is the subject under review.  This checker owns the JSON
decoder, frozen byte and domain anchors, receipt oracle, T07 release grounding,
T07/T08/T09 semantic split, source-AST policy, and mutation suite.  It does not run
another gate and grants no runtime, provider, production, evidence, or output
authority.
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
from typing import Any, Callable, Iterable, Mapping, NoReturn


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024

SOURCE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_end_to_end_subject_binding_isolated_lab_implementation_authority_and_"
    "resource_binding_decision_v1.py"
)
CHECKER_REL = (
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_end_to_end_subject_binding_isolated_lab_implementation_authority_and_"
    "resource_binding_decision_v1_pack.py"
)
DECISION_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_end_to_end_subject_binding_isolated_lab_implementation_"
    "authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
)
EXPECTED_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_end_to_end_subject_binding_isolated_lab_implementation_"
    "authority_and_resource_binding_decision_v1_pack.expected.v0.tsv"
)
MANIFEST_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_end_to_end_subject_binding_isolated_lab_implementation_"
    "authority_and_resource_binding_decision_v1_pack_v0.json"
)
REPORT_REL = (
    "docs/reports/goal-c-u/2026-07-18-biocortex-track-b-reference-provider-"
    "fault-injection-runner-end-to-end-subject-binding-isolated-lab-implementation-"
    "authority-and-resource-binding-decision-v1-pack.md"
)
GATE_REL = (
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-end-to-end-subject-binding-isolated-lab-implementation-authority-and-"
    "resource-binding-decision-v1-pack.sh"
)

PREDECESSOR_MANIFEST_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_track_profile_binding_synthetic_exact_packet_profile_"
    "provider_or_lab_profile_namespace_configuration_sha256_and_non_"
    "substitutable_track_verifier_isolated_lab_v1_pack_v0.json"
)
PREDECESSOR_EXPECTED_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_track_profile_binding_synthetic_exact_packet_profile_"
    "provider_or_lab_profile_namespace_configuration_sha256_and_non_"
    "substitutable_track_verifier_isolated_lab_v1_pack.expected.v0.tsv"
)
PREDECESSOR_FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_track_profile_binding_synthetic_exact_packet_profile_"
    "provider_or_lab_profile_namespace_configuration_sha256_and_non_"
    "substitutable_track_verifier_isolated_lab_v1_pack_synthetic_v0.json"
)
PREDECESSOR_GATE_REL = (
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-track-profile-binding-synthetic-exact-packet-profile-provider-or-"
    "lab-profile-namespace-configuration-sha256-and-non-substitutable-track-"
    "verifier-isolated-lab-v1-pack.sh"
)
T08_SPEC_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_runtime_prerequisite_evidence_packet_offline_integration_"
    "and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
)

SOURCE_RAW_SHA256 = "1d662858461645b69908791662b5503d016a91823087b6895b7a225c30f9f06b"
DECISION_RAW_SHA256 = (
    "2fd96dd1bfc038c65ea067d69b928148763d7e8e0671ef3d378bc72118332277"
)
EXPECTED_RAW_SHA256 = (
    "aa25a61c1da03c75042de8680037f8a895035310d48dccae0472d6eb8c8fafad"
)
DECISION_CANONICAL_SHA256 = (
    "9dd154809c0adeee59e78d7cb43c39efd5331e77608c58ca718396d755369453"
)
DECISION_DOMAIN_SHA256 = (
    "749a35600f49114d6984e841d4926e0982a0fd6aa87d12b7703de0bc631e9a90"
)
RECEIPT_CONTENT_SHA256 = (
    "9a3e0bd2349b328eaa552b0896e76a7b0011db901e025233971d63b8190b4b07"
)

RECORD_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_end_to_end_subject_binding_isolated_lab_implementation_authority_and_"
    "resource_binding_decision.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_end_to_end_subject_binding_isolated_lab_implementation_authority_and_"
    "resource_binding_decision_v1.receipt.v0"
)
MANIFEST_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_end_to_end_subject_binding_isolated_lab_implementation_authority_and_"
    "resource_binding_decision_v1_pack_manifest.v0"
)
DATE = "2026-07-18"
STATUS = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "END_TO_END_SUBJECT_BINDING_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_"
    "SCOPE_RECORDED_ZERO_EXTERNAL_SPEND_NO_RUNTIME_OR_PROVIDER_AUTHORITY"
)
DECISION = (
    "AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_T08_END_TO_END_SUBJECT_BINDING_ISOLATED_LAB_"
    "COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED"
)
MODE = "ISOLATED_LAB_FIRST"
CURRENT_STATE = "AUTHORIZED_T08_END_TO_END_SUBJECT_BINDING_ISOLATED_LAB_EXACT_UNIT"
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "END_TO_END_SUBJECT_BINDING_SYNTHETIC_EXACT_T07_RECEIPT_TRACK_PREREQUISITE_"
    "SOURCE_BUILD_SESSION_CHANNEL_SCHEDULE_ROW_SET_AND_SUBJECT_"
    "VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
)

PREDECESSOR_RAW_SHA256 = {
    (
        "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-"
        "injection-runner-track-profile-binding-synthetic-exact-packet-profile-"
        "provider-or-lab-profile-namespace-configuration-sha256-and-non-"
        "substitutable-track-verifier-isolated-lab-v1.schema.json"
    ): "7cdbb084c193e5936cd66237504f40cd3d050a3b5f814c0e8e92992a68ac9634",
    (
        "docs/reports/goal-c-u/2026-07-18-biocortex-track-b-reference-provider-"
        "fault-injection-runner-track-profile-binding-synthetic-exact-packet-"
        "profile-provider-or-lab-profile-namespace-configuration-sha256-and-"
        "non-substitutable-track-verifier-isolated-lab-v1-pack.md"
    ): "31398214bd12861b8ae614e1a255dcd58325186d74602b6f8ef92e4f802be128",
    PREDECESSOR_GATE_REL:
        "aad0e8e3a71cd1e5d94921613ccddf936cadf4a4a5099831c0aeecf243d7261d",
    (
        "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_"
        "runner_track_profile_binding_synthetic_exact_packet_profile_provider_"
        "or_lab_profile_namespace_configuration_sha256_and_non_substitutable_"
        "track_verifier_isolated_lab_v1.py"
    ): "777bfaa0c18569e68af1cf7c6e5957f1712079bfcfe4e2085e607dba5c9fcb23",
    (
        "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_track_profile_binding_synthetic_exact_packet_profile_"
        "provider_or_lab_profile_namespace_configuration_sha256_and_non_"
        "substitutable_track_verifier_isolated_lab_v1_pack.py"
    ): "27c25f6c75504925859d693d09c391a6f60ec2c34aab84dda26bd610d4b94e91",
    PREDECESSOR_EXPECTED_REL:
        "bb1bb0f215cf8e272335dbec1d6c7ac2958dd52985a090a9e9fbf2abaf72585a",
    PREDECESSOR_FIXTURE_REL:
        "97a45faa1a2e4d1198c5ea5222ada4d31e46093c8956ecb319a2912e46b5b4e4",
    PREDECESSOR_MANIFEST_REL:
        "75bcb6f0a47395b0aa5969f8071701a5ef8d777e902c255299d069413278b7e5",
}
T08_SPEC_RAW_SHA256 = (
    "3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6"
)
PREDECESSOR_RECEIPT_CONTENT_SHA256 = (
    "44c79026c2d98dc99e48dac4a1f047f634a521a5a224a0933a852ebe6c78776a"
)
T07_TRACK_RECEIPTS = {
    "MANAGED_SPANNER_CLOUD_KMS": (
        "5db2449ebf80e668ac7fc8ccaec6cc62a7461d8874809543a74ee9b7b5d725b6"
    ),
    "SELF_HOSTED_ETCD_OPENBAO": (
        "3f49518a74a6a7075335db5b139035613ff992d1deedc0c31216832dd4dcb014"
    ),
}

DOMAIN_PREFIXES = {
    "authorized_component_contract": (
        b"agent-bridge\x00biocortex-ab\x00t08-end-to-end-subject-binding-authority\x00"
        b"authorized-component-contract\x00v1\x00"
    ),
    "decision_provenance": (
        b"agent-bridge\x00biocortex-ab\x00t08-end-to-end-subject-binding-authority\x00"
        b"decision-provenance\x00v1\x00"
    ),
    "implementation_authority": (
        b"agent-bridge\x00biocortex-ab\x00t08-end-to-end-subject-binding-authority\x00"
        b"implementation-authority\x00v1\x00"
    ),
    "owner_implementation_actor": (
        b"agent-bridge\x00biocortex-ab\x00t08-end-to-end-subject-binding-authority\x00"
        b"owner-implementation-actor\x00v1\x00"
    ),
    "resource_binding": (
        b"agent-bridge\x00biocortex-ab\x00t08-end-to-end-subject-binding-authority\x00"
        b"resource-binding\x00v1\x00"
    ),
    "state_machine": (
        b"agent-bridge\x00biocortex-ab\x00t08-end-to-end-subject-binding-authority\x00"
        b"state-machine\x00v1\x00"
    ),
    "rollback": (
        b"agent-bridge\x00biocortex-ab\x00t08-end-to-end-subject-binding-authority\x00"
        b"rollback\x00v1\x00"
    ),
    "boundary": (
        b"agent-bridge\x00biocortex-ab\x00t08-end-to-end-subject-binding-authority\x00"
        b"boundary\x00v1\x00"
    ),
    "nonclaims": (
        b"agent-bridge\x00biocortex-ab\x00t08-end-to-end-subject-binding-authority\x00"
        b"nonclaims\x00v1\x00"
    ),
    "decision_record": (
        b"agent-bridge\x00biocortex-ab\x00t08-end-to-end-subject-binding-authority\x00"
        b"decision-record\x00v1\x00"
    ),
    "receipt_content": (
        b"agent-bridge\x00biocortex-ab\x00t08-end-to-end-subject-binding-authority\x00"
        b"receipt-content\x00v1\x00"
    ),
}
HASHED_SECTIONS = (
    "authorized_component_contract",
    "decision_provenance",
    "implementation_authority",
    "owner_implementation_actor",
    "resource_binding",
    "state_machine",
    "rollback",
    "boundary",
    "nonclaims",
)
FROZEN_SECTION_HASHES = {
    "authorized_component_contract_sha256": (
        "8779aa043190b2ca00edbcf0a66c407b25a9d2ff0d380d8034aa9b28500e84d6"
    ),
    "decision_provenance_sha256": (
        "737c8220a2d058d1d68c5385d58e767e2e1b579f1c543efe4c78e142cca59d97"
    ),
    "implementation_authority_sha256": (
        "4966ee02e7bbd3369939713f70caff6546ed88330e21ebc520ec37c821053010"
    ),
    "owner_implementation_actor_sha256": (
        "c535bc8e56e32f66a53dac92ff307c6d8ce52adf9f4017429a39db21d45f6906"
    ),
    "resource_binding_sha256": (
        "7266ba8b6c8cef476b661ebdac628b3f1151f35ce7a9deb0b58376b3f2f55d91"
    ),
    "state_machine_sha256": (
        "aa751d4eec63be3081449b89816e4f24b1343fcf9d8b65a3e3dcef9bfb1f81f6"
    ),
    "rollback_sha256": (
        "23548abdd57447dbb0a2d70f468e8e5dc261b6435002ac4e537641f5cce0ed48"
    ),
    "boundary_sha256": (
        "c4ffaa0a78914760b8ccce80a9009eba00207252e8edf73e28a6df43581cdc90"
    ),
    "nonclaims_sha256": (
        "df3d2ca0190eafd1b62a6a03f4e84272662003f90ef0358d417c66cc9b24aa50"
    ),
}

REQUEST_FIELDS = (
    "prerequisite_id", "source_id", "build_id", "session_id",
    "channel_id", "schedule_id", "row_set_id", "subject",
)
POLICY_MATCH_FIELDS = (
    "t07_receipt_content_sha256",
    "track_id",
    *REQUEST_FIELDS,
)
FORBIDDEN_REQUEST_FIELDS = (
    "audience",
    "configuration_sha256",
    "declared_role_class",
    "frame_sha256",
    "namespace_id",
    "nonce",
    "packet_profile_id",
    "provider_or_lab_profile_id",
    "signer_key_id",
    "signer_key_version",
    "signer_role",
    "t07_receipt",
    "t07_receipt_content_sha256",
    "track_id",
)
EXPECTED_TRACKS = ("MANAGED_SPANNER_CLOUD_KMS", "SELF_HOSTED_ETCD_OPENBAO")
EXPECTED_PROFILES = (
    {
        "build_id": "KAT_MANAGED_T08_BUILD_V1",
        "channel_id": "KAT_MANAGED_T08_CHANNEL_V1",
        "prerequisite_id": "KAT_MANAGED_T08_PREREQUISITE_V1",
        "row_set_id": "KAT_MANAGED_T08_ROW_SET_V1",
        "schedule_id": "KAT_MANAGED_T08_SCHEDULE_V1",
        "session_id": "KAT_MANAGED_T08_SESSION_V1",
        "source_id": "KAT_MANAGED_T08_SOURCE_V1",
        "subject": "KAT_MANAGED_VALID_MINIMAL_FRAME_SUBJECT_V1",
        "t07_receipt_content_sha256": T07_TRACK_RECEIPTS[
            "MANAGED_SPANNER_CLOUD_KMS"
        ],
        "track_id": "MANAGED_SPANNER_CLOUD_KMS",
    },
    {
        "build_id": "KAT_SELF_HOSTED_T08_BUILD_V1",
        "channel_id": "KAT_SELF_HOSTED_T08_CHANNEL_V1",
        "prerequisite_id": "KAT_SELF_HOSTED_T08_PREREQUISITE_V1",
        "row_set_id": "KAT_SELF_HOSTED_T08_ROW_SET_V1",
        "schedule_id": "KAT_SELF_HOSTED_T08_SCHEDULE_V1",
        "session_id": "KAT_SELF_HOSTED_T08_SESSION_V1",
        "source_id": "KAT_SELF_HOSTED_T08_SOURCE_V1",
        "subject": "KAT_SELF_HOSTED_VALID_MINIMAL_FRAME_SUBJECT_V1",
        "t07_receipt_content_sha256": T07_TRACK_RECEIPTS[
            "SELF_HOSTED_ETCD_OPENBAO"
        ],
        "track_id": "SELF_HOSTED_ETCD_OPENBAO",
    },
)

ALLOWED_OPERATIONS = (
    "ADD_CLOSED_WORLD_SYNTHETIC_END_TO_END_SUBJECT_BINDING_POLICY_REQUEST_AND_RECEIPT_SCHEMAS",
    "ADD_EXACT_TWO_PROFILE_DEFAULT_REJECT_END_TO_END_SUBJECT_BINDING_REGISTRY_KATS",
    "ADD_PURE_END_TO_END_SUBJECT_BINDING_REFERENCE_VERIFIER_FOR_FIXED_PUBLIC_ONLY_KATS",
    "COMPOSE_EXACTLY_ONCE_WITH_FROZEN_T07_PREDECESSOR_PUBLIC_REVIEW_API",
    "BIND_T07_RECEIPT_CONTENT_AND_TRACK_TO_EXACT_PREREQUISITE_SOURCE_BUILD_SESSION_CHANNEL_SCHEDULE_ROW_SET_AND_SUBJECT",
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
    "ADD_OR_FETCH_UNPINNED_DEPENDENCY",
    "ALLOW_AMBIGUOUS_ZERO_OR_MULTIPLE_MATCHING_PROFILES",
    "ALLOW_DEFAULT_ALLOW_WILDCARD_PREFIX_OR_HIERARCHICAL_MATCH",
    "ALLOW_GROUP_ROLE_OR_PARENT_SCOPE_INHERITANCE",
    "AUTHORIZE_OR_INJECT_FAULT",
    "AUTHORIZE_OUTPUT_OR_CLAIM",
    "BIND_OR_CLAIM_PREREQUISITE_BUILD_SESSION_CHANNEL_SCHEDULE_ROW_SET_OR_SUBJECT_TRUTH",
    "BIND_PRODUCTION_OWNER_EVIDENCE_AUDIENCE_OR_NONCE",
    "BIND_PROVIDER_OR_PRODUCTION_ENDPOINT",
    "CALL_PROVIDER_OR_ATTEMPT_WIRE",
    "CLAIM_CONFIGURATION_NAMESPACE_PACKET_PROFILE_OR_PROVIDER_PROFILE_CURRENTNESS_OR_TRUTH",
    "CLAIM_PRODUCTION_TRACK_SUBJECT_BINDING_OR_MITIGATION",
    "COMMIT_PRIVATE_KEY_TEST_SEED_OR_SECRET_SHAPED_MATERIAL",
    "CREATE_RUNTIME_OR_EXPERIMENT_ROW",
    "DEPLOY_OR_ENABLE_PRODUCTION_INGESTION",
    "DERIVE_END_TO_END_SUBJECT_BINDING_POLICY_FROM_FRAME_BUNDLE_OR_REQUEST",
    "ESTABLISH_DURABLE_CUSTODY_OR_REPLAY_LEDGER",
    "IMPLEMENT_T09_CONTENT_IDENTITY_QUARANTINE_CUSTODY_OR_REPLAY_CAS",
    "LAUNCH_RUNNER_OR_BACKGROUND_DAEMON",
    "PARSE_FRAME_AGAIN_TO_DERIVE_T08_PREREQUISITE_SOURCE_BUILD_SESSION_CHANNEL_SCHEDULE_ROW_SET_TRACK_OR_SUBJECT",
    "PERSIST_END_TO_END_SUBJECT_BINDING_POLICY_REQUEST_OR_RESULT",
    "PROVISION_PAID_OR_EXTERNAL_RESOURCE",
    "READ_AMBIENT_DEFAULT_OR_SYSTEM_TRUST_OR_CREDENTIAL_CHAIN",
    "REGISTER_OR_IMPORT_INTO_PRODUCTION_RUNTIME",
    "REPRESENT_RUNTIME_OWNER_DECISION",
    "SATISFY_RUNTIME_PREREQUISITE",
    "TAKE_TRACK_ID_FROM_DETACHED_T08_REQUEST_OR_RAW_FRAME",
    "USE_AMBIENT_OR_PRODUCTION_TRUSTED_TIME",
)
COMPONENT_LIMITS = {
    "max_array_items": 64,
    "max_authentication_bundle_bytes": 65536,
    "max_authorization_policy_bytes": 65536,
    "max_authorization_request_bytes": 16384,
    "max_input_frame_bytes": 1048576,
    "max_json_depth": 32,
    "max_json_nodes": 4096,
    "max_object_members": 256,
    "max_parallel_workers": 1,
    "max_predecessor_review_calls": 1,
    "max_private_scratch_bytes": 67108864,
    "max_profile_string_utf8_bytes": 256,
    "max_end_to_end_subject_binding_entries": 2,
    "max_end_to_end_subject_binding_policy_bytes": 65536,
    "max_end_to_end_subject_binding_request_bytes": 16384,
    "max_trust_policy_bytes": 65536,
    "public_input_count": 10,
}

TOP_LEVEL_KEYS = (
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
)
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
authorized_local_threat_specifications binding_profile_count
binding_request_field_count binding_policy_match_dimension_count
default_disposition wildcards_allowed public_input_count
track_profile_binding_implemented end_to_end_subject_binding_implemented
track_subject_binding_production_control_implemented
local_t07_specification_exercised local_t08_specification_exercised
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
predecessor_receipt_content_sha256 t08_semantic_specification_raw_sha256
content_sha256""".split()
)
INTEGER_RECEIPT_FIELDS = {
    "authorized_candidate_surface_component_count",
    "authorized_local_threat_specification_count",
    "binding_profile_count",
    "binding_request_field_count",
    "binding_policy_match_dimension_count",
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
    """Fail-closed independent-checker error."""


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise CheckError(f"{code}: {detail}")


def exact_keys(value: Any, expected: Iterable[str], code: str) -> None:
    require(type(value) is dict, code, "not a plain object")
    require(set(value) == set(expected), code, "closed-world key mismatch")


def exact_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(
            exact_equal(left[key], right[key]) for key in left
        )
    if type(left) is list:
        return len(left) == len(right) and all(
            exact_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return bool(left == right)


def validate_json_value(
    value: Any,
    depth: int = 0,
    node_counter: list[int] | None = None,
) -> None:
    if node_counter is None:
        node_counter = [0]
    node_counter[0] += 1
    require(node_counter[0] <= 4096, "E_JSON_NODES", str(node_counter[0]))
    require(depth <= 32, "E_JSON_DEPTH", str(depth))
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        require(-(2**63) <= value <= 2**63 - 1, "E_JSON_INT", str(value))
        return
    if type(value) is str:
        try:
            raw = value.encode("utf-8", "strict")
        except UnicodeEncodeError as error:
            raise CheckError("E_JSON_UNICODE: invalid scalar") from error
        require(len(raw) <= 1024 * 1024, "E_JSON_STRING", str(len(raw)))
        return
    if type(value) is list:
        require(len(value) <= 64, "E_JSON_ARRAY", str(len(value)))
        for item in value:
            validate_json_value(item, depth + 1, node_counter)
        return
    require(type(value) is dict, "E_JSON_TYPE", type(value).__name__)
    require(len(value) <= 256, "E_JSON_OBJECT", str(len(value)))
    for key, item in value.items():
        require(type(key) is str and key != "", "E_JSON_KEY", repr(key))
        validate_json_value(key, depth + 1, node_counter)
        validate_json_value(item, depth + 1, node_counter)


def canonical_bytes(value: Any) -> bytes:
    validate_json_value(value)
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def domain_sha256(domain: str, value: Any) -> str:
    require(domain in DOMAIN_PREFIXES, "E_DOMAIN", domain)
    return hashlib.sha256(DOMAIN_PREFIXES[domain] + canonical_bytes(value)).hexdigest()


def checked_path(relative: str) -> Path:
    require(
        type(relative) is str
        and relative
        and not relative.startswith("/")
        and "\\" not in relative
        and "\x00" not in relative
        and all(part not in ("", ".", "..") for part in relative.split("/")),
        "E_PATH",
        repr(relative),
    )
    candidate = ROOT.joinpath(*relative.split("/"))
    metadata = candidate.lstat()
    require(stat.S_ISREG(metadata.st_mode), "E_PATH_TYPE", relative)
    require(not candidate.is_symlink(), "E_PATH_SYMLINK", relative)
    require(metadata.st_size <= MAX_ARTIFACT_BYTES, "E_PATH_SIZE", relative)
    resolved = candidate.resolve(strict=True)
    root = ROOT.resolve(strict=True)
    require(resolved == root or root in resolved.parents, "E_PATH_ESCAPE", relative)
    return candidate


def read_bytes(relative: str) -> bytes:
    return checked_path(relative).read_bytes()


def read_text(relative: str) -> str:
    raw = read_bytes(relative)
    require(not raw.startswith(b"\xef\xbb\xbf"), "E_BOM", relative)
    try:
        return raw.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise CheckError(f"E_UTF8: {relative}") from error


def raw_sha256(relative: str) -> str:
    return hashlib.sha256(read_bytes(relative)).hexdigest()


def duplicate_safe_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(type(key) is str and key not in result, "E_JSON_DUPLICATE", repr(key))
        result[key] = value
    return result


def bounded_integer(token: str) -> int:
    value = int(token, 10)
    require(-(2**63) <= value <= 2**63 - 1, "E_JSON_INT", token)
    return value


def reject_float(token: str) -> NoReturn:
    raise CheckError(f"E_JSON_FLOAT: {token}")


def reject_constant(token: str) -> NoReturn:
    raise CheckError(f"E_JSON_CONSTANT: {token}")


def parse_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    require(type(raw) is bytes, "E_JSON_RAW_TYPE", label)
    require(0 < len(raw) <= MAX_ARTIFACT_BYTES, "E_JSON_SIZE", label)
    require(not raw.startswith(b"\xef\xbb\xbf"), "E_JSON_BOM", label)
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise CheckError(f"E_UTF8: {label}") from error
    decoder = json.JSONDecoder(
        object_pairs_hook=duplicate_safe_object,
        parse_int=bounded_integer,
        parse_float=reject_float,
        parse_constant=reject_constant,
        strict=True,
    )
    try:
        value, end = decoder.raw_decode(text)
    except (json.JSONDecodeError, RecursionError) as error:
        raise CheckError(f"E_JSON_PARSE: {label}: {error}") from error
    require(not text[end:].strip(), "E_JSON_TRAILING", label)
    require(type(value) is dict, "E_JSON_ROOT", label)
    validate_json_value(value)
    return value


def read_json(relative: str) -> dict[str, Any]:
    return parse_json_bytes(read_bytes(relative), relative)


def expected_section_hashes(record: Mapping[str, Any]) -> dict[str, str]:
    return {
        f"{section}_sha256": domain_sha256(section, record[section])
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
    require(raw_sha256(DECISION_REL) == DECISION_RAW_SHA256, "E_DECISION_RAW", DECISION_REL)
    require(raw_sha256(EXPECTED_REL) == EXPECTED_RAW_SHA256, "E_EXPECTED_RAW", EXPECTED_REL)


def verify_predecessor(record: Mapping[str, Any]) -> None:
    require(len(PREDECESSOR_RAW_SHA256) == 8, "E_T07_COUNT", "eight artifacts")
    for relative, expected_hash in PREDECESSOR_RAW_SHA256.items():
        require(raw_sha256(relative) == expected_hash, "E_T07_RAW", relative)
    predecessor = record["predecessor"]
    require(
        exact_equal(predecessor["artifact_raw_sha256"], PREDECESSOR_RAW_SHA256),
        "E_T07_ARTIFACT_BINDING",
        "artifact map",
    )
    require(
        predecessor["integration_commit"]
        == "4bcecaefad5f8a4173e9cc8e0ea8460897badbc3"
        and predecessor["integration_tree"]
        == "739de5525eb6b6d3d535f926f33f8fd9ac14e921"
        and predecessor["integration_parents"]
        == [
            "084eb71dd9c95fbc6285041b1503327705f9a6a1",
            "9a78dbc00705bacf42b629147753f48603d431bc",
        ]
        and predecessor["source_commit"]
        == "9a78dbc00705bacf42b629147753f48603d431bc"
        and predecessor["source_tree"]
        == "739de5525eb6b6d3d535f926f33f8fd9ac14e921"
        and predecessor["source_parent"]
        == "084eb71dd9c95fbc6285041b1503327705f9a6a1",
        "E_T07_TOPOLOGY",
        "source/integration lineage",
    )
    require(
        predecessor["authorization_consumption_state"] == "CONSUMED_SCOPE_COMPLETE"
        and predecessor["implementation_authority_single_use_consumed"] is True
        and predecessor["track_profile_binding_isolated_lab_component_implemented"]
        is True
        and predecessor["local_t07_specification_exercised"] is True
        and predecessor["local_t08_specification_exercised"] is False
        and predecessor["fast_stdout_line_count"] == 93
        and predecessor["fast_stdout_sha256"]
        == "5be17dca5300e396d4d092fe15a9b7d5141ee97a25d150df87413bbabe9aa676"
        and predecessor["full_stdout_line_count"] == 94
        and predecessor["full_stdout_sha256"]
        == "12a8a1f2f975bbdf83b66c925500e43abc5917c5ec65b237ede02e93fa220c31",
        "E_T07_RELEASE_STATE",
        "released consumed predecessor",
    )
    require(
        predecessor["receipt_content_sha256"] == PREDECESSOR_RECEIPT_CONTENT_SHA256
        and predecessor["t07_per_track_receipt_content_sha256"] == T07_TRACK_RECEIPTS,
        "E_T07_RECEIPTS",
        "pack/per-track receipts",
    )
    lines = read_text(PREDECESSOR_EXPECTED_REL).splitlines()
    require(len(lines) == 48, "E_T07_EXPECTED_LINES", str(len(lines)))
    require(
        lines[39] == "receipt_set_sha256\t" + PREDECESSOR_RECEIPT_CONTENT_SHA256,
        "E_T07_EXPECTED_CONTENT",
        "last receipt line",
    )
    fixture = read_json(PREDECESSOR_FIXTURE_REL)
    receipts = fixture["expected_receipts"]
    require(type(receipts) is list and len(receipts) == 2, "E_T07_FIXTURE", "receipts")
    require(
        {item["track_id"]: item["content_sha256"] for item in receipts}
        == T07_TRACK_RECEIPTS,
        "E_T07_TRACK_RECEIPTS",
        "fixture receipts",
    )
    manifest = read_json(PREDECESSOR_MANIFEST_REL)
    require(
        manifest["next_unit"]
        == "UNAUTHORIZED_PENDING_SEPARATE_OWNER_RESOURCE_DECISION_FOR_T08_END_TO_END_SUBJECT_BINDING"
        and manifest["next_unit_authorized_by_this_pack"] is False
        and manifest["state"][
            "implementation_authority_consumed_only_by_exact_integrated_full_gate"
        ]
        is True
        and manifest["state"][
            "implementation_authority_single_use_consumed_before_integrated_full_gate"
        ]
        is False
        and manifest["boundary"][
            "local_t07_specification_exercised_after_integrated_full_gate"
        ]
        is True
        and manifest["boundary"]["local_t08_specification_exercised"] is False
        and manifest["boundary"]["local_t09_specification_exercised"] is False
        and manifest["expected"]["managed_receipt_content_sha256"]
        == T07_TRACK_RECEIPTS["MANAGED_SPANNER_CLOUD_KMS"]
        and manifest["expected"]["self_hosted_receipt_content_sha256"]
        == T07_TRACK_RECEIPTS["SELF_HOSTED_ETCD_OPENBAO"],
        "E_T07_MANIFEST",
        "release successor boundary",
    )


def verify_t08_specification(record: Mapping[str, Any]) -> None:
    require(raw_sha256(T08_SPEC_REL) == T08_SPEC_RAW_SHA256, "E_T08_RAW", T08_SPEC_REL)
    predecessor = record["predecessor"]
    require(
        predecessor["t08_semantic_specification_path"] == T08_SPEC_REL
        and predecessor["t08_semantic_specification_raw_sha256"]
        == T08_SPEC_RAW_SHA256,
        "E_T08_BINDING",
        "record path/hash",
    )
    specification = read_json(T08_SPEC_REL)
    controls = [
        row
        for row in specification["production_ingestion_controls"]
        if row.get("control_id") == "TRACK_SUBJECT_BINDING"
    ]
    threats = {
        row["case_id"]: row
        for row in specification["threat_cases"]
        if row.get("case_id") in {"T07", "T08", "T09"}
    }
    require(len(controls) == 1 and set(threats) == {"T07", "T08", "T09"}, "E_T08_ROWS", "exact rows")
    control = controls[0]
    require(
        control["mandatory_check"]
        == (
            "Bind prerequisite, provider or lab profile, namespace, build, "
            "configuration, subject, and non-substitutable track."
        )
        and control["primary_failure_code"]
        == "E_PRODUCTION_TRACK_SUBJECT_BINDING_FAILED"
        and control["implemented"] is False
        and control["runtime_exercised"] is False
        and control["satisfiable_by_offline"] is False,
        "E_T08_CONTROL",
        "production control remains unsatisfied",
    )
    require(
        threats["T07"]
        == {
            "case_id": "T07",
            "expected_disposition": "REJECTED_FAIL_CLOSED",
            "expected_reason_code": "E_PRODUCTION_TRACK_SUBJECT_BINDING_FAILED",
            "mutation": (
                "Managed and self-hosted packet, profile, namespace, or "
                "configuration substitution"
            ),
            "threat_class": "TRACK_ISOLATION",
        }
        and threats["T08"]["mutation"]
        == "Prerequisite, source, build, session, channel, schedule, row set, or subject mismatch"
        and threats["T08"]["threat_class"] == "SUBJECT_BINDING"
        and threats["T08"]["expected_reason_code"]
        == "E_PRODUCTION_TRACK_SUBJECT_BINDING_FAILED"
        and threats["T09"]["threat_class"] == "CONTENT_IDENTITY"
        and threats["T09"]["expected_reason_code"] == "E_PRODUCTION_CUSTODY_FAILED",
        "E_T07_T08_SPLIT",
        "T07 profile substitution and T08 subject mismatch remain separate",
    )


def validate_semantics(record: Mapping[str, Any]) -> None:
    exact_keys(record, TOP_LEVEL_KEYS, "E_RECORD_KEYS")
    require(
        record["schema"] == RECORD_SCHEMA
        and type(record["schema_version"]) is int
        and record["schema_version"] == 1
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
    decision_without_hashes = {
        key: copy.deepcopy(value)
        for key, value in record.items()
        if key != "section_sha256"
    }
    require(
        domain_sha256("decision_record", decision_without_hashes)
        == DECISION_DOMAIN_SHA256,
        "E_DECISION_DOMAIN_HASH",
        "decision",
    )

    component = record["authorized_component_contract"]
    model = component["binding_model"]
    require(
        model["binding_profile_count"] == 2
        and model["binding_profiles"] == list(EXPECTED_PROFILES)
        and model["profile_order"] == list(EXPECTED_TRACKS)
        and model["request_field_count"] == 8
        and model["request_fields"] == list(REQUEST_FIELDS)
        and model["policy_match_dimension_count"] == 10
        and model["policy_match_fields"] == list(POLICY_MATCH_FIELDS)
        and model["matching_profile"] == "EXACT_ALL_FIELDS_ASCII_BYTE_EQUAL"
        and model["default_disposition"] == "REJECTED_FAIL_CLOSED"
        and model["reject_on_zero_matches"] is True
        and model["reject_on_multiple_matches"] is True
        and model["wildcards_allowed"] is False
        and model["prefix_match_allowed"] is False
        and model["hierarchical_match_allowed"] is False
        and model["group_or_role_inheritance_allowed"] is False,
        "E_BINDING_MODEL",
        "exact two-profile default-reject registry",
    )
    for index, profile in enumerate(model["binding_profiles"]):
        require(set(profile) == set(POLICY_MATCH_FIELDS), "E_PROFILE_KEYS", str(index))
        for field, value in profile.items():
            require(
                type(value) is str
                and value
                and value.isascii()
                and len(value.encode("ascii")) <= 256
                and "*" not in value
                and "?" not in value,
                "E_PROFILE_VALUE",
                f"{index}:{field}",
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
            "separately_injected_synthetic_track_profile_binding_policy",
            "detached_track_profile_binding_request",
            "separately_injected_synthetic_end_to_end_subject_binding_policy",
            "detached_end_to_end_subject_binding_request",
            "mode",
        ]
        and topology["review_order"]
        == [
            "MODE_PREOBSERVATION_GUARD",
            "T07_TRACK_PROFILE_BINDING_REVIEW_EXACTLY_ONCE",
            "SEPARATE_END_TO_END_SUBJECT_BINDING_POLICY_REVIEW",
            "DETACHED_END_TO_END_SUBJECT_BINDING_REQUEST_REVIEW_LAST",
            "EXACT_SINGLE_PROFILE_MATCH",
        ]
        and topology["track_identity_source"] == "T07_PREDECESSOR_RECEIPT_ONLY"
        and topology["predecessor_reviewer_call_count_per_success"] == 1
        and topology["caller_supplied_predecessor_receipt_allowed"] is False
        and topology["production_and_unknown_mode_rejected_before_any_input_observation"]
        is True
        and topology["binding_request_observed_after_policy"] is True
        and topology["binding_policy_may_be_sourced_from_frame"] is False
        and topology["binding_policy_may_be_sourced_from_request"] is False
        and topology["frame_reparsed_by_t08_after_t07_success"] is False
        and topology["request_fields_forbidden"] == list(FORBIDDEN_REQUEST_FIELDS),
        "E_INPUT_TOPOLOGY",
        "mode -> T07 once -> policy -> request -> exact match",
    )
    require(
        not set(REQUEST_FIELDS).intersection({"track_id", "t07_receipt_content_sha256"}),
        "E_T08_REQUEST_LEAKAGE",
        "predecessor receipt/track fields in request",
    )
    truth = component["truth_boundary"]
    require(
        truth
        == {
            "build_truth_proved": False,
            "channel_truth_proved": False,
            "prerequisite_truth_proved": False,
            "row_set_truth_proved": False,
            "schedule_truth_proved": False,
            "session_truth_proved": False,
            "source_truth_proved": False,
            "subject_truth_proved": False,
            "t08_end_to_end_subject_binding_implemented": False,
            "t09_content_identity_and_quarantine_custody_implemented": False,
            "t07_receipt_and_track_are_non_substitutable_exact_policy_dimensions": True,
        },
        "E_TRUTH_BOUNDARY",
        "T07/T08/T09 separation",
    )
    require(
        component["local_scope"]["authorized_candidate_surface_component_count"] == 1
        and component["local_scope"]["authorized_candidate_surface_components"]
        == ["END_TO_END_SUBJECT_BINDING_SYNTHETIC_VERIFIER"]
        and component["local_scope"]["authorized_local_threat_specifications"]
        == ["T08"]
        and component["local_scope"]["candidate_surface_components_implemented_by_decision"]
        == 0
        and component["local_scope"]["target_production_control"]
        == "TRACK_SUBJECT_BINDING"
        and component["reviewer_topology"]["minimum_independent_reviewer_lane_count"]
        == 2
        and component["reviewer_topology"]["required_reviewer_lanes"]
        == [
            "CONTRACT_CONFORMANCE_REVIEW",
            "SECURITY_AND_SOURCE_BOUND_GATE_REVIEW",
        ],
        "E_LOCAL_SCOPE",
        "one T08 component/two lanes",
    )

    authority = record["implementation_authority"]
    require(
        authority["allowed_operations"] == list(ALLOWED_OPERATIONS)
        and authority["forbidden_operations"] == list(FORBIDDEN_OPERATIONS)
        and authority["authorized_local_threat_specifications"] == ["T08"]
        and authority["authorized_candidate_surface_component_count"] == 1
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
        "T08-only reversible local authority",
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
        "bounded offline zero-spend resources",
    )
    state = record["state_machine"]
    require(
        state["current_state"] == CURRENT_STATE
        and len(state["states"]) == 5
        and len(state["transitions"]) == 4
        and state["transitions"][2]["event"]
        == "EXACT_AUTHORIZED_T08_SUCCESSOR_INTEGRATED_AND_FULL_GATE_PASSES"
        and state["decision_full_gate_consumes_new_authority"] is False
        and state["global_single_use_proved"] is False
        and state["runtime_authority_state_representable"] is False
        and state["positive_provider_authority_state_representable"] is False,
        "E_STATE",
        "activation does not consume authority",
    )
    boundary = record["boundary"]
    require(
        boundary["authorized_future_local_threat_specifications"] == ["T08"]
        and boundary["current_decision_candidate_surface_components_implemented"] == 0
        and boundary["isolated_lab_predecessor_surface_components_implemented"] == 5
        and boundary["local_predecessor_threat_specifications_covered"] == 7
        and boundary["future_successor_candidate_surface_component_total"] == 6
        and boundary["future_successor_candidate_surface_components_authorized"] == 1
        and boundary["local_t07_specification_exercised"] is True
        and boundary["local_t08_specification_exercised"] is False
        and boundary["local_t09_specification_exercised"] is False
        and boundary["end_to_end_subject_binding_isolated_lab_implementation_authorized"]
        is True
        and boundary["end_to_end_subject_binding_isolated_lab_implemented"] is False
        and boundary["track_subject_binding_production_control_implemented"] is False
        and boundary["production_ingestion_control_count"] == 14
        and boundary["production_ingestion_controls_implemented"] == 0
        and boundary["production_threat_specification_count"] == 20
        and boundary["production_threat_specifications_runtime_exercised"] == 0
        and boundary["runtime_prerequisite_count"] == 16
        and boundary["runtime_prerequisites_satisfied"] == 0
        and boundary["runtime_authority"] is False
        and boundary["provider_authority"] is False,
        "E_BOUNDARY",
        "5/7 predecessor, 6/8 ceiling, zero production",
    )
    require(
        len(record["nonclaims"]) == 71
        and all(value is False for value in record["nonclaims"].values())
        and record["nonclaims"]["subject_truth_proved"] is False
        and record["nonclaims"]["t08_end_to_end_subject_binding_implemented"] is False
        and record["nonclaims"]["track_id_accepted_from_detached_t08_request"] is False
        and record["nonclaims"]["track_id_derived_from_raw_frame_by_t08"] is False,
        "E_NONCLAIMS",
        "71 explicit false claims",
    )
    provenance = record["decision_provenance"]
    actor = record["owner_implementation_actor"]
    require(
        provenance["directive_observed_in_owner_session"] is True
        and provenance["directive_semantics"]
        == "CONTINUE_NEXT_BOUNDED_T08_END_TO_END_SUBJECT_BINDING_DECISION_UNIT"
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
    verify_predecessor(record)
    verify_t08_specification(record)


def validate_record(record: dict[str, Any], expected: Mapping[str, Any]) -> None:
    validate_json_value(record)
    validate_exact_tree(record, expected)
    validate_semantics(record)


def build_expected_receipt(record: Mapping[str, Any]) -> dict[str, Any]:
    model = record["authorized_component_contract"]["binding_model"]
    boundary = record["boundary"]
    authority = record["implementation_authority"]
    actor = record["owner_implementation_actor"]
    resources = record["resource_binding"]
    decision_without_hashes = {
        key: copy.deepcopy(value)
        for key, value in record.items()
        if key != "section_sha256"
    }
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "status": STATUS,
        "decision": DECISION,
        "date": DATE,
        "mode": MODE,
        "next_unit": NEXT_UNIT,
        "current_state": CURRENT_STATE,
        "authorization_effective_only_after_integrated_full_gate": boundary[
            "effective_only_after_integrated_full_gate"
        ],
        "implementation_authority_recorded": boundary["implementation_authority_recorded"],
        "implementation_scope_decision_recorded": boundary[
            "implementation_scope_decision_recorded"
        ],
        "implementation_resource_binding_recorded": boundary[
            "implementation_resource_binding_recorded"
        ],
        "implementation_authority_single_use_consumed": False,
        "predecessor_authorization_consumption_state": record["predecessor"][
            "authorization_consumption_state"
        ],
        "predecessor_implementation_authority_single_use_consumed": record[
            "predecessor"
        ]["implementation_authority_single_use_consumed"],
        "authorized_candidate_surface_component_count": authority[
            "authorized_candidate_surface_component_count"
        ],
        "authorized_local_threat_specification_count": len(
            authority["authorized_local_threat_specifications"]
        ),
        "authorized_local_threat_specifications": ",".join(
            authority["authorized_local_threat_specifications"]
        ),
        "binding_profile_count": model["binding_profile_count"],
        "binding_request_field_count": model["request_field_count"],
        "binding_policy_match_dimension_count": model["policy_match_dimension_count"],
        "default_disposition": model["default_disposition"],
        "wildcards_allowed": model["wildcards_allowed"],
        "public_input_count": resources["component_limits"]["public_input_count"],
        "track_profile_binding_implemented": boundary[
            "track_profile_binding_isolated_lab_implemented"
        ],
        "end_to_end_subject_binding_implemented": boundary[
            "end_to_end_subject_binding_isolated_lab_implemented"
        ],
        "track_subject_binding_production_control_implemented": boundary[
            "track_subject_binding_production_control_implemented"
        ],
        "local_t07_specification_exercised": boundary["local_t07_specification_exercised"],
        "local_t08_specification_exercised": boundary["local_t08_specification_exercised"],
        "future_successor_candidate_surface_component_total": boundary[
            "future_successor_candidate_surface_component_total"
        ],
        "future_successor_candidate_surface_components_authorized": boundary[
            "future_successor_candidate_surface_components_authorized"
        ],
        "current_decision_candidate_surface_components_implemented": boundary[
            "current_decision_candidate_surface_components_implemented"
        ],
        "isolated_lab_predecessor_surface_components_implemented": boundary[
            "isolated_lab_predecessor_surface_components_implemented"
        ],
        "local_predecessor_threat_specifications_covered": boundary[
            "local_predecessor_threat_specifications_covered"
        ],
        "future_successor_minimum_independent_reviewer_lane_count": boundary[
            "future_successor_minimum_independent_reviewer_lane_count"
        ],
        "production_security_reviewer_bound": boundary[
            "production_security_reviewer_bound"
        ],
        "owner_semantic_actor_label": actor["semantic_actor_label"],
        "owner_semantic_actor_binding_recorded": actor["semantic_actor_binding_recorded"],
        "owner_cryptographic_identity_verified": actor["cryptographic_identity_verified"],
        "owner_signature_observed": actor["signature_observed"],
        "owner_supplied_numeric_budget_cap": record["decision_provenance"][
            "owner_supplied_numeric_budget_cap"
        ],
        "external_paid_spend_cap": resources["effective_external_paid_spend_cap"],
        "allowed_operation_count": len(authority["allowed_operations"]),
        "forbidden_operation_count": len(authority["forbidden_operations"]),
        "provider_endpoint_count": len(resources["provider_endpoints"]),
        "component_runtime_network": resources["component_runtime_network"],
        "global_single_use_proved": record["state_machine"]["global_single_use_proved"],
        "production_environment_implementation_authorized": authority[
            "production_environment_implementation_authorized"
        ],
        "production_ingestion_implemented": boundary["production_ingestion_implemented"],
        "production_ingestion_enabled": boundary["production_ingestion_enabled"],
        "production_ingestion_controls_implemented": boundary[
            "production_ingestion_controls_implemented"
        ],
        "production_ingestion_controls_runtime_exercised": boundary[
            "production_ingestion_controls_runtime_exercised"
        ],
        "real_evidence_items_present": boundary["real_evidence_items_present"],
        "production_validated_evidence_items": boundary[
            "production_validated_evidence_items"
        ],
        "runtime_evidence_accepted": boundary["runtime_evidence_accepted"],
        "runtime_prerequisites_satisfied": boundary["runtime_prerequisites_satisfied"],
        "runtime_owner_identity_bound": boundary["runtime_owner_identity_bound"],
        "runtime_owner_decision_recorded": boundary["runtime_owner_decision_recorded"],
        "runtime_admission_ready": boundary["runtime_admission_ready"],
        "runtime_admission_granted": boundary["runtime_admission_granted"],
        "runtime_authority": boundary["runtime_authority"],
        "provider_authority": boundary["provider_authority"],
        "downstream_gates_authorized": boundary["downstream_gates_authorized"],
        "runtime_side_effects_unlocked": boundary["runtime_side_effects_unlocked"],
        "implementation_side_effects_unlocked": boundary[
            "implementation_side_effects_unlocked"
        ],
        "nonclaim_field_count": len(record["nonclaims"]),
        "all_nonclaims_explicit": all(
            value is False for value in record["nonclaims"].values()
        ),
        "authorized_component_contract_sha256": record["section_sha256"][
            "authorized_component_contract_sha256"
        ],
        "implementation_authority_sha256": record["section_sha256"][
            "implementation_authority_sha256"
        ],
        "resource_binding_sha256": record["section_sha256"]["resource_binding_sha256"],
        "state_machine_sha256": record["section_sha256"]["state_machine_sha256"],
        "rollback_sha256": record["section_sha256"]["rollback_sha256"],
        "boundary_sha256": record["section_sha256"]["boundary_sha256"],
        "nonclaims_sha256": record["section_sha256"]["nonclaims_sha256"],
        "decision_record_sha256": domain_sha256(
            "decision_record", decision_without_hashes
        ),
        "predecessor_integration_commit": record["predecessor"]["integration_commit"],
        "predecessor_receipt_content_sha256": record["predecessor"][
            "receipt_content_sha256"
        ],
        "t08_semantic_specification_raw_sha256": record["predecessor"][
            "t08_semantic_specification_raw_sha256"
        ],
    }
    exact_keys(receipt, TSV_FIELDS[:-1], "E_RECEIPT_BUILD_KEYS")
    receipt["content_sha256"] = domain_sha256("receipt_content", receipt)
    return receipt


def parse_expected_receipt() -> dict[str, Any]:
    lines = read_text(EXPECTED_REL).splitlines()
    require(len(lines) == len(TSV_FIELDS) == 78, "E_TSV_LINES", str(len(lines)))
    receipt: dict[str, Any] = {}
    for index, line in enumerate(lines):
        parts = line.split("\t")
        require(len(parts) == 2, "E_TSV_COLUMNS", str(index))
        field, rendered = parts
        require(field == TSV_FIELDS[index] and field not in receipt, "E_TSV_FIELD", field)
        if field in INTEGER_RECEIPT_FIELDS:
            value = int(rendered, 10)
            require(type(value) is int and rendered == str(value), "E_TSV_INTEGER", field)
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
        require(
            "\t" not in rendered and "\n" not in rendered and "\r" not in rendered,
            "E_TSV_CONTROL",
            field,
        )
        lines.append(f"{field}\t{rendered}")
    return "\n".join(lines) + "\n"


def validate_receipt(receipt: dict[str, Any], record: Mapping[str, Any]) -> str:
    expected = build_expected_receipt(record)
    validate_exact_tree(receipt, expected, "receipt")
    validate_exact_tree(receipt, parse_expected_receipt(), "expected_tsv")
    require(
        receipt["schema"] == RECEIPT_SCHEMA
        and receipt["decision_record_sha256"] == DECISION_DOMAIN_SHA256
        and receipt["content_sha256"] == RECEIPT_CONTENT_SHA256
        and receipt["allowed_operation_count"] == len(ALLOWED_OPERATIONS)
        and receipt["forbidden_operation_count"] == len(FORBIDDEN_OPERATIONS)
        and receipt["nonclaim_field_count"] == 71
        and receipt["binding_profile_count"] == 2
        and receipt["binding_request_field_count"] == 8
        and receipt["binding_policy_match_dimension_count"] == 10
        and receipt["public_input_count"] == 10,
        "E_RECEIPT_BINDING",
        "identity/counts",
    )
    unsigned = dict(receipt)
    del unsigned["content_sha256"]
    require(
        domain_sha256("receipt_content", unsigned) == RECEIPT_CONTENT_SHA256,
        "E_RECEIPT_CONTENT",
        "domain hash",
    )
    rendered = render_tsv(receipt)
    require(rendered == read_text(EXPECTED_REL), "E_RECEIPT_TSV", "exact bytes")
    return rendered


def load_source() -> ModuleType:
    path = checked_path(SOURCE_REL).resolve()
    name = "_t08_end_to_end_subject_binding_authority_source_under_review"
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
    observed_imports: set[str] = set()
    forbidden_names = {"__import__", "compile", "eval", "exec", "input", "open"}
    forbidden_attributes = {
        "chdir", "connect", "environ", "fork", "getenv", "import_module",
        "listdir", "mkdir", "now", "open", "Popen", "putenv", "randbytes",
        "read", "read_bytes", "read_text", "recv", "remove", "rename",
        "replace", "request", "rmdir", "run", "send", "sleep", "socket",
        "spawn", "system", "time", "today", "token_bytes", "token_hex",
        "unlink", "urandom", "urlopen", "utcnow", "walk", "write",
        "write_bytes", "write_text",
    }
    public_functions: set[str] = set()
    review_nodes: list[ast.FunctionDef] = []
    classes: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                observed_imports.add(root)
                require(root in allowed_imports, "E_AST_IMPORT", alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            observed_imports.add(root)
            require(node.level == 0 and root in allowed_imports, "E_AST_IMPORT", module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in forbidden_names, "E_AST_CALL", node.func.id)
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
            classes.append(node.name)
    require(observed_imports == allowed_imports, "E_AST_IMPORT_SET", repr(observed_imports))
    require(
        public_functions
        == {
            "build_owner_decision_record", "canonical_bytes", "domain_sha256",
            "exact_equal", "exact_keys", "expected_section_hashes", "render_tsv",
            "require", "review_decision",
        },
        "E_AST_PUBLIC",
        repr(sorted(public_functions)),
    )
    require(classes == [], "E_AST_CLASS", repr(classes))
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
    except (
        CheckError, ValueError, TypeError, KeyError, IndexError, OSError,
        SyntaxError, UnicodeError, RecursionError,
    ):
        return
    raise CheckError(f"E_MUTATION_ACCEPTED: {label}")


def mutate_scalar(value: Any) -> Any:
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is str:
        if len(value) == 64 and all(character in "0123456789abcdef" for character in value):
            return "0" * 64 if value != "0" * 64 else "1" * 64
        return value + "_MUTATED"
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


def check_json_guards() -> int:
    probes = [
        b'{"a":1,"a":2}', b'{"v":NaN}', b'{"v":Infinity}',
        b'{"v":-Infinity}', b'{"v":9223372036854775808}',
        b'{"v":-9223372036854775809}', b'{"v":1.5}',
        b'\xef\xbb\xbf{"v":1}', b'{"v":1}{}',
        json.dumps({"v": list(range(65))}, separators=(",", ":")).encode(),
    ]
    nested: Any = "leaf"
    for _ in range(34):
        nested = {"n": nested}
    probes.append(json.dumps(nested, separators=(",", ":")).encode())
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
        "profile_boundary_negatives": 0,
        "overclaim_negatives": 0,
        "section_hash_negatives": 0,
        "receipt_negatives": 0,
        "source_ast_negatives": 0,
    }
    source_text = read_text(SOURCE_REL)
    snippets = (
        "\nimport os\n", "\nimport socket\n", "\nfrom pathlib import Path\n",
        "\ndef public_extra():\n    pass\n",
        "\ndef _open_probe():\n    return open('x')\n",
        "\ndef _import_probe():\n    return __import__('os')\n",
        "\ndef _global_probe():\n    global MUTABLE\n",
        "\nasync def _async_probe():\n    pass\n",
        "\ndef _read_probe():\n    return value.read_text()\n",
        "\ndef review_decision(extra):\n    pass\n",
        "\n_DUPLICATE_LITERAL = {'x': 1, 'x': 2}\n",
        "\ndef _time_probe():\n    return value.utcnow()\n",
        "\nclass Extra: pass\n",
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
        path for path in leaf_paths(record) if path and path[0] != "section_sha256"
    ]
    counts["grounding_matrix_negatives"] = exercise_paths(
        grounding_paths, "grounding", record, expected, module
    )

    directed: list[dict[str, Any]] = []
    model_path = ("authorized_component_contract", "binding_model")
    topology_path = ("authorized_component_contract", "input_topology")
    truth_path = ("authorized_component_contract", "truth_boundary")

    def add(path: tuple[Any, ...], replacement: Any) -> None:
        candidate = copy.deepcopy(record)
        set_path(candidate, path, replacement)
        rehash_record(candidate)
        directed.append(candidate)

    for field in REQUEST_FIELDS:
        add(model_path + ("request_fields",), [item for item in REQUEST_FIELDS if item != field])
    for leaked in (
        "track_id", "t07_receipt_content_sha256", "configuration_sha256",
        "packet_profile_id", "frame_sha256",
    ):
        add(model_path + ("request_fields",), list(REQUEST_FIELDS) + [leaked])
        add(model_path + ("policy_match_fields",), list(POLICY_MATCH_FIELDS) + [leaked])
    for field in ("track_id", "t07_receipt_content_sha256", "configuration_sha256"):
        add(
            topology_path + ("request_fields_forbidden",),
            [item for item in FORBIDDEN_REQUEST_FIELDS if item != field],
        )
    add(topology_path + ("frame_reparsed_by_t08_after_t07_success",), True)
    add(topology_path + ("track_identity_source",), "RAW_FRAME_OR_REQUEST")
    add(topology_path + ("predecessor_reviewer_call_count_per_success",), 2)
    add(truth_path + ("subject_truth_proved",), True)
    add(truth_path + ("prerequisite_truth_proved",), True)
    add(truth_path + ("build_truth_proved",), True)
    add(truth_path + ("t08_end_to_end_subject_binding_implemented",), True)
    for flag in (
        "wildcards_allowed", "prefix_match_allowed", "hierarchical_match_allowed",
        "group_or_role_inheritance_allowed",
    ):
        add(model_path + (flag,), True)
    add(model_path + ("reject_on_zero_matches",), False)
    add(model_path + ("reject_on_multiple_matches",), False)
    add(
        model_path + ("binding_profiles", 1),
        copy.deepcopy(record["authorized_component_contract"]["binding_model"]["binding_profiles"][0]),
    )
    add(
        model_path + ("binding_profiles", 0, "t07_receipt_content_sha256"),
        T07_TRACK_RECEIPTS["SELF_HOSTED_ETCD_OPENBAO"],
    )
    add(
        model_path + ("binding_profiles", 0, "track_id"),
        "SELF_HOSTED_ETCD_OPENBAO",
    )
    for index, candidate in enumerate(directed):
        reject_record_both(candidate, expected, module, f"profile-boundary:{index}")
        counts["profile_boundary_negatives"] += 1

    sentinel_strings = {
        "NONE", "NOT_APPLICABLE_NOT_ENABLED",
        "FIXED_KAT_LABELS_ONLY_NOT_TRUSTED_TIME",
    }
    overclaim_paths: list[tuple[Any, ...]] = []
    for section in HASHED_SECTIONS:
        for suffix in leaf_paths(record[section]):
            path = (section,) + suffix
            value = get_path(record, path)
            if (
                value is False
                or (type(value) is int and value == 0)
                or (type(value) is list and not value)
                or value in sentinel_strings
            ):
                overclaim_paths.append(path)
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
            candidate["content_sha256"] = domain_sha256("receipt_content", unsigned)
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
        "profile_boundary_negative_tests": counts["profile_boundary_negatives"],
        "receipt_negative_tests": counts["receipt_negatives"],
        "section_hash_negative_tests": counts["section_hash_negatives"],
        "source_ast_negative_tests": counts["source_ast_negatives"],
        "source_ast_purity": "PASS",
        "t08_semantic_specification_hashes_frozen": 1,
    }


def file_mode(relative: str) -> str:
    mode = checked_path(relative).stat().st_mode
    return "100755" if mode & 0o111 else "100644"


def verify_manifest(
    record: Mapping[str, Any],
    receipt: Mapping[str, Any],
    counts: Mapping[str, int],
) -> None:
    manifest = read_json(MANIFEST_REL)
    exact_keys(
        manifest,
        {
            "authorized_component_summary", "boundary", "date", "decision",
            "evidence_sha256", "logical_baseline_commit", "logical_baseline_parents",
            "logical_baseline_tree", "next_unit", "owner_semantics", "packet",
            "predecessor", "resource_binding", "results", "schema", "status",
            "t08_semantic_specification", "test_oracle",
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
        == "4bcecaefad5f8a4173e9cc8e0ea8460897badbc3"
        and manifest["logical_baseline_tree"]
        == "739de5525eb6b6d3d535f926f33f8fd9ac14e921"
        and manifest["logical_baseline_parents"]
        == [
            "084eb71dd9c95fbc6285041b1503327705f9a6a1",
            "9a78dbc00705bacf42b629147753f48603d431bc",
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
        "source/checker/owner/expected hashes",
    )
    packet = manifest["packet"]
    exact_keys(packet, {"all_add_required", "modes", "path_count", "paths"}, "E_PACKET_KEYS")
    require(
        packet["all_add_required"] is True
        and packet["path_count"] == 7
        and packet["paths"] == list(PACK_PATHS)
        and packet["modes"] == PACK_MODES
        and {relative: file_mode(relative) for relative in PACK_PATHS} == PACK_MODES,
        "E_PACKET",
        "exact seven add-only paths/modes",
    )
    require(manifest["test_oracle"] == manifest_oracle(counts), "E_MANIFEST_ORACLE", "counts")
    require(
        exact_equal(manifest["predecessor"], record["predecessor"]),
        "E_MANIFEST_PREDECESSOR",
        "exact T07 predecessor",
    )

    model = record["authorized_component_contract"]["binding_model"]
    summary = manifest["authorized_component_summary"]
    require(
        summary
        == {
            "authorized_candidate_surface_component_count": 1,
            "authorized_candidate_surface_components": [
                "END_TO_END_SUBJECT_BINDING_SYNTHETIC_VERIFIER"
            ],
            "authorized_component_contract_sha256": FROZEN_SECTION_HASHES[
                "authorized_component_contract_sha256"
            ],
            "authorized_local_threat_specification_count": 1,
            "authorized_local_threat_specifications": ["T08"],
            "binding_policy_match_dimension_count": 10,
            "binding_policy_match_fields": list(POLICY_MATCH_FIELDS),
            "binding_profile_count": 2,
            "binding_profiles": list(EXPECTED_TRACKS),
            "binding_request_field_count": 8,
            "binding_request_fields": list(REQUEST_FIELDS),
            "current_decision_candidate_surface_components_implemented": 0,
            "default_disposition": "REJECTED_FAIL_CLOSED",
            "future_successor_minimum_independent_reviewer_lane_count": 2,
            "required_reviewer_lanes": [
                "CONTRACT_CONFORMANCE_REVIEW",
                "SECURITY_AND_SOURCE_BOUND_GATE_REVIEW",
            ],
            "track_profile_binding_implemented": True,
            "target_production_control": "TRACK_SUBJECT_BINDING",
            "end_to_end_subject_binding_implemented": False,
            "wildcards_allowed": False,
        }
        and summary["binding_profile_count"] == model["binding_profile_count"],
        "E_MANIFEST_SUMMARY",
        "T08 component summary",
    )
    boundary = manifest["boundary"]
    require(
        boundary
        == {
            "authorization_effective_only_after_integrated_full_gate": True,
            "decision_full_gate_consumes_new_authority": False,
            "downstream_gate_count": 4,
            "downstream_gates_authorized": 0,
            "future_successor_candidate_surface_component_total": 6,
            "implementation_authority_single_use_consumed": False,
            "isolated_lab_predecessor_surface_components_implemented": 5,
            "local_predecessor_threat_specifications_covered": 7,
            "local_t07_specification_exercised": True,
            "local_t08_specification_exercised": False,
            "local_t09_specification_exercised": False,
            "predecessor_implementation_authority_consumed": True,
            "production_environment_implementation_authorized": False,
            "production_ingestion_control_count": 14,
            "production_ingestion_controls_implemented": 0,
            "production_ingestion_controls_runtime_exercised": 0,
            "production_ingestion_enabled": False,
            "production_ingestion_implemented": False,
            "production_security_reviewer_bound": False,
            "production_threat_specification_count": 20,
            "production_threat_specifications_runtime_exercised": 0,
            "production_validated_evidence_items": 0,
            "provider_authority": False,
            "real_evidence_items_present": 0,
            "runtime_admission_granted": False,
            "runtime_admission_ready": False,
            "runtime_authority": False,
            "runtime_evidence_accepted": 0,
            "runtime_owner_decision_recorded": False,
            "runtime_owner_identity_bound": False,
            "runtime_prerequisite_count": 16,
            "runtime_prerequisites_satisfied": 0,
            "runtime_side_effects_unlocked": "NONE",
            "end_to_end_subject_binding_isolated_lab_implementation_authorized": True,
            "end_to_end_subject_binding_isolated_lab_implemented": False,
            "track_subject_binding_production_control_implemented": False,
        },
        "E_MANIFEST_BOUNDARY",
        "zero production/T08/T09",
    )
    limits = record["resource_binding"]["component_limits"]
    require(
        manifest["resource_binding"]
        == {
            "allowed_resource_classes": record["resource_binding"]["allowed_resource_classes"],
            "component_runtime_network": False,
            "credential_handle_count": 0,
            "credential_path_count": 0,
            "currency_scope": "ALL_CURRENCIES_ZERO_ONLY",
            "effective_external_paid_spend_cap": 0,
            "max_authentication_bundle_bytes": limits["max_authentication_bundle_bytes"],
            "max_authorization_policy_bytes": limits["max_authorization_policy_bytes"],
            "max_authorization_request_bytes": limits["max_authorization_request_bytes"],
            "max_input_frame_bytes": limits["max_input_frame_bytes"],
            "max_parallel_workers": limits["max_parallel_workers"],
            "max_private_scratch_bytes": limits["max_private_scratch_bytes"],
            "max_end_to_end_subject_binding_entries": limits[
                "max_end_to_end_subject_binding_entries"
            ],
            "max_end_to_end_subject_binding_policy_bytes": limits[
                "max_end_to_end_subject_binding_policy_bytes"
            ],
            "max_end_to_end_subject_binding_request_bytes": limits[
                "max_end_to_end_subject_binding_request_bytes"
            ],
            "max_trust_policy_bytes": limits["max_trust_policy_bytes"],
            "owner_supplied_numeric_budget_cap": False,
            "private_key_or_seed_material_authorized": False,
            "production_resource_authority_bound": False,
            "provider_endpoint_count": 0,
            "public_input_count": 10,
            "signing_or_key_generation_authorized": False,
            "test_data_scope": (
                "COMMITTED_NONSECRET_PUBLIC_ONLY_SYNTHETIC_KAT_NO_SEEDS_NO_PRIVATE_KEYS"
            ),
        },
        "E_MANIFEST_RESOURCES",
        "bounded zero-spend resources",
    )
    require(
        manifest["owner_semantics"]
        == {
            "binding_basis": "ESTABLISHED_PROFILE_PLUS_CURRENT_SESSION_CONTINUITY",
            "cryptographic_identity_verified": False,
            "directive_observed_in_owner_session": True,
            "directive_semantics": (
                "CONTINUE_NEXT_BOUNDED_T08_END_TO_END_SUBJECT_BINDING_DECISION_UNIT"
            ),
            "implementation_authority_effective_only_after_integrated_full_gate": True,
            "owner_supplied_numeric_budget_cap": False,
            "runtime_owner_decision_recorded": False,
            "runtime_owner_identity_bound": False,
            "semantic_actor_binding_recorded": True,
            "semantic_actor_label": "pallasting",
            "semantic_actor_role": "PROJECT_OWNER",
            "signature_observed": False,
            "source_or_fast_replay_effective_authority": False,
        },
        "E_MANIFEST_OWNER",
        "semantic-only owner",
    )
    require(
        manifest["t08_semantic_specification"]
        == {
            "control_id": "TRACK_SUBJECT_BINDING",
            "mandatory_t08_request_dimensions": [
                "prerequisite", "source", "build", "session", "channel",
                "schedule", "row_set", "subject",
            ],
            "path": T08_SPEC_REL,
            "policy_match_dimension_count": 10,
            "predecessor_binding_dimensions": [
                "t07_receipt_content_sha256", "track_id",
            ],
            "primary_failure_code": "E_PRODUCTION_TRACK_SUBJECT_BINDING_FAILED",
            "raw_sha256": T08_SPEC_RAW_SHA256,
            "satisfiable_by_offline": False,
            "t07_threat_class": "TRACK_ISOLATION",
            "t08_threat_class": "SUBJECT_BINDING",
            "threat_case_id": "T08",
        },
        "E_MANIFEST_T08",
        "T07/T08 semantic split",
    )
    results = manifest["results"]
    require(
        results
        == {
            "all_nonclaims_explicit": True,
            "allowed_operation_count": 8,
            "authorized_component_contract_sha256": FROZEN_SECTION_HASHES[
                "authorized_component_contract_sha256"
            ],
            "binding_policy_match_dimension_count": 10,
            "binding_profile_count": 2,
            "binding_request_field_count": 8,
            "boundary_sha256": FROZEN_SECTION_HASHES["boundary_sha256"],
            "content_sha256": RECEIPT_CONTENT_SHA256,
            "decision_provenance_sha256": FROZEN_SECTION_HASHES[
                "decision_provenance_sha256"
            ],
            "decision_record_sha256": DECISION_DOMAIN_SHA256,
            "forbidden_operation_count": 33,
            "implementation_authority_sha256": FROZEN_SECTION_HASHES[
                "implementation_authority_sha256"
            ],
            "nonclaim_field_count": 71,
            "nonclaims_sha256": FROZEN_SECTION_HASHES["nonclaims_sha256"],
            "owner_implementation_actor_sha256": FROZEN_SECTION_HASHES[
                "owner_implementation_actor_sha256"
            ],
            "resource_binding_sha256": FROZEN_SECTION_HASHES[
                "resource_binding_sha256"
            ],
            "rollback_sha256": FROZEN_SECTION_HASHES["rollback_sha256"],
            "state_count": 5,
            "state_machine_sha256": FROZEN_SECTION_HASHES[
                "state_machine_sha256"
            ],
            "transition_count": 4,
        },
        "E_MANIFEST_RESULTS",
        "receipt/record results",
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
    require(
        module.render_tsv(copy.deepcopy(source_receipt)) == rendered,
        "E_SOURCE_RENDER",
        "TSV",
    )
    if mode == "candidate":
        return rendered
    counts = run_self_test(module, record, expected_record, copy.deepcopy(source_receipt))
    if mode == "normal":
        verify_manifest(record, source_receipt, counts)
        return rendered
    ordered = (
        "directed_negative_tests", "json_guard_negatives",
        "closed_world_negatives", "grounding_matrix_negatives",
        "profile_boundary_negatives", "overclaim_negatives",
        "section_hash_negatives", "receipt_negatives", "source_ast_negatives",
    )
    lines = ["self_test\tPASS"]
    lines.extend(f"{key}\t{counts[key]}" for key in ordered)
    lines.extend(
        (
            "predecessor_artifact_hashes_frozen\t8",
            "predecessor_exact_receipt_lines\t48",
            "t08_request_binding_dimensions\t8",
            "t08_policy_match_dimensions\t10",
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
        CheckError, AssertionError, ValueError, TypeError, KeyError, IndexError,
        OSError, SyntaxError, UnicodeError, RecursionError,
    ) as error:
        print(
            "T08 end-to-end subject-binding authority decision pack check failed: " + str(error),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
