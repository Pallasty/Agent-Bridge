#!/usr/bin/env python3
"""Pure reviewer for the signer role/scope isolated-lab authority decision.

The reviewed record can authorize one exact reversible repository successor.
It does not implement authorization, accept evidence, authenticate a real
owner or subject, provide replay protection, or expose a runtime/provider API.
All inputs are already in memory.  The reviewer performs no filesystem,
environment, clock, process, network, provider, credential, randomness,
entropy, signing, key-generation, or mutable-global-state I/O.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping


RECORD_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "signer_role_scope_authorization_isolated_lab_implementation_authority_and_"
    "resource_binding_decision.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "signer_role_scope_authorization_isolated_lab_implementation_authority_and_"
    "resource_binding_decision_v1.receipt.v0"
)
DATE = "2026-07-18"
STATUS = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_"
    "RESOURCE_SCOPE_RECORDED_ZERO_EXTERNAL_SPEND_NO_RUNTIME_OR_PROVIDER_AUTHORITY"
)
DECISION = (
    "AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_SIGNER_ROLE_SCOPE_AUTHORIZATION_"
    "ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED"
)
MODE = "ISOLATED_LAB_FIRST"
CURRENT_STATE = "AUTHORIZED_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_EXACT_UNIT"
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "SIGNER_ROLE_SCOPE_AUTHORIZATION_SYNTHETIC_EXACT_OWNER_CLASS_EVIDENCE_CLASS_"
    "TRACK_SUBJECT_AUDIENCE_AND_NONCE_POLICY_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
)
IMPLEMENTATION_SIDE_EFFECTS = (
    "REVERSIBLE_LOCAL_CODE_SCHEMA_TEST_DOCS_FOR_EXACT_NEXT_UNIT_ONLY"
)

PREDECESSOR_MANIFEST_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_"
    "exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_"
    "pack_v0.json"
)
PREDECESSOR_GATE_PATH = (
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-bootstrap-trust-authentication-synthetic-trust-chain-exact-key-"
    "version-declared-role-and-revocation-verifier-isolated-lab-v1-pack.sh"
)
T06_SEMANTIC_SPECIFICATION_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_runtime_prerequisite_evidence_packet_offline_integration_"
    "and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
)

PREDECESSOR_ARTIFACT_RAW_SHA256 = {
    (
        "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-"
        "injection-runner-bootstrap-trust-authentication-isolated-lab-v1.schema.json"
    ): "d078513da9cabad07fb000485fdcb663ede13993341917d56792a8a1c909901c",
    (
        "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-"
        "fault-injection-runner-bootstrap-trust-authentication-synthetic-trust-"
        "chain-exact-key-version-declared-role-and-revocation-verifier-isolated-"
        "lab-v1-pack.md"
    ): "9da0b11bfc86011ca792a6c0b2836c53c55837c17ac680296f5ad595b1a32ef0",
    PREDECESSOR_GATE_PATH: (
        "aaa66cd7b2045571a766839aea8e2f269bbaab9c15ba7607da0d57fe253fb061"
    ),
    (
        "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_"
        "runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_"
        "version_declared_role_and_revocation_verifier_isolated_lab_v1.py"
    ): "f483200c34ab570b3da8f45d6e4d0adb8e382f5d6fa815112a2c0b62c0431341",
    (
        "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_"
        "exact_key_version_declared_role_and_revocation_verifier_isolated_lab_"
        "v1_pack.py"
    ): "bcfe18cb20733392fb4f494e9783ca99d90afc52429024f2f88cfd2163d29e20",
    (
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_"
        "exact_key_version_declared_role_and_revocation_verifier_isolated_lab_"
        "v1_pack.expected.v0.tsv"
    ): "0085ddde9579cfaa0050cd71c07bc26fd0dc34d2c144400ad16535dd480aaa36",
    (
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_"
        "exact_key_version_declared_role_and_revocation_verifier_isolated_lab_"
        "v1_pack_synthetic_v0.json"
    ): "31959b02f20278d126be3a7e18e44e220b47cffb41804f69e3ace5c93277923e",
    PREDECESSOR_MANIFEST_PATH: (
        "bd0cca68c7edf8d992a7ec27cb4c700cd97cf61c4a2557ad56aca5f996a6744b"
    ),
}

PREDECESSOR = {
    "artifact_raw_sha256": PREDECESSOR_ARTIFACT_RAW_SHA256,
    "authorization_consumption_state": "CONSUMED_SCOPE_COMPLETE",
    "bootstrap_trust_authentication_implemented": True,
    "decision_source_baseline_commit": (
        "7df72e2d49bbc25580d4dcb63bc1a183120bba77"
    ),
    "decision_source_baseline_parents": [
        "2707996e0616885fa51da9b908764f017a67299f",
        "2a26de5b99886922240350fadefa07bc8f4c5dcd",
    ],
    "decision_source_baseline_tree": (
        "7fc4786b814d81d97e8672bcae484c07e180f04a"
    ),
    "fast_stdout_line_count": 95,
    "fast_stdout_sha256": (
        "3881e2fbeacfa584098233cae7f7b8cbb56e4f5abb6d7dfb7c75fc59420b7f1b"
    ),
    "full_stdout_line_count": 96,
    "full_stdout_sha256": (
        "baf76dca1f7ff58da7c352665b88ef39503a5765d102f885d29777a3c7d1e0ed"
    ),
    "gate_path": PREDECESSOR_GATE_PATH,
    "gate_raw_sha256": (
        "aaa66cd7b2045571a766839aea8e2f269bbaab9c15ba7607da0d57fe253fb061"
    ),
    "implementation_authority_single_use_consumed": True,
    "integration_commit": "7df72e2d49bbc25580d4dcb63bc1a183120bba77",
    "integration_parents": [
        "2707996e0616885fa51da9b908764f017a67299f",
        "2a26de5b99886922240350fadefa07bc8f4c5dcd",
    ],
    "integration_tree": "7fc4786b814d81d97e8672bcae484c07e180f04a",
    "local_t05_specification_exercised": True,
    "local_t06_specification_exercised": False,
    "manifest_path": PREDECESSOR_MANIFEST_PATH,
    "manifest_raw_sha256": (
        "bd0cca68c7edf8d992a7ec27cb4c700cd97cf61c4a2557ad56aca5f996a6744b"
    ),
    "receipt_content_sha256": (
        "899a27ce565d0a8159334513edba2c166b6b6d56f8b74587a6d5e89be6408715"
    ),
    "signer_role_scope_authorization_implemented": False,
    "source_commit": "2a26de5b99886922240350fadefa07bc8f4c5dcd",
    "source_parent": "61585e655f7bfd537f8a123141e4e39a590a66d8",
    "source_tree": "596c6b7d8bdf18b844c6e24a664213fc23fd9772",
    "t06_semantic_specification_path": T06_SEMANTIC_SPECIFICATION_PATH,
    "t06_semantic_specification_raw_sha256": (
        "3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6"
    ),
}

DECISION_PROVENANCE = {
    "budget_cap_source": "FAIL_CLOSED_ZERO_DEFAULT_UNDER_REVERSIBLE_AUTONOMY",
    "decision_time_utc": "NONE",
    "directive_observed_in_owner_session": True,
    "directive_semantics": (
        "CONTINUE_NEXT_BOUNDED_SIGNER_ROLE_SCOPE_AUTHORIZATION_DECISION_UNIT"
    ),
    "explicit_credential_authority_observed": False,
    "explicit_endpoint_authority_observed": False,
    "explicit_production_runtime_authority_observed": False,
    "explicit_production_signer_authority_observed": False,
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

COMMON_SCOPE = {
    "evidence_class": "SYNTHETIC_PRODUCTION_EVIDENCE_ENVELOPE_KAT",
    "owner_class": "SYNTHETIC_KAT_EVIDENCE_REVIEW_OWNER_CLASS_V1",
}

SYNTHETIC_AUTHORIZATION_PROFILES = [
    {
        "authorization_policy_revision": (
            "KAT_MANAGED_SIGNER_ROLE_SCOPE_AUTHORIZATION_POLICY_REVISION_1"
        ),
        "audience": (
            "AB_TRACK_B_MANAGED_FAULT_INJECTION_RUNNER_ISOLATED_LAB_"
            "AUTHORIZATION_KAT_V1"
        ),
        "declared_role_class": "SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY",
        "effect": "ALLOW",
        "evidence_class": COMMON_SCOPE["evidence_class"],
        "frame_sha256": (
            "e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295"
        ),
        "grant_id": "KAT_MANAGED_SIGNER_ROLE_SCOPE_GRANT_V1",
        "nonce_scope": "KAT_MANAGED_SIGNER_ROLE_SCOPE_NONCE_V1_0001",
        "owner_class": COMMON_SCOPE["owner_class"],
        "predecessor_receipt_content_sha256": (
            "46a923e510a29ed144d0de092b8346585a4a857e009d042bb68da1003f681803"
        ),
        "revocation_snapshot_revision": (
            "KAT_MANAGED_REVOCATION_SNAPSHOT_REVISION_1"
        ),
        "signer_key_id": "KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER_V2",
        "signer_key_version": "KAT_MANAGED_LEAF_KEY_VERSION_2",
        "signer_role": "KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER",
        "subject": "KAT_MANAGED_VALID_MINIMAL_FRAME_SUBJECT_V1",
        "track_id": "MANAGED_SPANNER_CLOUD_KMS",
        "trust_policy_sha256": (
            "882f37d4862ed83bb8d91b218dec8c9b40861b35e3785620f873d9250f9d51b0"
        ),
        "vector_set_id": (
            "KAT_MANAGED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1"
        ),
    },
    {
        "authorization_policy_revision": (
            "KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_AUTHORIZATION_POLICY_REVISION_1"
        ),
        "audience": (
            "AB_TRACK_B_SELF_HOSTED_FAULT_INJECTION_RUNNER_ISOLATED_LAB_"
            "AUTHORIZATION_KAT_V1"
        ),
        "declared_role_class": "SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY",
        "effect": "ALLOW",
        "evidence_class": COMMON_SCOPE["evidence_class"],
        "frame_sha256": (
            "da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e"
        ),
        "grant_id": "KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_GRANT_V1",
        "nonce_scope": "KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_NONCE_V1_0001",
        "owner_class": COMMON_SCOPE["owner_class"],
        "predecessor_receipt_content_sha256": (
            "72d1e5c86fc99027427c78f1b2792d51e02461a6cc9b120f1d8baf877472e1c1"
        ),
        "revocation_snapshot_revision": (
            "KAT_SELF_HOSTED_REVOCATION_SNAPSHOT_REVISION_1"
        ),
        "signer_key_id": "KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER_V2",
        "signer_key_version": "KAT_SELF_HOSTED_LEAF_KEY_VERSION_2",
        "signer_role": "KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER",
        "subject": "KAT_SELF_HOSTED_VALID_MINIMAL_FRAME_SUBJECT_V1",
        "track_id": "SELF_HOSTED_ETCD_OPENBAO",
        "trust_policy_sha256": (
            "882f37d4862ed83bb8d91b218dec8c9b40861b35e3785620f873d9250f9d51b0"
        ),
        "vector_set_id": (
            "KAT_SELF_HOSTED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1"
        ),
    },
]

AUTHORIZED_COMPONENT_CONTRACT = {
    "authorization_model": {
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
    "input_topology": {
        "authorization_policy_may_be_sourced_from_bundle": False,
        "authorization_policy_may_be_sourced_from_frame": False,
        "authorization_policy_may_be_sourced_from_request": False,
        "authorization_request_observed_after_policy": True,
        "caller_supplied_predecessor_receipt_allowed": False,
        "predecessor_reviewer_call_count_per_success": 1,
        "production_and_unknown_mode_rejected_before_any_input_observation": True,
        "public_input_tuple": [
            "frame",
            "detached_authentication_bundle",
            "separately_injected_synthetic_trust_policy",
            "separately_injected_synthetic_signer_authorization_policy",
            "detached_authorization_request",
            "mode",
        ],
        "review_order": [
            "MODE_PREOBSERVATION_GUARD",
            "T05_BOOTSTRAP_TRUST_AUTHENTICATION_REVIEW",
            "SEPARATE_SIGNER_AUTHORIZATION_POLICY_REVIEW",
            "DETACHED_AUTHORIZATION_REQUEST_REVIEW",
        ],
        "signer_identity_source": "T05_PREDECESSOR_RECEIPT_ONLY",
    },
    "local_scope": {
        "authorized_candidate_surface_component_count": 1,
        "authorized_candidate_surface_components": [
            "SIGNER_ROLE_SCOPE_AUTHORIZATION_SYNTHETIC_VERIFIER"
        ],
        "authorized_local_threat_specification_count": 1,
        "authorized_local_threat_specifications": ["T06"],
        "candidate_surface_components_implemented_by_decision": 0,
        "production_ingestion_control_implemented_by_authorization": False,
        "target_production_control": "SIGNER_ROLE_SCOPE_AUTHORIZATION",
    },
    "nonce_boundary": {
        "fixed_public_kat_equality_only": True,
        "freshness_proved": False,
        "generation_authorized": False,
        "single_use_proved": False,
        "t09_durable_replay_cas_implemented": False,
    },
    "output_boundary": {
        "evidence_acceptance_authorized": False,
        "output_or_claim_authorized": False,
        "successful_component_state": (
            "AUTHORIZED_SYNTHETIC_KAT_SIGNER_FOR_EXACT_FROZEN_ROLE_SCOPE_"
            "COMPONENT_ONLY"
        ),
    },
    "policy_profile": {
        "authorization_profiles": SYNTHETIC_AUTHORIZATION_PROFILES,
        "authorization_registry_is_production_policy": False,
        "profile_count": 2,
        "profile_order": [
            "MANAGED_SPANNER_CLOUD_KMS",
            "SELF_HOSTED_ETCD_OPENBAO",
        ],
        "request_scope_fields": [
            "owner_class",
            "evidence_class",
            "track_id",
            "subject",
            "audience",
            "nonce_scope",
        ],
        "request_signer_fields_forbidden": [
            "declared_role_class",
            "predecessor_receipt_content_sha256",
            "signer_key_id",
            "signer_key_version",
            "signer_role",
        ],
        "scope_dimension_count": 6,
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
    "scope_truth_boundary": {
        "audience_is_authenticated_runtime_consumer": False,
        "owner_class_is_authenticated_owner_identity": False,
        "subject_label_truth_proved": False,
        "t07_track_profile_binding_implemented": False,
        "t08_end_to_end_subject_binding_implemented": False,
        "track_is_provider_profile_currentness": False,
    },
}

ALLOWED_OPERATIONS = [
    "ADD_CLOSED_WORLD_SYNTHETIC_SIGNER_AUTHORIZATION_POLICY_REQUEST_AND_RECEIPT_SCHEMAS",
    "ADD_EXACT_TWO_PROFILE_DEFAULT_DENY_AUTHORIZATION_REGISTRY_KATS",
    "ADD_PURE_SIGNER_ROLE_SCOPE_REFERENCE_VERIFIER_FOR_FIXED_PUBLIC_ONLY_KATS",
    "COMPOSE_EXACTLY_ONCE_WITH_FROZEN_T05_PREDECESSOR_PUBLIC_REVIEW_API",
    "BIND_T05_SIGNER_TUPLE_AND_RECEIPT_TO_EXACT_SIX_DIMENSION_SYNTHETIC_SCOPE",
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
]

IMPLEMENTATION_AUTHORITY = {
    "allowed_operations": ALLOWED_OPERATIONS,
    "authority_class": "REVERSIBLE_CODE_SCHEMA_TEST_DOCUMENTATION_ONLY",
    "authorized_candidate_surface_component_count": 1,
    "authorized_local_threat_specifications": ["T06"],
    "current_state": CURRENT_STATE,
    "default_off_required": True,
    "effective_only_after_integrated_full_gate": True,
    "exact_next_unit_authorized": True,
    "forbidden_operations": FORBIDDEN_OPERATIONS,
    "implementation_authority_recorded": True,
    "implementation_scope": (
        "SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_CODE_ONLY_EXACT_NEXT_"
        "UNIT_SINGLE_USE_NON_TRANSITIVE"
    ),
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
    "resource_scope_id": (
        "EXISTING_LOCAL_WORKTREE_PRIVATE_SCRATCH_LOCAL_COMPUTE_AND_COMMITTED_"
        "PUBLIC_ONLY_T05_AND_T06_SYNTHETIC_KATS"
    ),
    "signing_or_key_generation_authorized": False,
    "test_data_scope": (
        "COMMITTED_NONSECRET_PUBLIC_ONLY_SYNTHETIC_KAT_NO_SEEDS_NO_PRIVATE_KEYS"
    ),
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
        "event": "OWNER_CONTINUES_NEXT_BOUNDED_SIGNER_ROLE_SCOPE_DECISION_PATH",
        "from_state": "UNRECORDED_NO_AUTHORITY",
        "to_state": CURRENT_STATE,
    },
    {
        "event": "OWNER_HOLDS_OR_REJECTS",
        "from_state": "UNRECORDED_NO_AUTHORITY",
        "to_state": "REJECTED_FAIL_CLOSED",
    },
    {
        "event": "EXACT_AUTHORIZED_T06_SUCCESSOR_INTEGRATED_AND_FULL_GATE_PASSES",
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
    "authorized_future_local_threat_specifications": ["T06"],
    "bootstrap_trust_authentication_isolated_lab_implemented": True,
    "current_decision_candidate_surface_components_implemented": 0,
    "downstream_gate_count": 4,
    "downstream_gates_authorized": 0,
    "effective_only_after_integrated_full_gate": True,
    "exact_next_unit_authorized": True,
    "future_successor_candidate_surface_component_total": 4,
    "future_successor_candidate_surface_components_authorized": 1,
    "future_successor_minimum_independent_reviewer_lane_count": 2,
    "implementation_authority_recorded": True,
    "implementation_resource_binding_recorded": True,
    "implementation_scope_decision_recorded": True,
    "implementation_side_effects_unlocked": IMPLEMENTATION_SIDE_EFFECTS,
    "isolated_lab_predecessor_surface_component_total": 3,
    "isolated_lab_predecessor_surface_components_implemented": 3,
    "local_predecessor_threat_specifications_covered": 5,
    "local_t06_specification_exercised": False,
    "local_t07_specification_exercised": False,
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
    "signer_role_scope_authorization_isolated_lab_implementation_authorized": True,
    "signer_role_scope_authorization_isolated_lab_implemented": False,
    "track_subject_binding_implemented": False,
}

NONCLAIMS = {
    "action_or_resource_capability_authorized": False,
    "any_production_ingestion_control_implemented": False,
    "application_claim_authorized": False,
    "audience_identity_authenticated": False,
    "authorization_policy_is_production_policy": False,
    "budget_cap_zero_is_budget_reservation": False,
    "condition_output_authorized": False,
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
    "local_t06_kat_is_production_mitigation": False,
    "nonce_freshness_proved": False,
    "nonce_generation_authorized": False,
    "nonce_replay_protection_proved": False,
    "nonce_single_use_proved": False,
    "output_permit_defined": False,
    "owner_class_is_authenticated_owner_identity": False,
    "owner_signature_observed": False,
    "paid_resource_provisioned": False,
    "predecessor_receipt_is_caller_supplied": False,
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
    "production_signer_authorization_implemented": False,
    "provider_authority": False,
    "provider_called": False,
    "real_evidence_accepted": False,
    "real_evidence_collected": False,
    "real_evidence_ingested": False,
    "real_evidence_present": False,
    "real_evidence_validated": False,
    "role_or_group_inheritance_implemented": False,
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
    "signer_role_scope_authorization_implemented": False,
    "signing_or_key_generation_authorized": False,
    "subject_label_truth_proved": False,
    "t07_track_profile_binding_implemented": False,
    "t08_end_to_end_subject_binding_implemented": False,
    "t09_replay_cas_implemented": False,
    "track_is_provider_profile_currentness": False,
    "track_subject_binding_implemented": False,
    "trusted_production_time_bound": False,
    "wildcard_prefix_or_hierarchy_authorization_implemented": False,
    "wire_attempted": False,
}

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
    "boundary",
    "decision_provenance",
    "implementation_authority",
    "nonclaims",
    "owner_implementation_actor",
    "resource_binding",
    "rollback",
    "state_machine",
)
SECTION_HASH_KEYS = tuple(
    f"{section_name}_sha256" for section_name in HASHED_SECTION_NAMES
)


class SignerRoleScopeAuthorityDecisionReviewError(ValueError):
    """Fail-closed decision-review error carrying a stable reason code."""


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise SignerRoleScopeAuthorityDecisionReviewError(f"{code}: {message}")


def exact_keys(value: Mapping[str, Any], expected: Iterable[str], code: str) -> None:
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
            exact_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return bool(left == right)


def _clone(value: Any) -> Any:
    if type(value) is dict:
        return {key: _clone(item) for key, item in value.items()}
    if type(value) is list:
        return [_clone(item) for item in value]
    return value


def _validate_json_value(value: Any, depth: int = 0) -> None:
    require(depth <= 64, "E_JSON_DEPTH", "value nesting exceeds 64")
    require(type(value) is not float, "E_JSON_FLOAT", "floats are forbidden")
    if type(value) is int:
        require(-(2**63) <= value <= 2**63 - 1, "E_JSON_INTEGER", "out of range")
        return
    if type(value) in (str, bool) or value is None:
        return
    if type(value) is list:
        for item in value:
            _validate_json_value(item, depth + 1)
        return
    require(type(value) is dict, "E_JSON_TYPE", "unsupported JSON value type")
    for key, item in value.items():
        require(type(key) is str, "E_JSON_KEY", "object key is not a string")
        _validate_json_value(item, depth + 1)


def canonical_bytes(value: Any) -> bytes:
    """Return strict sorted compact UTF-8 JSON bytes for an in-memory value."""

    _validate_json_value(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def domain_sha256(domain: str, value: Any) -> str:
    """Hash a canonical value under one exact ASCII domain."""

    require(type(domain) is str and domain.isascii(), "E_HASH_DOMAIN", "invalid domain")
    return hashlib.sha256(
        domain.encode("ascii") + b"\0" + canonical_bytes(value)
    ).hexdigest()


def expected_section_hashes(record: Mapping[str, Any]) -> dict[str, str]:
    return {
        f"{section_name}_sha256": domain_sha256(
            DOMAIN_PREFIXES[section_name], record[section_name]
        )
        for section_name in HASHED_SECTION_NAMES
    }


def build_owner_decision_record() -> dict[str, Any]:
    """Build the one exact owner decision record without performing I/O."""

    record: dict[str, Any] = {
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
    predecessor = record["predecessor"]
    authority = record["implementation_authority"]
    component = record["authorized_component_contract"]
    resources = record["resource_binding"]
    boundary = record["boundary"]
    state = record["state_machine"]

    require(
        predecessor["authorization_consumption_state"] == "CONSUMED_SCOPE_COMPLETE"
        and predecessor["implementation_authority_single_use_consumed"] is True
        and predecessor["bootstrap_trust_authentication_implemented"] is True
        and predecessor["signer_role_scope_authorization_implemented"] is False,
        "E_PREDECESSOR_AUTHORITY",
        "T05 predecessor consumption or T06 boundary drift",
    )
    require(
        predecessor["manifest_path"] == PREDECESSOR_MANIFEST_PATH
        and predecessor["manifest_path"] in predecessor["artifact_raw_sha256"]
        and len(predecessor["artifact_raw_sha256"]) == 8
        and predecessor["t06_semantic_specification_path"]
        == T06_SEMANTIC_SPECIFICATION_PATH,
        "E_PREDECESSOR_IDENTITY",
        "protected predecessor or T06 semantic specification drift",
    )
    require(
        authority["effective_only_after_integrated_full_gate"] is True
        and state["decision_full_gate_consumes_new_authority"] is False
        and authority["non_transitive"] is True
        and authority["subdelegation_authorized"] is False
        and authority["runtime_import_authorized"] is False,
        "E_AUTHORITY_SCOPE",
        "authority activation, transitivity, or runtime boundary drift",
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
        and topology["production_and_unknown_mode_rejected_before_any_input_observation"]
        is True
        and topology["caller_supplied_predecessor_receipt_allowed"] is False
        and topology["signer_identity_source"] == "T05_PREDECESSOR_RECEIPT_ONLY"
        and topology["predecessor_reviewer_call_count_per_success"] == 1
        and topology["authorization_policy_may_be_sourced_from_bundle"] is False
        and topology["authorization_policy_may_be_sourced_from_frame"] is False
        and topology["authorization_policy_may_be_sourced_from_request"] is False,
        "E_INPUT_TOPOLOGY",
        "six-input, predecessor, or policy-separation contract drift",
    )
    model = component["authorization_model"]
    require(
        model["default_effect"] == "DENY"
        and model["allow_grant_count"] == 2
        and model["wildcards_allowed"] is False
        and model["prefix_match_allowed"] is False
        and model["hierarchical_match_allowed"] is False
        and model["role_inheritance_allowed"] is False
        and model["group_inheritance_allowed"] is False
        and model["deny_on_zero_matches"] is True
        and model["deny_on_multiple_matches"] is True,
        "E_DEFAULT_DENY",
        "closed-world default-deny authorization model drift",
    )
    policy = component["policy_profile"]
    profiles = policy["authorization_profiles"]
    require(
        type(profiles) is list
        and len(profiles) == 2
        and policy["profile_count"] == 2
        and [profile["track_id"] for profile in profiles]
        == policy["profile_order"]
        == ["MANAGED_SPANNER_CLOUD_KMS", "SELF_HOSTED_ETCD_OPENBAO"]
        and policy["scope_dimension_count"] == 6,
        "E_AUTHORIZATION_PROFILE",
        "two-track authorization profile identity, order, or scope count drift",
    )
    critical_sets: list[set[str]] = []
    for profile in profiles:
        require(
            profile["effect"] == "ALLOW"
            and profile["owner_class"] == COMMON_SCOPE["owner_class"]
            and profile["evidence_class"] == COMMON_SCOPE["evidence_class"],
            "E_AUTHORIZATION_GRANT",
            "grant effect or common synthetic scope drift",
        )
        for field in (
            "grant_id",
            "signer_key_id",
            "signer_key_version",
            "signer_role",
            "declared_role_class",
            "track_id",
            "subject",
            "audience",
            "nonce_scope",
            "authorization_policy_revision",
            "vector_set_id",
            "revocation_snapshot_revision",
        ):
            value = profile[field]
            require(
                type(value) is str
                and value
                and value.isascii()
                and value == value.strip()
                and len(value.encode("utf-8")) <= 256
                and "*" not in value,
                "E_SCOPE_VALUE",
                field,
            )
        critical_sets.append(
            {
                profile["grant_id"],
                profile["signer_key_id"],
                profile["signer_key_version"],
                profile["signer_role"],
                profile["track_id"],
                profile["subject"],
                profile["audience"],
                profile["nonce_scope"],
                profile["authorization_policy_revision"],
                profile["vector_set_id"],
                profile["revocation_snapshot_revision"],
                profile["frame_sha256"],
                profile["predecessor_receipt_content_sha256"],
            }
        )
    require(
        critical_sets[0].isdisjoint(critical_sets[1]),
        "E_TRACK_SUBSTITUTION",
        "managed and self-hosted authorization values overlap",
    )
    truth = component["scope_truth_boundary"]
    nonce = component["nonce_boundary"]
    require(
        all(value is False for value in truth.values())
        and nonce["fixed_public_kat_equality_only"] is True
        and nonce["freshness_proved"] is False
        and nonce["single_use_proved"] is False
        and nonce["t09_durable_replay_cas_implemented"] is False,
        "E_SCOPE_TRUTH_OR_REPLAY",
        "scope labels or nonce equality were promoted to truth/replay claims",
    )
    reviewer = component["reviewer_topology"]
    require(
        reviewer["minimum_independent_reviewer_lane_count"] >= 2
        and reviewer["lane_identity_distinctness_required"] is True
        and reviewer["production_security_reviewer_binding"] == "NONE",
        "E_REVIEWER_TOPOLOGY",
        "future reviewer topology drift",
    )
    require(
        resources["component_runtime_network"] is False
        and resources["provider_endpoints"] == []
        and resources["credential_handles"] == []
        and resources["credential_paths"] == []
        and resources["effective_external_paid_spend_cap"] == 0
        and resources["private_key_or_seed_material_authorized"] is False
        and resources["signing_or_key_generation_authorized"] is False
        and resources["component_limits"]["max_authorization_grants"] == 2
        and resources["component_limits"]["max_parallel_workers"] == 1,
        "E_RESOURCE_AUTHORITY",
        "resource, secret, signing, network, or cardinality authority drift",
    )
    require(
        boundary["isolated_lab_predecessor_surface_components_implemented"] == 3
        and boundary["local_predecessor_threat_specifications_covered"] == 5
        and boundary["authorized_future_local_threat_specifications"] == ["T06"]
        and boundary["signer_role_scope_authorization_isolated_lab_implemented"]
        is False
        and boundary["local_t06_specification_exercised"] is False
        and boundary["local_t07_specification_exercised"] is False
        and boundary["track_subject_binding_implemented"] is False
        and boundary["production_ingestion_controls_implemented"] == 0,
        "E_CONTROL_ACCOUNTING",
        "decision, T06/T07, or production control accounting drift",
    )
    require(
        all(value is False for value in record["nonclaims"].values()),
        "E_NONCLAIM",
        "a denied claim became positive",
    )


def review_decision(record: Mapping[str, Any]) -> dict[str, Any]:
    """Review one exact in-memory record and return a deterministic receipt."""

    _validate_json_value(record)
    exact_keys(record, TOP_LEVEL_KEYS, "E_RECORD_KEYS")
    expected_record = build_owner_decision_record()
    for scalar_key in (
        "date",
        "decision",
        "next_unit",
        "schema",
        "schema_version",
        "status",
    ):
        require(
            exact_equal(record[scalar_key], expected_record[scalar_key]),
            "E_RECORD_IDENTITY",
            f"{scalar_key} drift",
        )
    for section_name in (
        "authorized_component_contract",
        "boundary",
        "decision_provenance",
        "implementation_authority",
        "nonclaims",
        "owner_implementation_actor",
        "predecessor",
        "resource_binding",
        "rollback",
        "state_machine",
    ):
        require(
            exact_equal(record[section_name], expected_record[section_name]),
            "E_SECTION",
            f"{section_name} drift",
        )
    exact_keys(record["section_sha256"], SECTION_HASH_KEYS, "E_SECTION_HASH_KEYS")
    expected_hashes = expected_section_hashes(record)
    require(
        exact_equal(record["section_sha256"], expected_hashes),
        "E_SECTION_HASH",
        "section hash drift",
    )
    _validate_semantic_boundaries(record)

    decision_record_sha256 = domain_sha256(
        DOMAIN_PREFIXES["decision_record"], record
    )
    receipt: dict[str, Any] = {
        "all_nonclaims_explicit": True,
        "allowed_operation_count": len(ALLOWED_OPERATIONS),
        "authorization_effective_only_after_integrated_full_gate": True,
        "authorization_profile_count": len(SYNTHETIC_AUTHORIZATION_PROFILES),
        "authorized_candidate_surface_component_count": 1,
        "authorized_component_contract_sha256": expected_hashes[
            "authorized_component_contract_sha256"
        ],
        "authorized_local_threat_specification_count": 1,
        "authorized_local_threat_specifications": "T06",
        "bootstrap_trust_authentication_implemented": True,
        "boundary_sha256": expected_hashes["boundary_sha256"],
        "component_runtime_network": False,
        "content_sha256": "0" * 64,
        "current_decision_candidate_surface_components_implemented": 0,
        "current_state": CURRENT_STATE,
        "date": DATE,
        "decision": DECISION,
        "decision_record_sha256": decision_record_sha256,
        "default_effect": "DENY",
        "downstream_gates_authorized": 0,
        "external_paid_spend_cap": 0,
        "forbidden_operation_count": len(FORBIDDEN_OPERATIONS),
        "future_successor_candidate_surface_component_total": 4,
        "future_successor_candidate_surface_components_authorized": 1,
        "future_successor_minimum_independent_reviewer_lane_count": 2,
        "global_single_use_proved": False,
        "implementation_authority_recorded": True,
        "implementation_authority_sha256": expected_hashes[
            "implementation_authority_sha256"
        ],
        "implementation_authority_single_use_consumed": False,
        "implementation_resource_binding_recorded": True,
        "implementation_scope_decision_recorded": True,
        "implementation_side_effects_unlocked": IMPLEMENTATION_SIDE_EFFECTS,
        "isolated_lab_predecessor_surface_components_implemented": 3,
        "local_predecessor_threat_specifications_covered": 5,
        "local_t06_specification_exercised": False,
        "local_t07_specification_exercised": False,
        "mode": MODE,
        "next_unit": NEXT_UNIT,
        "nonclaim_field_count": len(NONCLAIMS),
        "nonclaims_sha256": expected_hashes["nonclaims_sha256"],
        "nonce_freshness_proved": False,
        "nonce_replay_protection_proved": False,
        "owner_cryptographic_identity_verified": False,
        "owner_semantic_actor_binding_recorded": True,
        "owner_semantic_actor_label": OWNER_IMPLEMENTATION_ACTOR[
            "semantic_actor_label"
        ],
        "owner_signature_observed": False,
        "owner_supplied_numeric_budget_cap": False,
        "predecessor_authorization_consumption_state": "CONSUMED_SCOPE_COMPLETE",
        "predecessor_implementation_authority_single_use_consumed": True,
        "predecessor_integration_commit": PREDECESSOR["integration_commit"],
        "predecessor_receipt_content_sha256": PREDECESSOR[
            "receipt_content_sha256"
        ],
        "production_environment_implementation_authorized": False,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "production_ingestion_enabled": False,
        "production_ingestion_implemented": False,
        "production_security_reviewer_bound": False,
        "production_validated_evidence_items": 0,
        "provider_authority": False,
        "provider_endpoint_count": 0,
        "public_input_count": COMPONENT_LIMITS["public_input_count"],
        "real_evidence_items_present": 0,
        "request_scope_dimension_count": 6,
        "resource_binding_sha256": expected_hashes["resource_binding_sha256"],
        "rollback_sha256": expected_hashes["rollback_sha256"],
        "runtime_admission_granted": False,
        "runtime_admission_ready": False,
        "runtime_authority": False,
        "runtime_evidence_accepted": 0,
        "runtime_owner_decision_recorded": False,
        "runtime_owner_identity_bound": False,
        "runtime_prerequisites_satisfied": 0,
        "runtime_side_effects_unlocked": "NONE",
        "schema": RECEIPT_SCHEMA,
        "signer_role_scope_authorization_implemented": False,
        "state_machine_sha256": expected_hashes["state_machine_sha256"],
        "status": STATUS,
        "t06_semantic_specification_raw_sha256": PREDECESSOR[
            "t06_semantic_specification_raw_sha256"
        ],
        "track_subject_binding_implemented": False,
        "wildcards_allowed": False,
    }
    receipt_without_hash = dict(receipt)
    del receipt_without_hash["content_sha256"]
    receipt["content_sha256"] = domain_sha256(
        DOMAIN_PREFIXES["receipt"], receipt_without_hash
    )
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
    "authorization_profile_count",
    "default_effect",
    "wildcards_allowed",
    "request_scope_dimension_count",
    "public_input_count",
    "bootstrap_trust_authentication_implemented",
    "signer_role_scope_authorization_implemented",
    "track_subject_binding_implemented",
    "local_t06_specification_exercised",
    "local_t07_specification_exercised",
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
    "nonce_freshness_proved",
    "nonce_replay_protection_proved",
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
    "t06_semantic_specification_raw_sha256",
    "content_sha256",
)


def render_tsv(receipt: Mapping[str, Any]) -> str:
    """Render the exact scalar receipt as deterministic TSV."""

    exact_keys(receipt, TSV_FIELDS, "E_RECEIPT_KEYS")
    lines: list[str] = []
    for field in TSV_FIELDS:
        value = receipt[field]
        require(type(value) in (str, int, bool), "E_TSV_VALUE", field)
        rendered = (
            "true" if value is True else "false" if value is False else str(value)
        )
        require("\t" not in rendered and "\n" not in rendered, "E_TSV_TEXT", field)
        lines.append(f"{field}\t{rendered}")
    return "\n".join(lines) + "\n"


__all__ = [
    "ALLOWED_OPERATIONS",
    "AUTHORIZED_COMPONENT_CONTRACT",
    "COMPONENT_LIMITS",
    "CURRENT_STATE",
    "DECISION",
    "DOMAIN_PREFIXES",
    "FORBIDDEN_OPERATIONS",
    "NEXT_UNIT",
    "NONCLAIMS",
    "PREDECESSOR",
    "PREDECESSOR_MANIFEST_PATH",
    "RECEIPT_SCHEMA",
    "RECORD_SCHEMA",
    "RESOURCE_BINDING",
    "STATUS",
    "SYNTHETIC_AUTHORIZATION_PROFILES",
    "SignerRoleScopeAuthorityDecisionReviewError",
    "T06_SEMANTIC_SPECIFICATION_PATH",
    "TSV_FIELDS",
    "build_owner_decision_record",
    "canonical_bytes",
    "domain_sha256",
    "expected_section_hashes",
    "render_tsv",
    "review_decision",
]
