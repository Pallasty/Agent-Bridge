#!/usr/bin/env python3
"""Pure reviewer for the T09 content-identity/custody authority decision.

The reviewed record can authorize one exact reversible repository successor.
It does not implement T09, create durable custody, canonicalize production
payloads, accept evidence, or expose runtime/provider authority. Inputs are
already in memory. This module performs no
filesystem, environment, clock, process, network, credential, randomness,
entropy, signing, key-generation, or mutable-global-state I/O.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping


RECORD_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "content_identity_and_quarantine_custody_isolated_lab_implementation_authority_and_"
    "resource_binding_decision.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "content_identity_and_quarantine_custody_isolated_lab_implementation_authority_and_"
    "resource_binding_decision_v1.receipt.v0"
)
DATE = "2026-07-18"
STATUS = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_"
    "SCOPE_RECORDED_ZERO_EXTERNAL_SPEND_NO_RUNTIME_OR_PROVIDER_AUTHORITY"
)
DECISION = (
    "AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_T09_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_ISOLATED_LAB_"
    "COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED"
)
MODE = "ISOLATED_LAB_FIRST"
CURRENT_STATE = "AUTHORIZED_T09_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_ISOLATED_LAB_EXACT_UNIT"
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_SYNTHETIC_EXACT_T08_RECEIPT_"
    "RAW_FRAME_SHA256_CANONICAL_FRAME_SHA256_PACKET_ID_SHA256_SIGNATURE_"
    "SUBJECT_SHA256_AND_VALIDATION_SUBJECT_SHA256_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
)
IMPLEMENTATION_SIDE_EFFECTS = (
    "REVERSIBLE_LOCAL_CODE_SCHEMA_TEST_DOCS_FOR_EXACT_NEXT_UNIT_ONLY"
)

PREDECESSOR_MANIFEST_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_"
    "track_prerequisite_source_build_session_channel_schedule_row_set_and_"
    "subject_verifier_isolated_lab_v1_pack_v0.json"
)
PREDECESSOR_GATE_PATH = (
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-end-to-end-subject-binding-synthetic-exact-t07-receipt-track-"
    "prerequisite-source-build-session-channel-schedule-row-set-and-subject-"
    "verifier-isolated-lab-v1-pack.sh"
)
T09_SEMANTIC_SPECIFICATION_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_runtime_prerequisite_evidence_packet_offline_integration_"
    "and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
)
PREDECESSOR_ARTIFACT_RAW_SHA256 = {
    (
        "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-"
        "injection-runner-end-to-end-subject-binding-synthetic-exact-t07-"
        "receipt-track-prerequisite-source-build-session-channel-schedule-row-"
        "set-and-subject-verifier-isolated-lab-v1.schema.json"
    ): "40d23b17f45f0c4cec7fa83e76b6edbf3616d3cb70a5466a3a111d33bab0c841",
    (
        "docs/reports/goal-c-u/2026-07-18-biocortex-track-b-reference-provider-"
        "fault-injection-runner-end-to-end-subject-binding-synthetic-exact-t07-"
        "receipt-track-prerequisite-source-build-session-channel-schedule-row-"
        "set-and-subject-verifier-isolated-lab-v1-pack.md"
    ): "0e74e74869826145ef0ccc100793bbb5bc39416398104d68587ba820afa189b9",
    PREDECESSOR_GATE_PATH:
        "c352cd166d0a89efe1568bb45f0c86915e319bb3c9b6d48bcce70e83480a21b1",
    (
        "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_"
        "runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_"
        "prerequisite_source_build_session_channel_schedule_row_set_and_"
        "subject_verifier_isolated_lab_v1.py"
    ): "2752e8b4ca393f5db14d7c980e65a5a71cdbff38a4eb19c861fffe5cc3ffc7f8",
    (
        "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_end_to_end_subject_binding_synthetic_exact_t07_"
        "receipt_track_prerequisite_source_build_session_channel_schedule_row_"
        "set_and_subject_verifier_isolated_lab_v1_pack.py"
    ): "54a37862f166d524791914239299529a746809a3b5b3305f04273cba856b6e10",
    (
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_"
        "track_prerequisite_source_build_session_channel_schedule_row_set_and_"
        "subject_verifier_isolated_lab_v1_pack.expected.v0.tsv"
    ): "f08708c42399e94064b1452cfbccaa287462fc18e236b9daed96217affd5f4a4",
    (
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_"
        "track_prerequisite_source_build_session_channel_schedule_row_set_and_"
        "subject_verifier_isolated_lab_v1_pack_synthetic_v0.json"
    ): "ab966ecef10652730b752f3308326f8fdba9cf61a3b688cfe421efc3788567c6",
    PREDECESSOR_MANIFEST_PATH:
        "efec8f434b3e957d8a2229cecc0172b9da69a14039dede8b94f7e137ae9d24fe",
}
PREDECESSOR = {
    "artifact_raw_sha256": PREDECESSOR_ARTIFACT_RAW_SHA256,
    "authorization_consumption_state": "CONSUMED_SCOPE_COMPLETE",
    "fast_stdout_line_count": 84,
    "fast_stdout_sha256":
        "53a05c12cc1103013cd753ea78a5bda3c3cab8751162494162e36387ffbc90a9",
    "full_stdout_line_count": 84,
    "full_stdout_sha256":
        "4975b65754527caf6c54c0cc2b2a9674e8fd8b8e5c783a9874148c50a43db6f8",
    "gate_path": PREDECESSOR_GATE_PATH,
    "gate_raw_sha256":
        "c352cd166d0a89efe1568bb45f0c86915e319bb3c9b6d48bcce70e83480a21b1",
    "implementation_authority_single_use_consumed": True,
    "integration_commit": "34b2d815b7439b346883bdfdebcd34640533a334",
    "integration_parents": [
        "34b1c7e6ca9c2b75fd2ef3cf418a444353059511",
        "4317400912b703a771eb2ca908a594d27b6e02b8",
    ],
    "integration_tree": "a844741d20b8697fdfc70d1ae98e89e509139173",
    "local_t08_specification_exercised": True,
    "local_t09_specification_exercised": False,
    "manifest_path": PREDECESSOR_MANIFEST_PATH,
    "manifest_raw_sha256":
        "efec8f434b3e957d8a2229cecc0172b9da69a14039dede8b94f7e137ae9d24fe",
    "receipt_content_sha256":
        "70a2d23143296c1370bda820e499df127b73d31c54ad1818faf3c56015a49cbc",
    "end_to_end_subject_binding_isolated_lab_component_implemented": True,
    "source_commit": "4317400912b703a771eb2ca908a594d27b6e02b8",
    "source_parent": "8521ff6a9784a6d74be2b8ee0e02f3aba6b9f8a5",
    "source_tree": "48674e5ff95dc9c3b31d813c42c4bc18290277b3",
    "t08_per_track_receipt_content_sha256": {
        "MANAGED_SPANNER_CLOUD_KMS":
            "7bf4b4151a12428da34eb5a095d340a4b5a1c531381385bf262cb1d5df7415b9",
        "SELF_HOSTED_ETCD_OPENBAO":
            "77e9eadcc83235e9f5b0357e9ca15b046c4044d36e764583b481bc7fb2c29865",
    },
    "t09_semantic_specification_path": T09_SEMANTIC_SPECIFICATION_PATH,
    "t09_semantic_specification_raw_sha256":
        "3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6",
}

DECISION_PROVENANCE = {
    "budget_cap_source": "FAIL_CLOSED_ZERO_DEFAULT_UNDER_REVERSIBLE_AUTONOMY",
    "decision_time_utc": "NONE",
    "directive_observed_in_owner_session": True,
    "directive_semantics":
        "CONTINUE_NEXT_BOUNDED_T09_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_DECISION_UNIT",
    "explicit_credential_authority_observed": False,
    "explicit_endpoint_authority_observed": False,
    "explicit_production_runtime_authority_observed": False,
    "explicit_provider_authority_observed": False,
    "latest_directive_explicitly_named_budget_cap": False,
    "latest_directive_explicitly_named_owner_label": False,
    "no_runtime_provider_or_production_authority_inferred": True,
    "owner_label_source": "ESTABLISHED_PROJECT_OWNER_PROFILE",
    "owner_supplied_numeric_budget_cap": False,
    "trusted_decision_timestamp_observed": False,
}
OWNER_IMPLEMENTATION_ACTOR = {
    "binding_basis": "ESTABLISHED_PROFILE_PLUS_CURRENT_SESSION_CONTINUITY",
    "cryptographic_identity_verified": False,
    "delegated_runtime_authority": False,
    "runtime_owner_decision_recorded": False,
    "runtime_owner_identity_bound": False,
    "semantic_actor_binding_recorded": True,
    "semantic_actor_label": "pallasting",
    "semantic_actor_role": "PROJECT_OWNER",
    "signature_observed": False,
}

REQUEST_FIELDS = [
    "raw_frame_sha256",
    "canonical_frame_sha256",
    "packet_id_sha256",
    "signature_subject_sha256",
    "validation_subject_sha256",
]
POLICY_MATCH_FIELDS = [
    "t08_receipt_content_sha256",
    "track_id",
    *REQUEST_FIELDS,
]
FORBIDDEN_REQUEST_FIELDS = [
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
    "t08_receipt",
    "t08_receipt_content_sha256",
    "track_id",
]
CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_PROFILES = [
    {
        "canonical_frame_sha256": "e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295",
        "packet_id_sha256": "f89f204c4dcb19e078a4448d8824ca8e7435688e06c5e57265789e273104571e",
        "raw_frame_sha256": "e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295",
        "signature_subject_sha256": "a52aa400add05bb7b545c9eddbf1f48e55befd393f07c5c6ba6baaefd4f5343b",
        "t08_receipt_content_sha256":
            "7bf4b4151a12428da34eb5a095d340a4b5a1c531381385bf262cb1d5df7415b9",
        "track_id": "MANAGED_SPANNER_CLOUD_KMS",
        "validation_subject_sha256":
            "7bf4b4151a12428da34eb5a095d340a4b5a1c531381385bf262cb1d5df7415b9",
    },
    {
        "canonical_frame_sha256": "da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e",
        "packet_id_sha256": "16f3d9bb3c69666d374e72f16036f5fe152ab73d864c051e57429fe4f09308bc",
        "raw_frame_sha256": "da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e",
        "signature_subject_sha256": "2eb3584afe6c8f18281224785ec083e531da37eed71524f2eedbf3a8225055ac",
        "t08_receipt_content_sha256":
            "77e9eadcc83235e9f5b0357e9ca15b046c4044d36e764583b481bc7fb2c29865",
        "track_id": "SELF_HOSTED_ETCD_OPENBAO",
        "validation_subject_sha256":
            "77e9eadcc83235e9f5b0357e9ca15b046c4044d36e764583b481bc7fb2c29865",
    },
]

AUTHORIZED_COMPONENT_CONTRACT = {
    "binding_model": {
        "binding_profile_count": 2,
        "binding_profiles": CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_PROFILES,
        "default_disposition": "REJECTED_FAIL_CLOSED",
        "group_or_role_inheritance_allowed": False,
        "hierarchical_match_allowed": False,
        "matching_profile": "EXACT_ALL_FIELDS_ASCII_BYTE_EQUAL",
        "policy_match_dimension_count": 7,
        "policy_match_fields": POLICY_MATCH_FIELDS,
        "prefix_match_allowed": False,
        "profile_order": [
            "MANAGED_SPANNER_CLOUD_KMS",
            "SELF_HOSTED_ETCD_OPENBAO",
        ],
        "reject_on_multiple_matches": True,
        "reject_on_zero_matches": True,
        "request_field_count": 5,
        "request_fields": REQUEST_FIELDS,
        "wildcards_allowed": False,
    },
    "input_topology": {
        "binding_policy_may_be_sourced_from_frame": False,
        "binding_policy_may_be_sourced_from_request": False,
        "binding_request_observed_after_policy": True,
        "caller_supplied_predecessor_receipt_allowed": False,
        "frame_reparsed_by_t09_after_t08_success": False,
        "predecessor_reviewer_call_count_per_success": 1,
        "production_and_unknown_mode_rejected_before_any_input_observation": True,
        "public_input_tuple": [
            "frame",
            "detached_authentication_bundle",
            "separately_injected_synthetic_trust_policy",
            "separately_injected_synthetic_signer_authorization_policy",
            "detached_authorization_request",
            "separately_injected_synthetic_track_profile_binding_policy",
            "detached_track_profile_binding_request",
            "separately_injected_synthetic_end_to_end_subject_binding_policy",
            "detached_end_to_end_subject_binding_request",
            "separately_injected_synthetic_content_identity_and_quarantine_custody_policy",
            "detached_content_identity_and_quarantine_custody_request",
            "mode",
        ],
        "request_fields_forbidden": FORBIDDEN_REQUEST_FIELDS,
        "review_order": [
            "MODE_PREOBSERVATION_GUARD",
            "T08_END_TO_END_SUBJECT_BINDING_REVIEW_EXACTLY_ONCE",
            "DERIVE_FIVE_IDENTITIES_FROM_EXACT_PUBLIC_FRAME_AND_T08_RECEIPT",
            "SEPARATE_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_POLICY_REVIEW",
            "DETACHED_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_REQUEST_REVIEW_LAST",
            "EXACT_SINGLE_PROFILE_MATCH",
        ],
        "canonical_identity_profile":
            "EXACT_PREDECESSOR_ACCEPTED_CANONICAL_FRAME_BYTES_NO_REPARSE_OR_RESERIALIZE",
        "packet_id_domain": "AB_TRACK_B_T09_SYNTHETIC_PACKET_ID_V1",
        "signature_subject_profile":
            "SHA256_OF_T05_U64BE_LENGTH_PREFIXED_TRACK_DOMAIN_AND_EXACT_FRAME_BYTES",
        "track_and_validation_subject_source": "T08_PREDECESSOR_RECEIPT_ONLY",
    },
    "local_scope": {
        "authorized_candidate_surface_component_count": 1,
        "authorized_candidate_surface_components": [
            "CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_SYNTHETIC_VERIFIER"
        ],
        "authorized_local_threat_specification_count": 1,
        "authorized_local_threat_specifications": ["T09"],
        "candidate_surface_components_implemented_by_decision": 0,
        "production_ingestion_control_implemented_by_authorization": False,
        "target_production_control": "QUARANTINE_CUSTODY",
    },
    "output_boundary": {
        "evidence_acceptance_authorized": False,
        "output_or_claim_authorized": False,
        "successful_component_state":
            "BOUND_FIVE_SYNTHETIC_CONTENT_IDENTITIES_TO_EXACT_FRAME_AND_T08_RECEIPT_CHAIN_ONLY",
    },
    "reviewer_topology": {
        "checker_is_production_security_approval": False,
        "lane_identity_distinctness_required": True,
        "minimum_independent_reviewer_lane_count": 2,
        "production_security_reviewer_binding": "NONE",
        "required_reviewer_lanes": [
            "CONTRACT_CONFORMANCE_REVIEW",
            "SECURITY_AND_SOURCE_BOUND_GATE_REVIEW",
        ],
    },
    "truth_boundary": {
        "canonicalization_generalized_beyond_exact_kat_frame": False,
        "content_identity_truth_proved": False,
        "durable_custody_proved": False,
        "packet_identity_authenticated": False,
        "signature_subject_identity_authenticated": False,
        "t09_content_identity_and_quarantine_custody_implemented": False,
        "t08_receipt_and_track_are_non_substitutable_exact_policy_dimensions": True,
        "validation_subject_identity_authenticated": False,
    },
}

ALLOWED_OPERATIONS = [
    "ADD_CLOSED_WORLD_SYNTHETIC_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_POLICY_REQUEST_AND_RECEIPT_SCHEMAS",
    "ADD_EXACT_TWO_PROFILE_DEFAULT_REJECT_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_REGISTRY_KATS",
    "ADD_PURE_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_REFERENCE_VERIFIER_FOR_FIXED_PUBLIC_ONLY_KATS",
    "COMPOSE_EXACTLY_ONCE_WITH_FROZEN_T08_PREDECESSOR_PUBLIC_REVIEW_API",
    "BIND_EXACT_RAW_CANONICAL_PACKET_SIGNATURE_AND_VALIDATION_SUBJECT_SHA256_IDENTITIES_TO_T08_RECEIPT",
    "DERIVE_RAW_AND_CANONICAL_SHA256_FROM_UNCHANGED_EXACT_PREDECESSOR_ACCEPTED_FRAME_BYTES",
    "DERIVE_DOMAIN_SEPARATED_SYNTHETIC_PACKET_ID_AND_EXACT_T05_SIGNATURE_SUBJECT_SHA256",
    "ADD_PREOBSERVATION_SYNTHETIC_PRODUCTION_MODE_GUARDS",
    "ADD_DETERMINISTIC_NONSECRET_PUBLIC_ONLY_ADVERSARIAL_KATS",
    "ADD_PURE_REVIEWER_INDEPENDENT_CONTRACT_AND_SECURITY_GATE_LANES_REPORT_AND_SOURCE_BOUND_GATE",
]
FORBIDDEN_OPERATIONS = [
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
    "BIND_OR_CLAIM_REAL_CONTENT_PACKET_SIGNATURE_OR_VALIDATION_SUBJECT_TRUTH",
    "BIND_PRODUCTION_OWNER_EVIDENCE_AUDIENCE_OR_NONCE",
    "BIND_PROVIDER_OR_PRODUCTION_ENDPOINT",
    "CALL_PROVIDER_OR_ATTEMPT_WIRE",
    "CLAIM_CONFIGURATION_NAMESPACE_PACKET_PROFILE_OR_PROVIDER_PROFILE_CURRENTNESS_OR_TRUTH",
    "CLAIM_PRODUCTION_CONTENT_IDENTITY_CUSTODY_OR_MITIGATION",
    "COMMIT_PRIVATE_KEY_TEST_SEED_OR_SECRET_SHAPED_MATERIAL",
    "CREATE_RUNTIME_OR_EXPERIMENT_ROW",
    "DEPLOY_OR_ENABLE_PRODUCTION_INGESTION",
    "DERIVE_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_POLICY_FROM_FRAME_BUNDLE_OR_REQUEST",
    "ESTABLISH_DURABLE_CUSTODY_RETENTION_TOMBSTONE_OR_REPLAY_LEDGER",
    "IMPLEMENT_T09_CONTENT_IDENTITY_QUARANTINE_CUSTODY_OR_REPLAY_CAS",
    "LAUNCH_RUNNER_OR_BACKGROUND_DAEMON",
    "PARSE_OR_RESERIALIZE_FRAME_AGAIN_TO_DERIVE_T09_IDENTITIES",
    "PERSIST_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_POLICY_REQUEST_OR_RESULT",
    "PROVISION_PAID_OR_EXTERNAL_RESOURCE",
    "READ_AMBIENT_DEFAULT_OR_SYSTEM_TRUST_OR_CREDENTIAL_CHAIN",
    "REGISTER_OR_IMPORT_INTO_PRODUCTION_RUNTIME",
    "REPRESENT_RUNTIME_OWNER_DECISION",
    "SATISFY_RUNTIME_PREREQUISITE",
    "TAKE_TRACK_OR_VALIDATION_SUBJECT_FROM_DETACHED_T09_REQUEST_OR_RAW_FRAME",
    "USE_AMBIENT_OR_PRODUCTION_TRUSTED_TIME",
]
IMPLEMENTATION_AUTHORITY = {
    "allowed_operations": ALLOWED_OPERATIONS,
    "authority_class": "REVERSIBLE_CODE_SCHEMA_TEST_DOCUMENTATION_ONLY",
    "authorized_candidate_surface_component_count": 1,
    "authorized_local_threat_specifications": ["T09"],
    "current_state": CURRENT_STATE,
    "default_off_required": True,
    "effective_only_after_integrated_full_gate": True,
    "exact_next_unit_authorized": True,
    "forbidden_operations": FORBIDDEN_OPERATIONS,
    "implementation_authority_recorded": True,
    "implementation_scope":
        "T09_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_ISOLATED_LAB_CODE_ONLY_EXACT_NEXT_UNIT_SINGLE_USE_NON_TRANSITIVE",
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
    "max_content_identity_and_quarantine_custody_entries": 2,
    "max_content_identity_and_quarantine_custody_policy_bytes": 65536,
    "max_content_identity_and_quarantine_custody_request_bytes": 16384,
    "max_end_to_end_subject_binding_policy_bytes": 65536,
    "max_end_to_end_subject_binding_request_bytes": 16384,
    "max_trust_policy_bytes": 65536,
    "public_input_count": 12,
}
RESOURCE_BINDING = {
    "allowed_resource_classes": [
        "EXISTING_LOCAL_CPU_AND_MEMORY",
        "ISOLATED_AGENT_BRIDGE_WORKTREE",
        "PRIVATE_LOCAL_TEST_SCRATCH",
    ],
    "ambient_or_system_trust_store_allowed": False,
    "component_limits": COMPONENT_LIMITS,
    "component_runtime_network": False,
    "credential_handles": [],
    "credential_paths": [],
    "currency_scope": "ALL_CURRENCIES_ZERO_ONLY",
    "custody_store_binding": "NONE",
    "dependency_scope": "PYTHON_STANDARD_LIBRARY_REFERENCE_KAT_ONLY_NO_FETCH",
    "effective_external_paid_spend_cap": 0,
    "implementation_resource_binding_recorded": True,
    "owner_supplied_numeric_budget_cap": False,
    "private_key_or_seed_material_authorized": False,
    "production_resource_authority_bound": False,
    "provider_endpoints": [],
    "real_evidence_input_authorized": False,
    "replay_ledger_binding": "NONE",
    "resource_scope_id":
        "EXISTING_LOCAL_WORKTREE_PRIVATE_SCRATCH_LOCAL_COMPUTE_AND_COMMITTED_PUBLIC_ONLY_T08_AND_T09_KATS",
    "signing_or_key_generation_authorized": False,
    "test_data_scope":
        "COMMITTED_NONSECRET_PUBLIC_ONLY_SYNTHETIC_KAT_NO_SEEDS_NO_PRIVATE_KEYS",
    "trusted_time_binding": "FIXED_KAT_LABELS_ONLY_NOT_TRUSTED_TIME",
}

STATES = [
    "UNRECORDED_NO_AUTHORITY",
    CURRENT_STATE,
    "REJECTED_FAIL_CLOSED",
    "CONSUMED_SCOPE_COMPLETE",
    "INVALIDATED_REQUIRES_NEW_DECISION",
]
TRANSITIONS = [
    {
        "event": "OWNER_CONTINUES_NEXT_BOUNDED_T09_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_DECISION_PATH",
        "from_state": "UNRECORDED_NO_AUTHORITY",
        "to_state": CURRENT_STATE,
    },
    {
        "event": "OWNER_HOLDS_OR_REJECTS",
        "from_state": "UNRECORDED_NO_AUTHORITY",
        "to_state": "REJECTED_FAIL_CLOSED",
    },
    {
        "event": "EXACT_AUTHORIZED_T09_SUCCESSOR_INTEGRATED_AND_FULL_GATE_PASSES",
        "from_state": CURRENT_STATE,
        "to_state": "CONSUMED_SCOPE_COMPLETE",
    },
    {
        "event": (
            "OWNER_REVOKES_OR_BASELINE_UNIT_SCOPE_POLICY_BUDGET_NETWORK_"
            "CREDENTIAL_ENDPOINT_OR_REVIEWER_TOPOLOGY_DRIFTS"
        ),
        "from_state": CURRENT_STATE,
        "to_state": "INVALIDATED_REQUIRES_NEW_DECISION",
    },
]
STATE_MACHINE = {
    "current_state": CURRENT_STATE,
    "decision_full_gate_consumes_new_authority": False,
    "global_single_use_proved": False,
    "initial_state": "UNRECORDED_NO_AUTHORITY",
    "positive_provider_authority_state_representable": False,
    "runtime_authority_state_representable": False,
    "states": STATES,
    "terminal_states": [
        "REJECTED_FAIL_CLOSED",
        "CONSUMED_SCOPE_COMPLETE",
        "INVALIDATED_REQUIRES_NEW_DECISION",
    ],
    "transitions": TRANSITIONS,
}
ROLLBACK = {
    "local_worktree_delete_allowed": True,
    "production_kill_switch": "NOT_APPLICABLE_NOT_ENABLED",
    "production_rollback_authority": False,
    "published_git_revert_plan_required": True,
    "remote_git_mutation_authority_derived": False,
    "reversible_only": True,
    "runtime_disable_action_required": False,
    "scope_invalidation_requires_new_decision": True,
    "unpublished_change_revert_allowed": True,
}
BOUNDARY = {
    "authorized_future_candidate_surface_component_count": 1,
    "authorized_future_local_threat_specification_count": 1,
    "authorized_future_local_threat_specifications": ["T09"],
    "current_decision_candidate_surface_components_implemented": 0,
    "downstream_gate_count": 4,
    "downstream_gates_authorized": 0,
    "effective_only_after_integrated_full_gate": True,
    "exact_next_unit_authorized": True,
    "future_successor_candidate_surface_component_total": 7,
    "future_successor_candidate_surface_components_authorized": 1,
    "future_successor_minimum_independent_reviewer_lane_count": 2,
    "implementation_authority_recorded": True,
    "implementation_resource_binding_recorded": True,
    "implementation_scope_decision_recorded": True,
    "implementation_side_effects_unlocked": IMPLEMENTATION_SIDE_EFFECTS,
    "isolated_lab_predecessor_surface_component_total": 6,
    "isolated_lab_predecessor_surface_components_implemented": 6,
    "local_predecessor_threat_specifications_covered": 8,
    "local_t08_specification_exercised": True,
    "local_t09_specification_exercised": False,
    "owner_handoff_eligible": False,
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
    "end_to_end_subject_binding_isolated_lab_implemented": True,
    "content_identity_and_quarantine_custody_isolated_lab_implementation_authorized": True,
    "content_identity_and_quarantine_custody_isolated_lab_implemented": False,
    "quarantine_custody_production_control_implemented": False,
}
NONCLAIMS = {
    "any_production_ingestion_control_implemented": False,
    "application_claim_authorized": False,
    "build_truth_proved": False,
    "budget_cap_zero_is_budget_reservation": False,
    "condition_output_authorized": False,
    "configuration_currentness_proved": False,
    "configuration_truth_proved": False,
    "credential_or_secret_material_accessed": False,
    "deployment_authorized": False,
    "downstream_gate_authority_derived": False,
    "durable_custody_proved": False,
    "durable_replay_cas_proved": False,
    "evidence_acceptance_authorized": False,
    "experiment_rows_created": False,
    "external_paid_spend_authorized": False,
    "fault_injected": False,
    "fault_injection_authorized": False,
    "git_publication_authority_derived": False,
    "global_single_use_proved": False,
    "independent_checker_is_production_security_approval": False,
    "local_t09_kat_is_production_mitigation": False,
    "namespace_identity_authenticated": False,
    "namespace_truth_proved": False,
    "output_permit_defined": False,
    "owner_signature_observed": False,
    "packet_profile_truth_proved": False,
    "paid_resource_provisioned": False,
    "predecessor_receipt_is_caller_supplied": False,
    "prerequisite_truth_proved": False,
    "private_key_or_seed_material_present": False,
    "production_authorization_succeeded": False,
    "production_credentials_authorized": False,
    "production_endpoint_bound": False,
    "production_environment_implementation_authorized": False,
    "production_ingestion_enabled": False,
    "production_ingestion_implemented": False,
    "production_owner_class_bound": False,
    "production_resource_authority_bound": False,
    "production_security_approval": False,
    "production_security_reviewer_bound": False,
    "production_track_subject_binding_implemented": False,
    "provider_authority": False,
    "provider_called": False,
    "provider_or_lab_profile_currentness_proved": False,
    "provider_or_lab_profile_identity_authenticated": False,
    "real_evidence_accepted": False,
    "real_evidence_collected": False,
    "real_evidence_ingested": False,
    "real_evidence_present": False,
    "real_evidence_validated": False,
    "runner_launch_authorized": False,
    "runner_launched": False,
    "runtime_admission_granted": False,
    "runtime_admission_ready": False,
    "runtime_authority": False,
    "runtime_owner_decision_recorded": False,
    "runtime_owner_identity_bound": False,
    "runtime_rows_created": False,
    "scientific_claim_authorized": False,
    "semantic_owner_label_is_authenticated_identity": False,
    "signing_or_key_generation_authorized": False,
    "subject_identity_authenticated": False,
    "source_truth_proved": False,
    "subject_truth_proved": False,
    "t09_content_identity_and_quarantine_custody_implemented": False,
    "track_id_accepted_from_detached_t09_request": False,
    "track_id_derived_from_raw_frame_by_t09": False,
    "track_is_provider_profile_currentness": False,
    "trusted_production_time_bound": False,
    "wire_attempted": False,
}

DOMAIN_PREFIXES = {
    "authorized_component_contract": (
        b"agent-bridge\x00biocortex-ab\x00t09-content-identity-and-quarantine-custody-authority\x00"
        b"authorized-component-contract\x00v1\x00"
    ),
    "decision_provenance": (
        b"agent-bridge\x00biocortex-ab\x00t09-content-identity-and-quarantine-custody-authority\x00"
        b"decision-provenance\x00v1\x00"
    ),
    "implementation_authority": (
        b"agent-bridge\x00biocortex-ab\x00t09-content-identity-and-quarantine-custody-authority\x00"
        b"implementation-authority\x00v1\x00"
    ),
    "owner_implementation_actor": (
        b"agent-bridge\x00biocortex-ab\x00t09-content-identity-and-quarantine-custody-authority\x00"
        b"owner-implementation-actor\x00v1\x00"
    ),
    "resource_binding": (
        b"agent-bridge\x00biocortex-ab\x00t09-content-identity-and-quarantine-custody-authority\x00"
        b"resource-binding\x00v1\x00"
    ),
    "state_machine": (
        b"agent-bridge\x00biocortex-ab\x00t09-content-identity-and-quarantine-custody-authority\x00"
        b"state-machine\x00v1\x00"
    ),
    "rollback": (
        b"agent-bridge\x00biocortex-ab\x00t09-content-identity-and-quarantine-custody-authority\x00"
        b"rollback\x00v1\x00"
    ),
    "boundary": (
        b"agent-bridge\x00biocortex-ab\x00t09-content-identity-and-quarantine-custody-authority\x00"
        b"boundary\x00v1\x00"
    ),
    "nonclaims": (
        b"agent-bridge\x00biocortex-ab\x00t09-content-identity-and-quarantine-custody-authority\x00"
        b"nonclaims\x00v1\x00"
    ),
    "decision_record": (
        b"agent-bridge\x00biocortex-ab\x00t09-content-identity-and-quarantine-custody-authority\x00"
        b"decision-record\x00v1\x00"
    ),
    "receipt_content": (
        b"agent-bridge\x00biocortex-ab\x00t09-content-identity-and-quarantine-custody-authority\x00"
        b"receipt-content\x00v1\x00"
    ),
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
HASHED_SECTION_NAMES = (
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
SECTION_HASH_KEYS = tuple(f"{name}_sha256" for name in HASHED_SECTION_NAMES)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ValueError(f"{code}: {message}")


def exact_keys(value: Mapping[str, Any], expected: Iterable[str], code: str) -> None:
    require(type(value) is dict, code, "expected plain object")
    require(set(value) == set(expected), code, "closed-world key mismatch")


def exact_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return (
            set(left) == set(right)
            and all(exact_equal(left[key], right[key]) for key in left)
        )
    if type(left) is list:
        return len(left) == len(right) and all(
            exact_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def _clone(value: Any) -> Any:
    if type(value) is dict:
        return {key: _clone(item) for key, item in value.items()}
    if type(value) is list:
        return [_clone(item) for item in value]
    return value


def _validate_json_value(value: Any, depth: int = 0) -> None:
    require(depth <= 32, "E_JSON_DEPTH", "JSON depth exceeded")
    if value is None or type(value) in (bool, int, str):
        if type(value) is int:
            require(-(2**63) <= value <= 2**63 - 1, "E_JSON_INT", "int64 only")
        return
    if type(value) is list:
        require(len(value) <= 64, "E_JSON_ARRAY", "array too large")
        for item in value:
            _validate_json_value(item, depth + 1)
        return
    if type(value) is dict:
        require(len(value) <= 256, "E_JSON_OBJECT", "object too large")
        for key, item in value.items():
            require(type(key) is str and key != "", "E_JSON_KEY", "bad key")
            _validate_json_value(item, depth + 1)
        return
    raise ValueError("E_JSON_TYPE: unsupported JSON type")


def canonical_bytes(value: Any) -> bytes:
    _validate_json_value(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def domain_sha256(domain: str, value: Any) -> str:
    require(domain in DOMAIN_PREFIXES, "E_DOMAIN", "unknown hash domain")
    return hashlib.sha256(DOMAIN_PREFIXES[domain] + canonical_bytes(value)).hexdigest()


def expected_section_hashes(record: Mapping[str, Any]) -> dict[str, str]:
    return {
        f"{name}_sha256": domain_sha256(name, record[name])
        for name in HASHED_SECTION_NAMES
    }


def build_owner_decision_record() -> dict[str, Any]:
    record = {
        "authorized_component_contract": _clone(AUTHORIZED_COMPONENT_CONTRACT),
        "boundary": _clone(BOUNDARY),
        "date": DATE,
        "decision": DECISION,
        "decision_provenance": _clone(DECISION_PROVENANCE),
        "implementation_authority": _clone(IMPLEMENTATION_AUTHORITY),
        "next_unit": NEXT_UNIT,
        "nonclaims": _clone(NONCLAIMS),
        "owner_implementation_actor": _clone(OWNER_IMPLEMENTATION_ACTOR),
        "predecessor": _clone(PREDECESSOR),
        "resource_binding": _clone(RESOURCE_BINDING),
        "rollback": _clone(ROLLBACK),
        "schema": RECORD_SCHEMA,
        "schema_version": 1,
        "section_sha256": {},
        "state_machine": _clone(STATE_MACHINE),
        "status": STATUS,
    }
    record["section_sha256"] = expected_section_hashes(record)
    return record


def _validate_semantic_boundaries(record: Mapping[str, Any]) -> None:
    expected = build_owner_decision_record()
    require(exact_equal(record, expected), "E_DECISION_DRIFT", "record drift")

    contract = record["authorized_component_contract"]
    model = contract["binding_model"]
    topology = contract["input_topology"]
    truth = contract["truth_boundary"]
    authority = record["implementation_authority"]
    boundary = record["boundary"]
    resources = record["resource_binding"]
    predecessor = record["predecessor"]

    require(model["binding_profile_count"] == 2, "E_PROFILE_COUNT", "two profiles")
    require(
        model["policy_match_fields"] == POLICY_MATCH_FIELDS,
        "E_MATCH_FIELDS",
        "match dimensions drift",
    )
    require(
        model["request_fields"] == REQUEST_FIELDS,
        "E_REQUEST_FIELDS",
        "request fields drift",
    )
    require(
        topology["request_fields_forbidden"] == FORBIDDEN_REQUEST_FIELDS,
        "E_FORBIDDEN_FIELDS",
        "forbidden request fields drift",
    )
    require(
        topology["public_input_tuple"][-1] == "mode"
        and len(topology["public_input_tuple"]) == 12,
        "E_INPUT_TOPOLOGY",
        "exact twelve-input API required",
    )
    require(
        topology["review_order"][0] == "MODE_PREOBSERVATION_GUARD"
        and topology["review_order"][-1] == "EXACT_SINGLE_PROFILE_MATCH",
        "E_REVIEW_ORDER",
        "review order drift",
    )
    require(
        topology["track_and_validation_subject_source"]
        == "T08_PREDECESSOR_RECEIPT_ONLY"
        and topology["frame_reparsed_by_t09_after_t08_success"] is False,
        "E_TRACK_SOURCE",
        "track must come only from T08 receipt",
    )
    require(
        all(value is False for key, value in truth.items() if key.endswith("_proved"))
        and truth["t09_content_identity_and_quarantine_custody_implemented"] is False,
        "E_T09_LEAKAGE",
        "decision must not claim T09 implementation or real-world truth",
    )
    require(
        all(type(item) is dict and set(item) == set(POLICY_MATCH_FIELDS)
            for item in model["binding_profiles"]),
        "E_PROFILE_SHAPE",
        "profile shape drift",
    )
    require(
        [item["track_id"] for item in model["binding_profiles"]]
        == model["profile_order"],
        "E_PROFILE_ORDER",
        "profile order drift",
    )
    require(
        len({item["track_id"] for item in model["binding_profiles"]}) == 2,
        "E_PROFILE_DUPLICATE",
        "duplicate track profile",
    )
    require(
        predecessor["authorization_consumption_state"] == "CONSUMED_SCOPE_COMPLETE"
        and predecessor["implementation_authority_single_use_consumed"] is True
        and predecessor["local_t08_specification_exercised"] is True,
        "E_PREDECESSOR_CONSUMPTION",
        "T08 must be released and consumed",
    )
    require(
        boundary["current_decision_candidate_surface_components_implemented"] == 0
        and boundary["isolated_lab_predecessor_surface_components_implemented"] == 6
        and boundary["local_predecessor_threat_specifications_covered"] == 8
        and boundary["future_successor_candidate_surface_component_total"] == 7,
        "E_COMPONENT_COUNTS",
        "6/8 predecessor and 7/9 future ceiling required",
    )
    require(
        boundary["local_t08_specification_exercised"] is True
        and boundary["local_t09_specification_exercised"] is False
        and boundary["local_t09_specification_exercised"] is False,
        "E_PREMATURE_IMPLEMENTATION",
        "decision implements no successor",
    )
    require(
        authority["effective_only_after_integrated_full_gate"] is True
        and record["state_machine"]["decision_full_gate_consumes_new_authority"]
        is False,
        "E_AUTHORITY_TIMING",
        "full activates but does not consume new authority",
    )
    require(
        resources["effective_external_paid_spend_cap"] == 0
        and resources["component_runtime_network"] is False
        and resources["provider_endpoints"] == []
        and resources["credential_handles"] == []
        and resources["credential_paths"] == [],
        "E_RESOURCE_BOUNDARY",
        "zero external resources required",
    )
    require(
        all(value is False for value in record["nonclaims"].values()),
        "E_NONCLAIMS",
        "every nonclaim must be explicit false",
    )


def review_decision(record: Mapping[str, Any]) -> dict[str, Any]:
    exact_keys(record, TOP_LEVEL_KEYS, "E_TOP_LEVEL")
    _validate_json_value(record)
    _validate_semantic_boundaries(record)
    require(
        exact_equal(record["section_sha256"], expected_section_hashes(record)),
        "E_SECTION_HASH",
        "section hash mismatch",
    )

    decision_without_hashes = {
        key: _clone(value)
        for key, value in record.items()
        if key != "section_sha256"
    }
    decision_record_sha256 = domain_sha256("decision_record", decision_without_hashes)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": STATUS,
        "decision": DECISION,
        "date": DATE,
        "mode": MODE,
        "next_unit": NEXT_UNIT,
        "current_state": CURRENT_STATE,
        "authorization_effective_only_after_integrated_full_gate":
            record["boundary"]["effective_only_after_integrated_full_gate"],
        "implementation_authority_recorded":
            record["boundary"]["implementation_authority_recorded"],
        "implementation_scope_decision_recorded":
            record["boundary"]["implementation_scope_decision_recorded"],
        "implementation_resource_binding_recorded":
            record["boundary"]["implementation_resource_binding_recorded"],
        "implementation_authority_single_use_consumed": False,
        "predecessor_authorization_consumption_state":
            record["predecessor"]["authorization_consumption_state"],
        "predecessor_implementation_authority_single_use_consumed":
            record["predecessor"]["implementation_authority_single_use_consumed"],
        "authorized_candidate_surface_component_count":
            record["implementation_authority"][
                "authorized_candidate_surface_component_count"
            ],
        "authorized_local_threat_specification_count":
            len(record["implementation_authority"][
                "authorized_local_threat_specifications"
            ]),
        "authorized_local_threat_specifications":
            ",".join(record["implementation_authority"][
                "authorized_local_threat_specifications"
            ]),
        "binding_profile_count":
            record["authorized_component_contract"]["binding_model"][
                "binding_profile_count"
            ],
        "binding_request_field_count":
            record["authorized_component_contract"]["binding_model"][
                "request_field_count"
            ],
        "binding_policy_match_dimension_count":
            record["authorized_component_contract"]["binding_model"][
                "policy_match_dimension_count"
            ],
        "default_disposition":
            record["authorized_component_contract"]["binding_model"][
                "default_disposition"
            ],
        "wildcards_allowed":
            record["authorized_component_contract"]["binding_model"][
                "wildcards_allowed"
            ],
        "public_input_count":
            record["resource_binding"]["component_limits"]["public_input_count"],
        "end_to_end_subject_binding_implemented":
            record["boundary"][
                "end_to_end_subject_binding_isolated_lab_implemented"
            ],
        "content_identity_and_quarantine_custody_implemented":
            record["boundary"]["content_identity_and_quarantine_custody_isolated_lab_implemented"],
        "quarantine_custody_production_control_implemented":
            record["boundary"][
                "quarantine_custody_production_control_implemented"
            ],
        "local_t08_specification_exercised":
            record["boundary"]["local_t08_specification_exercised"],
        "local_t09_specification_exercised":
            record["boundary"]["local_t09_specification_exercised"],
        "future_successor_candidate_surface_component_total":
            record["boundary"]["future_successor_candidate_surface_component_total"],
        "future_successor_candidate_surface_components_authorized":
            record["boundary"][
                "future_successor_candidate_surface_components_authorized"
            ],
        "current_decision_candidate_surface_components_implemented":
            record["boundary"][
                "current_decision_candidate_surface_components_implemented"
            ],
        "isolated_lab_predecessor_surface_components_implemented":
            record["boundary"][
                "isolated_lab_predecessor_surface_components_implemented"
            ],
        "local_predecessor_threat_specifications_covered":
            record["boundary"]["local_predecessor_threat_specifications_covered"],
        "future_successor_minimum_independent_reviewer_lane_count":
            record["boundary"][
                "future_successor_minimum_independent_reviewer_lane_count"
            ],
        "production_security_reviewer_bound":
            record["boundary"]["production_security_reviewer_bound"],
        "owner_semantic_actor_label":
            record["owner_implementation_actor"]["semantic_actor_label"],
        "owner_semantic_actor_binding_recorded":
            record["owner_implementation_actor"][
                "semantic_actor_binding_recorded"
            ],
        "owner_cryptographic_identity_verified":
            record["owner_implementation_actor"][
                "cryptographic_identity_verified"
            ],
        "owner_signature_observed":
            record["owner_implementation_actor"]["signature_observed"],
        "owner_supplied_numeric_budget_cap":
            record["decision_provenance"]["owner_supplied_numeric_budget_cap"],
        "external_paid_spend_cap":
            record["resource_binding"]["effective_external_paid_spend_cap"],
        "allowed_operation_count":
            len(record["implementation_authority"]["allowed_operations"]),
        "forbidden_operation_count":
            len(record["implementation_authority"]["forbidden_operations"]),
        "provider_endpoint_count":
            len(record["resource_binding"]["provider_endpoints"]),
        "component_runtime_network":
            record["resource_binding"]["component_runtime_network"],
        "global_single_use_proved":
            record["state_machine"]["global_single_use_proved"],
        "production_environment_implementation_authorized":
            record["implementation_authority"][
                "production_environment_implementation_authorized"
            ],
        "production_ingestion_implemented":
            record["boundary"]["production_ingestion_implemented"],
        "production_ingestion_enabled":
            record["boundary"]["production_ingestion_enabled"],
        "production_ingestion_controls_implemented":
            record["boundary"]["production_ingestion_controls_implemented"],
        "production_ingestion_controls_runtime_exercised":
            record["boundary"][
                "production_ingestion_controls_runtime_exercised"
            ],
        "real_evidence_items_present":
            record["boundary"]["real_evidence_items_present"],
        "production_validated_evidence_items":
            record["boundary"]["production_validated_evidence_items"],
        "runtime_evidence_accepted":
            record["boundary"]["runtime_evidence_accepted"],
        "runtime_prerequisites_satisfied":
            record["boundary"]["runtime_prerequisites_satisfied"],
        "runtime_owner_identity_bound":
            record["boundary"]["runtime_owner_identity_bound"],
        "runtime_owner_decision_recorded":
            record["boundary"]["runtime_owner_decision_recorded"],
        "runtime_admission_ready":
            record["boundary"]["runtime_admission_ready"],
        "runtime_admission_granted":
            record["boundary"]["runtime_admission_granted"],
        "runtime_authority": record["boundary"]["runtime_authority"],
        "provider_authority": record["boundary"]["provider_authority"],
        "downstream_gates_authorized":
            record["boundary"]["downstream_gates_authorized"],
        "runtime_side_effects_unlocked":
            record["boundary"]["runtime_side_effects_unlocked"],
        "implementation_side_effects_unlocked":
            record["boundary"]["implementation_side_effects_unlocked"],
        "nonclaim_field_count": len(record["nonclaims"]),
        "all_nonclaims_explicit":
            all(value is False for value in record["nonclaims"].values()),
        "authorized_component_contract_sha256":
            record["section_sha256"]["authorized_component_contract_sha256"],
        "implementation_authority_sha256":
            record["section_sha256"]["implementation_authority_sha256"],
        "resource_binding_sha256":
            record["section_sha256"]["resource_binding_sha256"],
        "state_machine_sha256":
            record["section_sha256"]["state_machine_sha256"],
        "rollback_sha256": record["section_sha256"]["rollback_sha256"],
        "boundary_sha256": record["section_sha256"]["boundary_sha256"],
        "nonclaims_sha256": record["section_sha256"]["nonclaims_sha256"],
        "decision_record_sha256": decision_record_sha256,
        "predecessor_integration_commit":
            record["predecessor"]["integration_commit"],
        "predecessor_receipt_content_sha256":
            record["predecessor"]["receipt_content_sha256"],
        "t09_semantic_specification_raw_sha256":
            record["predecessor"]["t09_semantic_specification_raw_sha256"],
    }
    receipt["content_sha256"] = domain_sha256("receipt_content", receipt)
    return receipt


TSV_FIELDS = (
    "schema",
    "status",
    "decision",
    "date",
    "mode",
    "next_unit",
    "current_state",
    "authorization_effective_only_after_integrated_full_gate",
    "implementation_authority_recorded",
    "implementation_scope_decision_recorded",
    "implementation_resource_binding_recorded",
    "implementation_authority_single_use_consumed",
    "predecessor_authorization_consumption_state",
    "predecessor_implementation_authority_single_use_consumed",
    "authorized_candidate_surface_component_count",
    "authorized_local_threat_specification_count",
    "authorized_local_threat_specifications",
    "binding_profile_count",
    "binding_request_field_count",
    "binding_policy_match_dimension_count",
    "default_disposition",
    "wildcards_allowed",
    "public_input_count",
    "end_to_end_subject_binding_implemented",
    "content_identity_and_quarantine_custody_implemented",
    "quarantine_custody_production_control_implemented",
    "local_t08_specification_exercised",
    "local_t09_specification_exercised",
    "future_successor_candidate_surface_component_total",
    "future_successor_candidate_surface_components_authorized",
    "current_decision_candidate_surface_components_implemented",
    "isolated_lab_predecessor_surface_components_implemented",
    "local_predecessor_threat_specifications_covered",
    "future_successor_minimum_independent_reviewer_lane_count",
    "production_security_reviewer_bound",
    "owner_semantic_actor_label",
    "owner_semantic_actor_binding_recorded",
    "owner_cryptographic_identity_verified",
    "owner_signature_observed",
    "owner_supplied_numeric_budget_cap",
    "external_paid_spend_cap",
    "allowed_operation_count",
    "forbidden_operation_count",
    "provider_endpoint_count",
    "component_runtime_network",
    "global_single_use_proved",
    "production_environment_implementation_authorized",
    "production_ingestion_implemented",
    "production_ingestion_enabled",
    "production_ingestion_controls_implemented",
    "production_ingestion_controls_runtime_exercised",
    "real_evidence_items_present",
    "production_validated_evidence_items",
    "runtime_evidence_accepted",
    "runtime_prerequisites_satisfied",
    "runtime_owner_identity_bound",
    "runtime_owner_decision_recorded",
    "runtime_admission_ready",
    "runtime_admission_granted",
    "runtime_authority",
    "provider_authority",
    "downstream_gates_authorized",
    "runtime_side_effects_unlocked",
    "implementation_side_effects_unlocked",
    "nonclaim_field_count",
    "all_nonclaims_explicit",
    "authorized_component_contract_sha256",
    "implementation_authority_sha256",
    "resource_binding_sha256",
    "state_machine_sha256",
    "rollback_sha256",
    "boundary_sha256",
    "nonclaims_sha256",
    "decision_record_sha256",
    "predecessor_integration_commit",
    "predecessor_receipt_content_sha256",
    "t09_semantic_specification_raw_sha256",
    "content_sha256",
)


def render_tsv(receipt: Mapping[str, Any]) -> str:
    exact_keys(receipt, TSV_FIELDS, "E_RECEIPT_KEYS")
    lines: list[str] = []
    for field in TSV_FIELDS:
        value = receipt[field]
        if type(value) is bool:
            rendered = "true" if value else "false"
        elif type(value) in (int, str):
            rendered = str(value)
        else:
            raise ValueError(f"E_RECEIPT_TYPE: {field}")
        require(
            "\t" not in rendered and "\n" not in rendered and "\r" not in rendered,
            "E_RECEIPT_CONTROL",
            field,
        )
        lines.append(f"{field}\t{rendered}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(render_tsv(review_decision(build_owner_decision_record())), end="")
