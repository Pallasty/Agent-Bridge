#!/usr/bin/env python3
"""Pure reviewer for the bootstrap-trust isolated-lab authority decision.

The reviewed record can authorize one exact reversible repository successor.
It never authenticates evidence, verifies a production signature, loads trust
material, or exposes a runtime/provider API.  All inputs are already in memory;
the reviewer performs no file, environment, clock, process, network, provider,
credential, randomness, entropy, or mutable-global-state I/O.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping


RECORD_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "bootstrap_trust_authentication_isolated_lab_implementation_authority_and_"
    "resource_binding_decision.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "bootstrap_trust_authentication_isolated_lab_implementation_authority_and_"
    "resource_binding_decision_v1.receipt.v0"
)
DATE = "2026-07-17"
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_"
    "AUTHENTICATION_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_SCOPE_"
    "RECORDED_ZERO_EXTERNAL_SPEND_NO_RUNTIME_OR_PROVIDER_AUTHORITY"
)
DECISION = (
    "AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_BOOTSTRAP_TRUST_AUTHENTICATION_"
    "ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED"
)
MODE = "ISOLATED_LAB_FIRST"
CURRENT_STATE = (
    "AUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT"
)
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_TRUST_CHAIN_EXACT_KEY_VERSION_"
    "DECLARED_ROLE_AND_REVOCATION_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
)
IMPLEMENTATION_SIDE_EFFECTS = (
    "REVERSIBLE_LOCAL_CODE_SCHEMA_TEST_DOCS_FOR_EXACT_NEXT_UNIT_ONLY"
)
PREDECESSOR_MANIFEST_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_runner_production_evidence_envelope_bounded_frame_parser_and_"
    "synthetic_mode_separation_isolated_lab_v1_pack_v0.json"
)

PREDECESSOR_ARTIFACT_RAW_SHA256 = {
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-v1.schema.json": (
        "e8cb4964f86de39b16d553537467006454c720dc8bfa8d36e370189627328f55"
    ),
    "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.md": (
        "a93fd00b9dc43f8b9d3717fd07bf3a2eef734724834d75d122d2e8bbbe6e3149"
    ),
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.sh": (
        "464b975d61403759221fd3aa41da4c38de12f4ec946b161100d23edadbc2b174"
    ),
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1.py": (
        "bfa3badbe2b467fbed610d5acb42ef21f1aec2ceb2d5ccf2c218fecfe438eed1"
    ),
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.py": (
        "76e0960cb9afa0e4e655ec122b600fe489a31acd5a7edf659d2fff4727ef0dcf"
    ),
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.expected.v0.tsv": (
        "775ecfa5169509a5fe0e5a900d8644f47b6b4cf64a1778c7d4ed52214115c847"
    ),
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_synthetic_v0.json": (
        "324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9"
    ),
    PREDECESSOR_MANIFEST_PATH: (
        "9c7ba09368ebd610452ca2799226c1f57dcb63fedabb0319f4b39bc071277d04"
    ),
}

PREDECESSOR = {
    "artifact_raw_sha256": PREDECESSOR_ARTIFACT_RAW_SHA256,
    "authorization_consumption_state": "CONSUMED_SCOPE_COMPLETE",
    "bootstrap_trust_authentication_authorized": False,
    "bootstrap_trust_authentication_implemented": False,
    "decision_source_baseline_commit": (
        "d0356dbdbd7239ffab972ee21da81891210a055b"
    ),
    "decision_source_baseline_parents": [
        "3bf8ad3a67ff02a4e717db8e29e89079f66c01cf",
        "20368c626bf34c5a1edd07391014ab8716536e7e",
    ],
    "decision_source_baseline_tree": (
        "b40c36c5fe73af3079bf3a81d69480d2555271d8"
    ),
    "gate_path": (
        "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-"
        "runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-"
        "mode-separation-isolated-lab-v1-pack.sh"
    ),
    "gate_raw_sha256": (
        "464b975d61403759221fd3aa41da4c38de12f4ec946b161100d23edadbc2b174"
    ),
    "implementation_authority_single_use_consumed": True,
    "integration_commit": "3bf8ad3a67ff02a4e717db8e29e89079f66c01cf",
    "integration_parents": [
        "7ef0f8e9b8048fbd1b308ca2a1d708138a615ed9",
        "e5012eb3fd6742ceaecedf4b36adbee8ecfeb054",
    ],
    "integration_tree": "1bb4b0d851bb4c1ce8a7bf91cbc489168ae41433",
    "manifest_path": PREDECESSOR_MANIFEST_PATH,
    "manifest_raw_sha256": (
        "9c7ba09368ebd610452ca2799226c1f57dcb63fedabb0319f4b39bc071277d04"
    ),
    "receipt_content_sha256": (
        "4d5752110ebf0c11197bd8667fb9e79948724f5195465e41c6709d98d6177b8c"
    ),
    "source_commit": "e5012eb3fd6742ceaecedf4b36adbee8ecfeb054",
    "source_parent": "fa0cb9f088e0da2c55c92efde860d9521d4b7493",
}

DECISION_PROVENANCE = {
    "budget_cap_source": "FAIL_CLOSED_ZERO_DEFAULT_UNDER_REVERSIBLE_AUTONOMY",
    "decision_time_utc": "NONE",
    "directive_observed_in_owner_session": True,
    "directive_semantics": (
        "CONTINUE_NEXT_BOUNDED_BOOTSTRAP_TRUST_AUTHENTICATION_DECISION_UNIT"
    ),
    "explicit_credential_authority_observed": False,
    "explicit_endpoint_authority_observed": False,
    "explicit_production_runtime_authority_observed": False,
    "explicit_production_signer_authority_observed": False,
    "explicit_production_trust_root_authority_observed": False,
    "explicit_provider_authority_observed": False,
    "latest_directive_explicitly_named_budget_cap": False,
    "latest_directive_explicitly_named_owner_label": False,
    "no_runtime_provider_or_production_trust_authority_inferred": True,
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

AUTHENTICATION_COMPONENT_STATES = [
    "UNREVIEWED_SYNTHETIC_KAT_ONLY",
    "MODE_REJECTED_FAIL_CLOSED",
    "PREDECESSOR_FRAME_REJECTED_FAIL_CLOSED",
    "TRUST_POLICY_REJECTED_FAIL_CLOSED",
    "AUTHENTICATION_REJECTED_FAIL_CLOSED",
    "AUTHENTICATED_SYNTHETIC_KAT_AGAINST_FROZEN_BOOTSTRAP_TRUST_SNAPSHOT_COMPONENT_ONLY",
]

SYNTHETIC_TRACK_PROFILES = [
    {
        "exact_chain_order": [
            "KAT_MANAGED_BOOTSTRAP_ROOT_V1",
            "KAT_MANAGED_TRUST_POLICY_ISSUER_V1",
            "KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER_V2",
        ],
        "issuer": {
            "key_id": "KAT_MANAGED_TRUST_POLICY_ISSUER_V1",
            "key_version": "KAT_MANAGED_ISSUER_KEY_VERSION_1",
            "role": "KAT_MANAGED_TRUST_POLICY_ISSUER",
        },
        "leaf": {
            "active_key_version": "KAT_MANAGED_LEAF_KEY_VERSION_2",
            "key_id": "KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER_V2",
            "revoked_key_version": "KAT_MANAGED_LEAF_KEY_VERSION_1",
            "role": "KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER",
        },
        "policy_revision": "KAT_MANAGED_TRUST_POLICY_REVISION_1",
        "public_only_precomputed_vector_set_id": (
            "KAT_MANAGED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1"
        ),
        "revocation_snapshot_revision": (
            "KAT_MANAGED_REVOCATION_SNAPSHOT_REVISION_1"
        ),
        "root": {
            "key_id": "KAT_MANAGED_BOOTSTRAP_ROOT_V1",
            "key_version": "KAT_MANAGED_ROOT_KEY_VERSION_1",
            "role": "KAT_MANAGED_BOOTSTRAP_ROOT",
        },
        "signature_domain": (
            "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_MANAGED_"
            "KAT_SIGNATURE_V1"
        ),
        "track_id": "MANAGED_SPANNER_CLOUD_KMS",
    },
    {
        "exact_chain_order": [
            "KAT_SELF_HOSTED_BOOTSTRAP_ROOT_V1",
            "KAT_SELF_HOSTED_TRUST_POLICY_ISSUER_V1",
            "KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER_V2",
        ],
        "issuer": {
            "key_id": "KAT_SELF_HOSTED_TRUST_POLICY_ISSUER_V1",
            "key_version": "KAT_SELF_HOSTED_ISSUER_KEY_VERSION_1",
            "role": "KAT_SELF_HOSTED_TRUST_POLICY_ISSUER",
        },
        "leaf": {
            "active_key_version": "KAT_SELF_HOSTED_LEAF_KEY_VERSION_2",
            "key_id": "KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER_V2",
            "revoked_key_version": "KAT_SELF_HOSTED_LEAF_KEY_VERSION_1",
            "role": "KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER",
        },
        "policy_revision": "KAT_SELF_HOSTED_TRUST_POLICY_REVISION_1",
        "public_only_precomputed_vector_set_id": (
            "KAT_SELF_HOSTED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1"
        ),
        "revocation_snapshot_revision": (
            "KAT_SELF_HOSTED_REVOCATION_SNAPSHOT_REVISION_1"
        ),
        "root": {
            "key_id": "KAT_SELF_HOSTED_BOOTSTRAP_ROOT_V1",
            "key_version": "KAT_SELF_HOSTED_ROOT_KEY_VERSION_1",
            "role": "KAT_SELF_HOSTED_BOOTSTRAP_ROOT",
        },
        "signature_domain": (
            "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_SELF_"
            "HOSTED_KAT_SIGNATURE_V1"
        ),
        "track_id": "SELF_HOSTED_ETCD_OPENBAO",
    },
]

AUTHORIZED_COMPONENT_CONTRACT = {
    "algorithm_profile": {
        "algorithm": "ED25519",
        "external_prehash_allowed": False,
        "public_key_encoding": "RAW_32_BYTE_RFC8032_CANONICAL_POINT",
        "public_key_prime_subgroup_required": True,
        "signature_encoding": "RAW_64_BYTE_RFC8032_CANONICAL_R_AND_SCALAR",
        "signature_message_profile": (
            "U64BE_LENGTH_PREFIXED_ASCII_DOMAIN_AND_EXACT_PREDECESSOR_CANONICAL_"
            "FRAME_BYTES_NO_PARSE_RESERIALIZE"
        ),
        "signature_scheme": "ED25519_PURE_RFC8032_NO_CONTEXT_NO_PREHASH",
        "signature_scalar_less_than_group_order_required": True,
        "small_order_or_identity_points_rejected": True,
    },
    "authentication_state_ceiling": {
        "production_success_state_representable": False,
        "states": AUTHENTICATION_COMPONENT_STATES,
        "successful_state": AUTHENTICATION_COMPONENT_STATES[-1],
    },
    "input_topology": {
        "authentication_metadata_detached": True,
        "production_and_unknown_mode_rejected_before_any_input_observation": True,
        "public_input_tuple": [
            "frame",
            "detached_authentication_bundle",
            "separately_injected_synthetic_trust_policy",
            "mode",
        ],
        "trust_policy_may_be_sourced_from_authentication_bundle": False,
        "trust_policy_may_be_sourced_from_envelope": False,
    },
    "local_scope": {
        "authorized_candidate_surface_component_count": 1,
        "authorized_candidate_surface_components": [
            "BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_VERIFIER"
        ],
        "authorized_local_threat_specification_count": 1,
        "authorized_local_threat_specifications": ["T05"],
        "candidate_surface_component_total": 1,
        "candidate_surface_components_implemented_by_decision": 0,
        "local_threat_specification_total": 1,
        "production_ingestion_control_implemented_by_authorization": False,
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
        "reviewer_identity_binding_mode": "SEMANTIC_LABEL_BOUND_AT_REVIEW_TIME",
    },
    "role_boundary": {
        "declared_role": "SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY",
        "declared_role_cryptographically_authenticated_in_kat": True,
        "declared_role_is_role_scope_authorization": False,
        "declared_role_source": "EXACT_SYNTHETIC_TRACK_PROFILE_LEAF_ROLE",
        "signer_role_scope_authorization_control_implemented": False,
        "track_subject_binding_control_implemented": False,
    },
    "synthetic_track_profiles": SYNTHETIC_TRACK_PROFILES,
    "trust_chain_profile": {
        "exact_positive_key_version_required": True,
        "latest_or_zero_key_version_allowed": False,
        "maximum_chain_entries": 3,
        "maximum_trust_roots": 2,
        "root_injection_from_untrusted_bundle_allowed": False,
        "separately_injected_trust_policy_required": True,
        "trust_on_first_use_allowed": False,
    },
    "trust_domain_family": (
        "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_KAT_"
        "SIGNATURE_FAMILY_V1"
    ),
    "revocation_profile": {
        "active_state": "ACTIVE_AT_EXACT_FROZEN_SYNTHETIC_REVISION",
        "frozen_snapshot_is_currentness": False,
        "revocation_source": "SEPARATELY_INJECTED_FROZEN_SYNTHETIC_TRUST_POLICY",
        "revoked_state": "REVOKED_AT_OR_BEFORE_EXACT_FROZEN_SYNTHETIC_REVISION",
        "self_asserted_active_state_allowed": False,
        "unknown_state": "UNKNOWN_FAIL_CLOSED",
    },
}

ALLOWED_OPERATIONS = [
    "ADD_CLOSED_WORLD_SYNTHETIC_BOOTSTRAP_TRUST_POLICY_AND_DETACHED_AUTHENTICATION_BUNDLE_SCHEMAS",
    "ADD_BOUNDED_PURE_ED25519_REFERENCE_VERIFIER_FOR_PUBLIC_ONLY_FIXED_KATS",
    "ADD_U64BE_LENGTH_PREFIXED_DOMAIN_AND_EXACT_PREDECESSOR_CANONICAL_FRAME_MESSAGE",
    "ADD_PINNED_SYNTHETIC_ROOT_CHAIN_EXACT_KEY_VERSION_DECLARED_ROLE_AND_FROZEN_REVOCATION_SNAPSHOT_CHECKS",
    "COMPOSE_WITH_FROZEN_PREDECESSOR_FRAME_REVIEW_API_IN_SYNTHETIC_MODE",
    "ADD_PREOBSERVATION_SYNTHETIC_PRODUCTION_MODE_GUARDS",
    "ADD_DETERMINISTIC_NONSECRET_PUBLIC_ONLY_ADVERSARIAL_KATS",
    "ADD_PURE_REVIEWER_INDEPENDENT_CONTRACT_AND_SECURITY_GATE_LANES_REPORT_AND_SOURCE_BOUND_GATE",
]

FORBIDDEN_OPERATIONS = [
    "ACCESS_CREDENTIAL_OR_SECRET_MATERIAL",
    "ACCEPT_OR_PERSIST_REAL_EVIDENCE",
    "ADD_CRYPTOGRAPHIC_SIGNING_KEY_GENERATION_OR_PRIVATE_SEED_API",
    "ADD_OR_FETCH_UNPINNED_CRYPTOGRAPHIC_DEPENDENCY",
    "ALLOW_LATEST_OR_ZERO_KEY_VERSION",
    "ALLOW_REVOCATION_FAIL_OPEN",
    "ALLOW_TRUST_ON_FIRST_USE_OR_UNKNOWN_ROOT",
    "AUTHORIZE_OR_INJECT_FAULT",
    "AUTHORIZE_OUTPUT_OR_CLAIM",
    "AUTHORIZE_SIGNER_ROLE_SCOPE_TRACK_SUBJECT_AUDIENCE_OR_NONCE",
    "BIND_PRODUCTION_SIGNER_KEY_VERSION_ROLE_REVOCATION_SOURCE_OR_TRUST_ROOT",
    "BIND_PROVIDER_OR_PRODUCTION_ENDPOINT",
    "CALL_PROVIDER_OR_ATTEMPT_WIRE",
    "CLAIM_FROZEN_REVOCATION_SNAPSHOT_CURRENTNESS_OR_FRESHNESS",
    "CLAIM_PRODUCTION_AUTHENTICATION_OR_PRODUCTION_MITIGATION",
    "COMMIT_PRIVATE_KEY_TEST_SEED_OR_SECRET_SHAPED_MATERIAL",
    "CREATE_RUNTIME_OR_EXPERIMENT_ROW",
    "DEPLOY_OR_ENABLE_PRODUCTION_INGESTION",
    "ESTABLISH_DURABLE_CUSTODY_OR_REPLAY_LEDGER",
    "FETCH_OR_REFRESH_TRUST_CERTIFICATE_OR_REVOCATION_DATA",
    "LAUNCH_RUNNER_OR_BACKGROUND_DAEMON",
    "PERSIST_AUTHENTICATED_EVIDENCE_OR_TRUST_MATERIAL",
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
    "authorized_local_threat_specifications": ["T05"],
    "current_state": CURRENT_STATE,
    "default_off_required": True,
    "effective_only_after_integrated_full_gate": True,
    "exact_next_unit_authorized": True,
    "forbidden_operations": FORBIDDEN_OPERATIONS,
    "implementation_authority_recorded": True,
    "implementation_scope": (
        "BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_CODE_ONLY_EXACT_NEXT_UNIT_"
        "SINGLE_USE_NON_TRANSITIVE"
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
    "max_authentication_bundle_bytes": 65536,
    "max_chain_entries": 3,
    "max_input_frame_bytes": 1048576,
    "max_json_depth": 32,
    "max_json_nodes": 4096,
    "max_object_members": 256,
    "max_parallel_workers": 1,
    "max_private_scratch_bytes": 67108864,
    "max_public_key_bytes": 32,
    "max_revocation_entries": 64,
    "max_role_entries": 16,
    "max_signature_verifications_per_review": 3,
    "max_signature_bytes": 64,
    "max_trust_policy_bytes": 65536,
    "max_trust_roots": 2,
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
    "production_trust_root_binding": "NONE",
    "provider_endpoints": [],
    "real_evidence_input_authorized": False,
    "replay_ledger_binding": "NONE",
    "resource_scope_id": (
        "EXISTING_LOCAL_WORKTREE_PRIVATE_SCRATCH_LOCAL_COMPUTE_AND_COMMITTED_"
        "PUBLIC_ONLY_SYNTHETIC_TRUST_KATS"
    ),
    "security_reviewer_binding": "NONE_PRODUCTION_SECURITY_REVIEWER_UNBOUND",
    "signing_or_key_generation_authorized": False,
    "synthetic_trust_root_binding": (
        "COMMITTED_NONSECRET_PUBLIC_ONLY_SYNTHETIC_KAT_NOT_PRODUCTION_TRUST"
    ),
    "test_data_scope": (
        "COMMITTED_NONSECRET_PUBLIC_ONLY_SYNTHETIC_KAT_NO_SEEDS_NO_PRIVATE_KEYS"
    ),
    "trusted_time_binding": "FIXED_KAT_ONLY_NOT_TRUSTED_TIME",
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
        "event": "OWNER_CONTINUES_NEXT_BOUNDED_BOOTSTRAP_TRUST_DECISION_PATH",
        "from_state": "UNRECORDED_NO_AUTHORITY",
        "to_state": CURRENT_STATE,
    },
    {
        "event": "OWNER_HOLDS_OR_REJECTS",
        "from_state": "UNRECORDED_NO_AUTHORITY",
        "to_state": "REJECTED_FAIL_CLOSED",
    },
    {
        "event": "EXACT_AUTHORIZED_SUCCESSOR_INTEGRATED_AND_FULL_GATE_PASSES",
        "from_state": CURRENT_STATE,
        "to_state": "CONSUMED_SCOPE_COMPLETE",
    },
    {
        "event": (
            "OWNER_REVOKES_OR_BASELINE_UNIT_ALGORITHM_MESSAGE_DOMAIN_TRUST_"
            "RESOURCE_BUDGET_NETWORK_CREDENTIAL_ENDPOINT_OR_REVIEWER_TOPOLOGY_DRIFTS"
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
    "authorized_future_local_threat_specifications": ["T05"],
    "bootstrap_trust_authentication_isolated_lab_implementation_authorized": True,
    "bootstrap_trust_authentication_isolated_lab_implemented": False,
    "current_decision_candidate_surface_components_implemented": 0,
    "downstream_gate_count": 4,
    "downstream_gates_authorized": 0,
    "effective_only_after_integrated_full_gate": True,
    "exact_next_unit_authorized": True,
    "future_successor_minimum_independent_reviewer_lane_count": 2,
    "future_successor_candidate_surface_component_total": 1,
    "future_successor_candidate_surface_components_authorized": 1,
    "implementation_authority_recorded": True,
    "implementation_resource_binding_recorded": True,
    "implementation_scope_decision_recorded": True,
    "implementation_side_effects_unlocked": IMPLEMENTATION_SIDE_EFFECTS,
    "isolated_lab_predecessor_surface_components_implemented": 2,
    "isolated_lab_predecessor_surface_component_total": 2,
    "local_predecessor_threat_specifications_covered": 4,
    "owner_handoff_eligible": False,
    "predecessor_implementation_authority_consumed": True,
    "production_environment_implementation_authorized": False,
    "production_ingestion_control_count": 14,
    "production_ingestion_controls_implemented": 0,
    "production_ingestion_controls_runtime_exercised": 0,
    "production_ingestion_enabled": False,
    "production_ingestion_implemented": False,
    "production_security_reviewer_bound": False,
    "production_shaped_component_code_authorized": True,
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
}

NONCLAIMS = {
    "any_production_ingestion_control_implemented": False,
    "application_claim_authorized": False,
    "bootstrap_trust_authentication_implemented": False,
    "budget_cap_zero_is_budget_reservation": False,
    "condition_output_authorized": False,
    "credential_or_secret_material_accessed": False,
    "declared_role_is_scope_authorization": False,
    "deployment_authorized": False,
    "downstream_gate_authority_derived": False,
    "durable_custody_proved": False,
    "durable_replay_cas_proved": False,
    "evidence_acceptance_authorized": False,
    "experiment_rows_created": False,
    "external_paid_spend_authorized": False,
    "fault_injected": False,
    "fault_injection_authorized": False,
    "frozen_revocation_snapshot_is_current": False,
    "git_publication_authority_derived": False,
    "global_single_use_proved": False,
    "independent_checker_is_production_security_approval": False,
    "local_t05_kat_is_production_mitigation": False,
    "output_permit_defined": False,
    "owner_signature_observed": False,
    "paid_resource_provisioned": False,
    "private_key_or_seed_material_present": False,
    "production_authentication_succeeded": False,
    "production_credentials_authorized": False,
    "production_endpoint_bound": False,
    "production_environment_implementation_authorized": False,
    "production_ingestion_enabled": False,
    "production_ingestion_implemented": False,
    "production_key_version_bound": False,
    "production_resource_authority_bound": False,
    "production_revocation_source_bound": False,
    "production_role_bound": False,
    "production_rollback_authority_bound": False,
    "production_security_approval": False,
    "production_security_reviewer_bound": False,
    "production_signer_bound": False,
    "production_trust_root_bound": False,
    "provider_authority": False,
    "provider_called": False,
    "provider_cryptographic_compatibility_proved": False,
    "real_evidence_accepted": False,
    "real_evidence_authenticated": False,
    "real_evidence_collected": False,
    "real_evidence_ingested": False,
    "real_evidence_present": False,
    "real_evidence_validated": False,
    "reference_verifier_is_production_fit": False,
    "revocation_currentness_proved": False,
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
    "synthetic_trust_root_is_production_trust": False,
    "track_subject_binding_implemented": False,
    "trusted_production_time_bound": False,
    "wire_attempted": False,
}

DOMAIN_PREFIXES = {
    "authorized_component_contract": (
        "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_COMPONENT_CONTRACT_V1"
    ),
    "boundary": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_BOUNDARY_V1",
    "decision_provenance": (
        "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_DECISION_PROVENANCE_V1"
    ),
    "decision_record": (
        "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_DECISION_RECORD_V1"
    ),
    "implementation_authority": (
        "AB_TRACK_B_BOOTSTRAP_TRUST_IMPLEMENTATION_AUTHORITY_SCOPE_V1"
    ),
    "nonclaims": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_NONCLAIMS_V1",
    "owner_implementation_actor": (
        "AB_TRACK_B_BOOTSTRAP_TRUST_OWNER_IMPLEMENTATION_ACTOR_V1"
    ),
    "receipt": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_DECISION_RECEIPT_V1",
    "resource_binding": (
        "AB_TRACK_B_BOOTSTRAP_TRUST_ISOLATED_LAB_RESOURCE_BINDING_V1"
    ),
    "rollback": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_ROLLBACK_V1",
    "state_machine": (
        "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_STATE_MACHINE_V1"
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


class BootstrapTrustAuthorityDecisionReviewError(ValueError):
    """Fail-closed decision-review error carrying a stable reason code."""


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise BootstrapTrustAuthorityDecisionReviewError(f"{code}: {message}")


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
    return hashlib.sha256(domain.encode("ascii") + b"\0" + canonical_bytes(value)).hexdigest()


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
        and predecessor["implementation_authority_single_use_consumed"] is True,
        "E_PREDECESSOR_AUTHORITY",
        "predecessor implementation authority is not consumed",
    )
    require(
        predecessor["manifest_path"] == PREDECESSOR_MANIFEST_PATH
        and predecessor["manifest_path"] in predecessor["artifact_raw_sha256"],
        "E_PREDECESSOR_MANIFEST_PATH",
        "predecessor manifest path is not the exact protected artifact path",
    )
    require(
        authority["effective_only_after_integrated_full_gate"] is True
        and state["decision_full_gate_consumes_new_authority"] is False,
        "E_AUTHORITY_ACTIVATION",
        "decision release/consumption boundary drift",
    )
    require(
        authority["non_transitive"] is True
        and authority["subdelegation_authorized"] is False
        and authority["runtime_import_authorized"] is False,
        "E_AUTHORITY_SCOPE",
        "authority became transitive or runtime-visible",
    )
    input_topology = component["input_topology"]
    require(
        input_topology["production_and_unknown_mode_rejected_before_any_input_observation"]
        is True
        and input_topology["trust_policy_may_be_sourced_from_authentication_bundle"]
        is False
        and input_topology["trust_policy_may_be_sourced_from_envelope"] is False,
        "E_TRUST_TOPOLOGY",
        "untrusted input can influence bootstrap trust",
    )
    profiles = component["synthetic_track_profiles"]
    require(
        type(profiles) is list
        and len(profiles) == 2
        and [profile["track_id"] for profile in profiles]
        == ["MANAGED_SPANNER_CLOUD_KMS", "SELF_HOSTED_ETCD_OPENBAO"],
        "E_SYNTHETIC_TRACK_PROFILE",
        "exact two-track profile identity or order drift",
    )
    profile_value_sets: list[set[str]] = []
    for profile in profiles:
        require(
            profile["exact_chain_order"]
            == [
                profile["root"]["key_id"],
                profile["issuer"]["key_id"],
                profile["leaf"]["key_id"],
            ],
            "E_SYNTHETIC_TRACK_CHAIN",
            "root-to-issuer-to-active-leaf chain order drift",
        )
        require(
            profile["leaf"]["active_key_version"]
            != profile["leaf"]["revoked_key_version"],
            "E_SYNTHETIC_TRACK_KEY_VERSION",
            "active and revoked leaf versions collide",
        )
        critical_values = {
            profile["root"]["key_id"],
            profile["root"]["key_version"],
            profile["root"]["role"],
            profile["issuer"]["key_id"],
            profile["issuer"]["key_version"],
            profile["issuer"]["role"],
            profile["leaf"]["key_id"],
            profile["leaf"]["active_key_version"],
            profile["leaf"]["revoked_key_version"],
            profile["leaf"]["role"],
            profile["policy_revision"],
            profile["revocation_snapshot_revision"],
            profile["signature_domain"],
            profile["public_only_precomputed_vector_set_id"],
        }
        require(
            len(critical_values) == 14,
            "E_SYNTHETIC_TRACK_VALUE_ALIAS",
            "one track aliases an ID, version, role, revision, domain, or vector set",
        )
        profile_value_sets.append(critical_values)
    require(
        profile_value_sets[0].isdisjoint(profile_value_sets[1]),
        "E_SYNTHETIC_TRACK_SUBSTITUTION",
        "managed and self-hosted profile values overlap",
    )
    reviewer = component["reviewer_topology"]
    require(
        reviewer["minimum_independent_reviewer_lane_count"] >= 2
        and reviewer["lane_identity_distinctness_required"] is True
        and reviewer["reviewer_identity_binding_mode"]
        == "SEMANTIC_LABEL_BOUND_AT_REVIEW_TIME"
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
        and resources["signing_or_key_generation_authorized"] is False,
        "E_RESOURCE_AUTHORITY",
        "resource, secret, signing, or network authority drift",
    )
    require(
        resources["component_limits"]["max_public_key_bytes"] == 32
        and resources["component_limits"]["max_signature_bytes"] == 64,
        "E_CRYPTOGRAPHIC_MATERIAL_LIMIT",
        "public-key or signature byte limit drift",
    )
    require(
        boundary["isolated_lab_predecessor_surface_components_implemented"] == 2
        and boundary["local_predecessor_threat_specifications_covered"] == 4
        and boundary["authorized_future_candidate_surface_component_count"] == 1
        and boundary["future_successor_candidate_surface_component_total"] == 1
        and boundary["future_successor_candidate_surface_components_authorized"]
        == 1
        and boundary["current_decision_candidate_surface_components_implemented"]
        == 0
        and boundary["authorized_future_local_threat_specifications"] == ["T05"]
        and boundary["bootstrap_trust_authentication_isolated_lab_implemented"]
        is False
        and boundary["production_ingestion_controls_implemented"] == 0,
        "E_CONTROL_ACCOUNTING",
        "decision or production control accounting drift",
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
        "authorized_candidate_surface_component_count": 1,
        "authorized_component_contract_sha256": expected_hashes[
            "authorized_component_contract_sha256"
        ],
        "authorized_local_threat_specification_count": 1,
        "authorized_local_threat_specifications": "T05",
        "bootstrap_trust_authentication_implemented": False,
        "boundary_sha256": expected_hashes["boundary_sha256"],
        "component_runtime_network": False,
        "content_sha256": "0" * 64,
        "current_decision_candidate_surface_components_implemented": 0,
        "current_state": CURRENT_STATE,
        "date": DATE,
        "decision": DECISION,
        "decision_record_sha256": decision_record_sha256,
        "downstream_gates_authorized": 0,
        "distinct_synthetic_track_profiles": True,
        "external_paid_spend_cap": 0,
        "forbidden_operation_count": len(FORBIDDEN_OPERATIONS),
        "future_successor_minimum_independent_reviewer_lane_count": 2,
        "future_successor_candidate_surface_component_total": 1,
        "future_successor_candidate_surface_components_authorized": 1,
        "global_single_use_proved": False,
        "implementation_authority_recorded": True,
        "implementation_authority_sha256": expected_hashes[
            "implementation_authority_sha256"
        ],
        "implementation_authority_single_use_consumed": False,
        "implementation_resource_binding_recorded": True,
        "implementation_scope_decision_recorded": True,
        "implementation_side_effects_unlocked": IMPLEMENTATION_SIDE_EFFECTS,
        "isolated_lab_predecessor_surface_components_implemented": 2,
        "local_predecessor_threat_specifications_covered": 4,
        "max_public_key_bytes": COMPONENT_LIMITS["max_public_key_bytes"],
        "max_signature_bytes": COMPONENT_LIMITS["max_signature_bytes"],
        "mode": MODE,
        "next_unit": NEXT_UNIT,
        "nonclaim_field_count": len(NONCLAIMS),
        "nonclaims_sha256": expected_hashes["nonclaims_sha256"],
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
        "production_shaped_component_code_authorized": True,
        "production_validated_evidence_items": 0,
        "provider_authority": False,
        "credential_handle_count": 0,
        "credential_path_count": 0,
        "provider_endpoint_count": 0,
        "real_evidence_items_present": 0,
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
        "state_machine_sha256": expected_hashes["state_machine_sha256"],
        "status": STATUS,
        "synthetic_track_profile_count": len(SYNTHETIC_TRACK_PROFILES),
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
    "synthetic_track_profile_count",
    "distinct_synthetic_track_profiles",
    "bootstrap_trust_authentication_implemented",
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
    "credential_handle_count",
    "credential_path_count",
    "component_runtime_network",
    "max_public_key_bytes",
    "max_signature_bytes",
    "global_single_use_proved",
    "production_shaped_component_code_authorized",
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
    "BootstrapTrustAuthorityDecisionReviewError",
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
    "TSV_FIELDS",
    "build_owner_decision_record",
    "canonical_bytes",
    "domain_sha256",
    "expected_section_hashes",
    "render_tsv",
    "review_decision",
]
