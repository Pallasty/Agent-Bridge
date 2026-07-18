#!/usr/bin/env python3
"""Independent fail-closed checker for the bootstrap-trust authority pack."""

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
from typing import Any, Callable, Iterable, Mapping


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MIN_JSON_INTEGER = -(2**63)
MAX_JSON_INTEGER = 2**63 - 1

SOURCE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "bootstrap_trust_authentication_isolated_lab_implementation_authority_and_"
    "resource_binding_decision_v1.py"
)
CHECKER_REL = (
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_"
    "and_resource_binding_decision_v1_pack.py"
)
DECISION_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_"
    "and_resource_binding_decision_v1_pack_owner_decision_v0.json"
)
EXPECTED_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_"
    "and_resource_binding_decision_v1_pack.expected.v0.tsv"
)
MANIFEST_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_"
    "and_resource_binding_decision_v1_pack_v0.json"
)

SOURCE_RAW_SHA256 = "f1168fad03ac6366e8d6501cbd4da3a2969d25cc6ef9f5bf85c0624de9ae545c"
DECISION_RAW_SHA256 = "05f2fad20896cd108f0695253c617cd0c050e80ae947ec4c90f7d7684e3e344b"
EXPECTED_RAW_SHA256 = "79502975f438ed644306a392131d102e2efadae37560b3489c91547a0125e43f"

MANIFEST_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "bootstrap_trust_authentication_isolated_lab_implementation_authority_and_"
    "resource_binding_decision_v1_pack_manifest.v0"
)
MANIFEST_EVIDENCE_PATHS = (
    SOURCE_REL,
    CHECKER_REL,
    DECISION_REL,
    EXPECTED_REL,
)

PREDECESSOR_EXPECTED_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_"
    "separation_isolated_lab_v1_pack.expected.v0.tsv"
)
PREDECESSOR_RAW_SHA256 = {
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-v1.schema.json":
        "e8cb4964f86de39b16d553537467006454c720dc8bfa8d36e370189627328f55",
    "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.md":
        "a93fd00b9dc43f8b9d3717fd07bf3a2eef734724834d75d122d2e8bbbe6e3149",
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.sh":
        "464b975d61403759221fd3aa41da4c38de12f4ec946b161100d23edadbc2b174",
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1.py":
        "bfa3badbe2b467fbed610d5acb42ef21f1aec2ceb2d5ccf2c218fecfe438eed1",
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.py":
        "76e0960cb9afa0e4e655ec122b600fe489a31acd5a7edf659d2fff4727ef0dcf",
    PREDECESSOR_EXPECTED_REL:
        "775ecfa5169509a5fe0e5a900d8644f47b6b4cf64a1778c7d4ed52214115c847",
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_synthetic_v0.json":
        "324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9",
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_v0.json":
        "9c7ba09368ebd610452ca2799226c1f57dcb63fedabb0319f4b39bc071277d04",
}
PREDECESSOR_EXPECTED_TSV = """schema	agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.receipt.v0
status	REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_PRODUCTION_EVIDENCE_ENVELOPE_BOUNDED_FRAME_AND_SYNTHETIC_MODE_SEPARATION_ISOLATED_LAB_COMPONENTS_IMPLEMENTED_LOCAL_KAT_CONFORMANT_PRODUCTION_CONTROLS_ZERO_RUNTIME_UNBOUND
decision	ISOLATED_LAB_FRAME_AND_MODE_COMPONENTS_CONFORMANT_PRODUCTION_PATH_FAIL_CLOSED
date	2026-07-17
mode	SYNTHETIC_KAT
next_unit	REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_BINDING_DECISION
component_state	PARSED_ISOLATED_LAB_KAT_COMPONENT_ONLY
valid_frame_count	2
fixture_negative_case_count	64
public_mode_pre_observation_test_count	6
source_direct_adversarial_reference_count	64
track_count	2
receipt_set_sha256	637a2a54a182eb377eb29e3513c98c2aeea386fd8516d2319e5d32a2ecda86c8
raw_frame_set_sha256	b5e7f2326df27889465f93d08b640cdbbc6c9b5944f0d241b5774afa5deed442
canonical_frame_set_sha256	be4a7fbc10e937fc8ada1fd7a297e7de65081918cab95a684c6d37c17a057746
isolated_lab_candidate_surface_component_total	2
isolated_lab_candidate_surface_component_implemented	2
isolated_lab_candidate_surface_component_locally_kat_exercised	2
boundary_threat_specifications_locally_kat_covered	4
threat_case_count	20
production_threat_cases_runtime_exercised	0
production_ingestion_control_count	14
production_ingestion_controls_implemented	0
production_ingestion_controls_runtime_exercised	0
real_evidence_items_present	0
production_validated_evidence_items	0
runtime_evidence_accepted	0
runtime_prerequisites_satisfied	0
downstream_gates_authorized	0
runtime_authority	false
provider_authority	false
runtime_side_effects_unlocked	NONE
schema_raw_sha256	e8cb4964f86de39b16d553537467006454c720dc8bfa8d36e370189627328f55
schema_canonical_sha256	c063d91c43ee4d73e5b01f396cd4da9aea2adafc78b17198a54d995b43c31f33
source_raw_sha256	bfa3badbe2b467fbed610d5acb42ef21f1aec2ceb2d5ccf2c218fecfe438eed1
fixture_raw_sha256	324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9
predecessor_artifact_count	7
predecessor_receipt_line_count	56
predecessor_receipt_content_sha256	48f4eee93f565005ffa79a119529d58e5d61eb947754d4672c96541001268463
content_sha256	4d5752110ebf0c11197bd8667fb9e79948724f5195465e41c6709d98d6177b8c
"""
PREDECESSOR_RECEIPT_CONTENT_SHA256 = (
    "4d5752110ebf0c11197bd8667fb9e79948724f5195465e41c6709d98d6177b8c"
)

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
CURRENT_STATE = "AUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT"
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_TRUST_CHAIN_EXACT_KEY_VERSION_"
    "DECLARED_ROLE_AND_REVOCATION_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
)
IMPLEMENTATION_SIDE_EFFECTS = (
    "REVERSIBLE_LOCAL_CODE_SCHEMA_TEST_DOCS_FOR_EXACT_NEXT_UNIT_ONLY"
)

DOMAIN_PREFIXES = {
    "authorized_component_contract":
        "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_COMPONENT_CONTRACT_V1",
    "boundary": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_BOUNDARY_V1",
    "decision_provenance":
        "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_DECISION_PROVENANCE_V1",
    "decision_record":
        "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_DECISION_RECORD_V1",
    "implementation_authority":
        "AB_TRACK_B_BOOTSTRAP_TRUST_IMPLEMENTATION_AUTHORITY_SCOPE_V1",
    "nonclaims": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_NONCLAIMS_V1",
    "owner_implementation_actor":
        "AB_TRACK_B_BOOTSTRAP_TRUST_OWNER_IMPLEMENTATION_ACTOR_V1",
    "receipt": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_DECISION_RECEIPT_V1",
    "resource_binding":
        "AB_TRACK_B_BOOTSTRAP_TRUST_ISOLATED_LAB_RESOURCE_BINDING_V1",
    "rollback": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_ROLLBACK_V1",
    "state_machine":
        "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHORIZATION_STATE_MACHINE_V1",
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
    "authorized_component_contract_sha256":
        "6982a387d0481c7603053971ce6b2b60bebadb32aea3eb2c22b1f2ae5bd73b3c",
    "boundary_sha256":
        "ee43100a159b00f5e97c53b312e6d056e6e91cfcb908ff3acd52b35481f4cdc9",
    "decision_provenance_sha256":
        "645775c985782fcd1553b146094217bb2d4b6e1c6800aed7091103a078cb1237",
    "implementation_authority_sha256":
        "8a1737328d04dd0b2d8178d745569d48c25926a47520187f62bd0fcb858a5eb7",
    "nonclaims_sha256":
        "8a1fdd31d740b46e2793e3218e14257ce8b6bf1a38cbeb389871c621fe797346",
    "owner_implementation_actor_sha256":
        "6842a9cfc98d8c0b7e0189f10d41b1470d834cf1a77e7288ce27bed76edf3db7",
    "resource_binding_sha256":
        "2e31bb0e743b776d69bafec4f22bd5b62c785e41c9568b1a0b92cd2caa5f61cf",
    "rollback_sha256":
        "5a518dfaa3cd7cde371d07ad3ed100fdcecb0e0fbee283b5bd5445e50497395a",
    "state_machine_sha256":
        "8cd0bc5ff63ab8fa54510c92834481ce7fc64561398aa9427c6ad9f7423de0d3",
}
DECISION_RECORD_CANONICAL_SHA256 = (
    "243b976f3e9f5cfea80dad7405b0822950ca15bab0330555f90cbf3c9449b003"
)
DECISION_RECORD_DOMAIN_SHA256 = (
    "ac37eb0c627512842a2e046dcba98b767ff7356dd7c728dc882e1e8baef35f0b"
)
RECEIPT_CONTENT_SHA256 = (
    "b15c3a545502dcaf47e4c297d98cd90ce01dfe93c70b93a4cf3771c4b1a48315"
)

EXPECTED_RECORD_JSON = r'''{"authorized_component_contract":{"algorithm_profile":{"algorithm":"ED25519","external_prehash_allowed":false,"public_key_encoding":"RAW_32_BYTE_RFC8032_CANONICAL_POINT","public_key_prime_subgroup_required":true,"signature_encoding":"RAW_64_BYTE_RFC8032_CANONICAL_R_AND_SCALAR","signature_message_profile":"U64BE_LENGTH_PREFIXED_ASCII_DOMAIN_AND_EXACT_PREDECESSOR_CANONICAL_FRAME_BYTES_NO_PARSE_RESERIALIZE","signature_scalar_less_than_group_order_required":true,"signature_scheme":"ED25519_PURE_RFC8032_NO_CONTEXT_NO_PREHASH","small_order_or_identity_points_rejected":true},"authentication_state_ceiling":{"production_success_state_representable":false,"states":["UNREVIEWED_SYNTHETIC_KAT_ONLY","MODE_REJECTED_FAIL_CLOSED","PREDECESSOR_FRAME_REJECTED_FAIL_CLOSED","TRUST_POLICY_REJECTED_FAIL_CLOSED","AUTHENTICATION_REJECTED_FAIL_CLOSED","AUTHENTICATED_SYNTHETIC_KAT_AGAINST_FROZEN_BOOTSTRAP_TRUST_SNAPSHOT_COMPONENT_ONLY"],"successful_state":"AUTHENTICATED_SYNTHETIC_KAT_AGAINST_FROZEN_BOOTSTRAP_TRUST_SNAPSHOT_COMPONENT_ONLY"},"input_topology":{"authentication_metadata_detached":true,"production_and_unknown_mode_rejected_before_any_input_observation":true,"public_input_tuple":["frame","detached_authentication_bundle","separately_injected_synthetic_trust_policy","mode"],"trust_policy_may_be_sourced_from_authentication_bundle":false,"trust_policy_may_be_sourced_from_envelope":false},"local_scope":{"authorized_candidate_surface_component_count":1,"authorized_candidate_surface_components":["BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_VERIFIER"],"authorized_local_threat_specification_count":1,"authorized_local_threat_specifications":["T05"],"candidate_surface_component_total":1,"candidate_surface_components_implemented_by_decision":0,"local_threat_specification_total":1,"production_ingestion_control_implemented_by_authorization":false},"reviewer_topology":{"checker_is_production_security_approval":false,"lane_identity_distinctness_required":true,"minimum_independent_reviewer_lane_count":2,"production_security_reviewer_binding":"NONE","required_reviewer_lanes":["CONTRACT_CONFORMANCE_REVIEW","SECURITY_AND_SOURCE_BOUND_GATE_REVIEW"],"reviewer_identity_binding_mode":"SEMANTIC_LABEL_BOUND_AT_REVIEW_TIME"},"revocation_profile":{"active_state":"ACTIVE_AT_EXACT_FROZEN_SYNTHETIC_REVISION","frozen_snapshot_is_currentness":false,"revocation_source":"SEPARATELY_INJECTED_FROZEN_SYNTHETIC_TRUST_POLICY","revoked_state":"REVOKED_AT_OR_BEFORE_EXACT_FROZEN_SYNTHETIC_REVISION","self_asserted_active_state_allowed":false,"unknown_state":"UNKNOWN_FAIL_CLOSED"},"role_boundary":{"declared_role":"SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY","declared_role_cryptographically_authenticated_in_kat":true,"declared_role_is_role_scope_authorization":false,"declared_role_source":"EXACT_SYNTHETIC_TRACK_PROFILE_LEAF_ROLE","signer_role_scope_authorization_control_implemented":false,"track_subject_binding_control_implemented":false},"synthetic_track_profiles":[{"exact_chain_order":["KAT_MANAGED_BOOTSTRAP_ROOT_V1","KAT_MANAGED_TRUST_POLICY_ISSUER_V1","KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER_V2"],"issuer":{"key_id":"KAT_MANAGED_TRUST_POLICY_ISSUER_V1","key_version":"KAT_MANAGED_ISSUER_KEY_VERSION_1","role":"KAT_MANAGED_TRUST_POLICY_ISSUER"},"leaf":{"active_key_version":"KAT_MANAGED_LEAF_KEY_VERSION_2","key_id":"KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER_V2","revoked_key_version":"KAT_MANAGED_LEAF_KEY_VERSION_1","role":"KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER"},"policy_revision":"KAT_MANAGED_TRUST_POLICY_REVISION_1","public_only_precomputed_vector_set_id":"KAT_MANAGED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1","revocation_snapshot_revision":"KAT_MANAGED_REVOCATION_SNAPSHOT_REVISION_1","root":{"key_id":"KAT_MANAGED_BOOTSTRAP_ROOT_V1","key_version":"KAT_MANAGED_ROOT_KEY_VERSION_1","role":"KAT_MANAGED_BOOTSTRAP_ROOT"},"signature_domain":"AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_MANAGED_KAT_SIGNATURE_V1","track_id":"MANAGED_SPANNER_CLOUD_KMS"},{"exact_chain_order":["KAT_SELF_HOSTED_BOOTSTRAP_ROOT_V1","KAT_SELF_HOSTED_TRUST_POLICY_ISSUER_V1","KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER_V2"],"issuer":{"key_id":"KAT_SELF_HOSTED_TRUST_POLICY_ISSUER_V1","key_version":"KAT_SELF_HOSTED_ISSUER_KEY_VERSION_1","role":"KAT_SELF_HOSTED_TRUST_POLICY_ISSUER"},"leaf":{"active_key_version":"KAT_SELF_HOSTED_LEAF_KEY_VERSION_2","key_id":"KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER_V2","revoked_key_version":"KAT_SELF_HOSTED_LEAF_KEY_VERSION_1","role":"KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER"},"policy_revision":"KAT_SELF_HOSTED_TRUST_POLICY_REVISION_1","public_only_precomputed_vector_set_id":"KAT_SELF_HOSTED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1","revocation_snapshot_revision":"KAT_SELF_HOSTED_REVOCATION_SNAPSHOT_REVISION_1","root":{"key_id":"KAT_SELF_HOSTED_BOOTSTRAP_ROOT_V1","key_version":"KAT_SELF_HOSTED_ROOT_KEY_VERSION_1","role":"KAT_SELF_HOSTED_BOOTSTRAP_ROOT"},"signature_domain":"AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_SELF_HOSTED_KAT_SIGNATURE_V1","track_id":"SELF_HOSTED_ETCD_OPENBAO"}],"trust_chain_profile":{"exact_positive_key_version_required":true,"latest_or_zero_key_version_allowed":false,"maximum_chain_entries":3,"maximum_trust_roots":2,"root_injection_from_untrusted_bundle_allowed":false,"separately_injected_trust_policy_required":true,"trust_on_first_use_allowed":false},"trust_domain_family":"AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_KAT_SIGNATURE_FAMILY_V1"},"boundary":{"authorized_future_candidate_surface_component_count":1,"authorized_future_local_threat_specification_count":1,"authorized_future_local_threat_specifications":["T05"],"bootstrap_trust_authentication_isolated_lab_implementation_authorized":true,"bootstrap_trust_authentication_isolated_lab_implemented":false,"current_decision_candidate_surface_components_implemented":0,"downstream_gate_count":4,"downstream_gates_authorized":0,"effective_only_after_integrated_full_gate":true,"exact_next_unit_authorized":true,"future_successor_candidate_surface_component_total":1,"future_successor_candidate_surface_components_authorized":1,"future_successor_minimum_independent_reviewer_lane_count":2,"implementation_authority_recorded":true,"implementation_resource_binding_recorded":true,"implementation_scope_decision_recorded":true,"implementation_side_effects_unlocked":"REVERSIBLE_LOCAL_CODE_SCHEMA_TEST_DOCS_FOR_EXACT_NEXT_UNIT_ONLY","isolated_lab_predecessor_surface_component_total":2,"isolated_lab_predecessor_surface_components_implemented":2,"local_predecessor_threat_specifications_covered":4,"owner_handoff_eligible":false,"predecessor_implementation_authority_consumed":true,"production_environment_implementation_authorized":false,"production_ingestion_control_count":14,"production_ingestion_controls_implemented":0,"production_ingestion_controls_runtime_exercised":0,"production_ingestion_enabled":false,"production_ingestion_implemented":false,"production_security_reviewer_bound":false,"production_shaped_component_code_authorized":true,"production_threat_specification_count":20,"production_threat_specifications_runtime_exercised":0,"production_validated_evidence_items":0,"provider_authority":false,"real_evidence_items_present":0,"runtime_admission_granted":false,"runtime_admission_ready":false,"runtime_authority":false,"runtime_evidence_accepted":0,"runtime_owner_decision_recorded":false,"runtime_owner_identity_bound":false,"runtime_prerequisite_count":16,"runtime_prerequisites_satisfied":0,"runtime_side_effects_unlocked":"NONE"},"date":"2026-07-17","decision":"AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED","decision_provenance":{"budget_cap_source":"FAIL_CLOSED_ZERO_DEFAULT_UNDER_REVERSIBLE_AUTONOMY","decision_time_utc":"NONE","directive_observed_in_owner_session":true,"directive_semantics":"CONTINUE_NEXT_BOUNDED_BOOTSTRAP_TRUST_AUTHENTICATION_DECISION_UNIT","explicit_credential_authority_observed":false,"explicit_endpoint_authority_observed":false,"explicit_production_runtime_authority_observed":false,"explicit_production_signer_authority_observed":false,"explicit_production_trust_root_authority_observed":false,"explicit_provider_authority_observed":false,"latest_directive_explicitly_named_budget_cap":false,"latest_directive_explicitly_named_owner_label":false,"no_runtime_provider_or_production_trust_authority_inferred":true,"owner_label_source":"ESTABLISHED_PROJECT_OWNER_PROFILE","owner_supplied_numeric_budget_cap":false,"trusted_decision_timestamp_observed":false},"implementation_authority":{"allowed_operations":["ADD_CLOSED_WORLD_SYNTHETIC_BOOTSTRAP_TRUST_POLICY_AND_DETACHED_AUTHENTICATION_BUNDLE_SCHEMAS","ADD_BOUNDED_PURE_ED25519_REFERENCE_VERIFIER_FOR_PUBLIC_ONLY_FIXED_KATS","ADD_U64BE_LENGTH_PREFIXED_DOMAIN_AND_EXACT_PREDECESSOR_CANONICAL_FRAME_MESSAGE","ADD_PINNED_SYNTHETIC_ROOT_CHAIN_EXACT_KEY_VERSION_DECLARED_ROLE_AND_FROZEN_REVOCATION_SNAPSHOT_CHECKS","COMPOSE_WITH_FROZEN_PREDECESSOR_FRAME_REVIEW_API_IN_SYNTHETIC_MODE","ADD_PREOBSERVATION_SYNTHETIC_PRODUCTION_MODE_GUARDS","ADD_DETERMINISTIC_NONSECRET_PUBLIC_ONLY_ADVERSARIAL_KATS","ADD_PURE_REVIEWER_INDEPENDENT_CONTRACT_AND_SECURITY_GATE_LANES_REPORT_AND_SOURCE_BOUND_GATE"],"authority_class":"REVERSIBLE_CODE_SCHEMA_TEST_DOCUMENTATION_ONLY","authorized_candidate_surface_component_count":1,"authorized_local_threat_specifications":["T05"],"current_state":"AUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT","default_off_required":true,"effective_only_after_integrated_full_gate":true,"exact_next_unit_authorized":true,"forbidden_operations":["ACCESS_CREDENTIAL_OR_SECRET_MATERIAL","ACCEPT_OR_PERSIST_REAL_EVIDENCE","ADD_CRYPTOGRAPHIC_SIGNING_KEY_GENERATION_OR_PRIVATE_SEED_API","ADD_OR_FETCH_UNPINNED_CRYPTOGRAPHIC_DEPENDENCY","ALLOW_LATEST_OR_ZERO_KEY_VERSION","ALLOW_REVOCATION_FAIL_OPEN","ALLOW_TRUST_ON_FIRST_USE_OR_UNKNOWN_ROOT","AUTHORIZE_OR_INJECT_FAULT","AUTHORIZE_OUTPUT_OR_CLAIM","AUTHORIZE_SIGNER_ROLE_SCOPE_TRACK_SUBJECT_AUDIENCE_OR_NONCE","BIND_PRODUCTION_SIGNER_KEY_VERSION_ROLE_REVOCATION_SOURCE_OR_TRUST_ROOT","BIND_PROVIDER_OR_PRODUCTION_ENDPOINT","CALL_PROVIDER_OR_ATTEMPT_WIRE","CLAIM_FROZEN_REVOCATION_SNAPSHOT_CURRENTNESS_OR_FRESHNESS","CLAIM_PRODUCTION_AUTHENTICATION_OR_PRODUCTION_MITIGATION","COMMIT_PRIVATE_KEY_TEST_SEED_OR_SECRET_SHAPED_MATERIAL","CREATE_RUNTIME_OR_EXPERIMENT_ROW","DEPLOY_OR_ENABLE_PRODUCTION_INGESTION","ESTABLISH_DURABLE_CUSTODY_OR_REPLAY_LEDGER","FETCH_OR_REFRESH_TRUST_CERTIFICATE_OR_REVOCATION_DATA","LAUNCH_RUNNER_OR_BACKGROUND_DAEMON","PERSIST_AUTHENTICATED_EVIDENCE_OR_TRUST_MATERIAL","PROVISION_PAID_OR_EXTERNAL_RESOURCE","READ_AMBIENT_DEFAULT_OR_SYSTEM_TRUST_OR_CREDENTIAL_CHAIN","REGISTER_OR_IMPORT_INTO_PRODUCTION_RUNTIME","REPRESENT_RUNTIME_OWNER_DECISION","SATISFY_RUNTIME_PREREQUISITE","USE_AMBIENT_OR_PRODUCTION_TRUSTED_TIME"],"implementation_authority_recorded":true,"implementation_scope":"BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_CODE_ONLY_EXACT_NEXT_UNIT_SINGLE_USE_NON_TRANSITIVE","implementation_scope_decision_recorded":true,"mode":"ISOLATED_LAB_FIRST","non_transitive":true,"production_environment_implementation_authorized":false,"production_shaped_component_code_authorized":true,"runtime_import_authorized":false,"runtime_registration_authorized":false,"single_successor_intent":true,"single_use_enforced_by_external_ledger":false,"subdelegation_authorized":false},"next_unit":"REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_TRUST_CHAIN_EXACT_KEY_VERSION_DECLARED_ROLE_AND_REVOCATION_VERIFIER_ISOLATED_LAB_IMPLEMENTATION","nonclaims":{"any_production_ingestion_control_implemented":false,"application_claim_authorized":false,"bootstrap_trust_authentication_implemented":false,"budget_cap_zero_is_budget_reservation":false,"condition_output_authorized":false,"credential_or_secret_material_accessed":false,"declared_role_is_scope_authorization":false,"deployment_authorized":false,"downstream_gate_authority_derived":false,"durable_custody_proved":false,"durable_replay_cas_proved":false,"evidence_acceptance_authorized":false,"experiment_rows_created":false,"external_paid_spend_authorized":false,"fault_injected":false,"fault_injection_authorized":false,"frozen_revocation_snapshot_is_current":false,"git_publication_authority_derived":false,"global_single_use_proved":false,"independent_checker_is_production_security_approval":false,"local_t05_kat_is_production_mitigation":false,"output_permit_defined":false,"owner_signature_observed":false,"paid_resource_provisioned":false,"private_key_or_seed_material_present":false,"production_authentication_succeeded":false,"production_credentials_authorized":false,"production_endpoint_bound":false,"production_environment_implementation_authorized":false,"production_ingestion_enabled":false,"production_ingestion_implemented":false,"production_key_version_bound":false,"production_resource_authority_bound":false,"production_revocation_source_bound":false,"production_role_bound":false,"production_rollback_authority_bound":false,"production_security_approval":false,"production_security_reviewer_bound":false,"production_signer_bound":false,"production_trust_root_bound":false,"provider_authority":false,"provider_called":false,"provider_cryptographic_compatibility_proved":false,"real_evidence_accepted":false,"real_evidence_authenticated":false,"real_evidence_collected":false,"real_evidence_ingested":false,"real_evidence_present":false,"real_evidence_validated":false,"reference_verifier_is_production_fit":false,"revocation_currentness_proved":false,"runner_launch_authorized":false,"runner_launched":false,"runtime_admission_granted":false,"runtime_admission_ready":false,"runtime_authority":false,"runtime_owner_decision_recorded":false,"runtime_owner_identity_bound":false,"runtime_rows_created":false,"scientific_claim_authorized":false,"semantic_owner_label_is_authenticated_identity":false,"signer_role_scope_authorization_implemented":false,"signing_or_key_generation_authorized":false,"synthetic_trust_root_is_production_trust":false,"track_subject_binding_implemented":false,"trusted_production_time_bound":false,"wire_attempted":false},"owner_implementation_actor":{"binding_basis":"ESTABLISHED_PROFILE_PLUS_CURRENT_SESSION_CONTINUITY","cryptographic_identity_verified":false,"delegated_runtime_authority":false,"runtime_owner_decision_recorded":false,"runtime_owner_identity_bound":false,"semantic_actor_binding_recorded":true,"semantic_actor_label":"pallasting","semantic_actor_role":"PROJECT_OWNER","signature_observed":false},"predecessor":{"artifact_raw_sha256":{"docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-v1.schema.json":"e8cb4964f86de39b16d553537467006454c720dc8bfa8d36e370189627328f55","docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.md":"a93fd00b9dc43f8b9d3717fd07bf3a2eef734724834d75d122d2e8bbbe6e3149","scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.sh":"464b975d61403759221fd3aa41da4c38de12f4ec946b161100d23edadbc2b174","scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1.py":"bfa3badbe2b467fbed610d5acb42ef21f1aec2ceb2d5ccf2c218fecfe438eed1","scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.py":"76e0960cb9afa0e4e655ec122b600fe489a31acd5a7edf659d2fff4727ef0dcf","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.expected.v0.tsv":"775ecfa5169509a5fe0e5a900d8644f47b6b4cf64a1778c7d4ed52214115c847","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_synthetic_v0.json":"324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_v0.json":"9c7ba09368ebd610452ca2799226c1f57dcb63fedabb0319f4b39bc071277d04"},"authorization_consumption_state":"CONSUMED_SCOPE_COMPLETE","bootstrap_trust_authentication_authorized":false,"bootstrap_trust_authentication_implemented":false,"decision_source_baseline_commit":"d0356dbdbd7239ffab972ee21da81891210a055b","decision_source_baseline_parents":["3bf8ad3a67ff02a4e717db8e29e89079f66c01cf","20368c626bf34c5a1edd07391014ab8716536e7e"],"decision_source_baseline_tree":"b40c36c5fe73af3079bf3a81d69480d2555271d8","gate_path":"scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.sh","gate_raw_sha256":"464b975d61403759221fd3aa41da4c38de12f4ec946b161100d23edadbc2b174","implementation_authority_single_use_consumed":true,"integration_commit":"3bf8ad3a67ff02a4e717db8e29e89079f66c01cf","integration_parents":["7ef0f8e9b8048fbd1b308ca2a1d708138a615ed9","e5012eb3fd6742ceaecedf4b36adbee8ecfeb054"],"integration_tree":"1bb4b0d851bb4c1ce8a7bf91cbc489168ae41433","manifest_path":"scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_v0.json","manifest_raw_sha256":"9c7ba09368ebd610452ca2799226c1f57dcb63fedabb0319f4b39bc071277d04","receipt_content_sha256":"4d5752110ebf0c11197bd8667fb9e79948724f5195465e41c6709d98d6177b8c","source_commit":"e5012eb3fd6742ceaecedf4b36adbee8ecfeb054","source_parent":"fa0cb9f088e0da2c55c92efde860d9521d4b7493"},"resource_binding":{"allowed_resource_classes":["EXISTING_LOCAL_CPU_AND_MEMORY","ISOLATED_AGENT_BRIDGE_WORKTREE","PRIVATE_LOCAL_TEST_SCRATCH"],"ambient_or_system_trust_store_allowed":false,"component_limits":{"max_array_items":64,"max_authentication_bundle_bytes":65536,"max_chain_entries":3,"max_input_frame_bytes":1048576,"max_json_depth":32,"max_json_nodes":4096,"max_object_members":256,"max_parallel_workers":1,"max_private_scratch_bytes":67108864,"max_public_key_bytes":32,"max_revocation_entries":64,"max_role_entries":16,"max_signature_bytes":64,"max_signature_verifications_per_review":3,"max_trust_policy_bytes":65536,"max_trust_roots":2},"component_runtime_network":false,"credential_handles":[],"credential_paths":[],"currency_scope":"ALL_CURRENCIES_ZERO_ONLY","custody_store_binding":"NONE","dependency_scope":"PYTHON_STANDARD_LIBRARY_REFERENCE_KAT_ONLY_NO_FETCH","effective_external_paid_spend_cap":0,"implementation_resource_binding_recorded":true,"owner_supplied_numeric_budget_cap":false,"private_key_or_seed_material_authorized":false,"production_resource_authority_bound":false,"production_trust_root_binding":"NONE","provider_endpoints":[],"real_evidence_input_authorized":false,"replay_ledger_binding":"NONE","resource_scope_id":"EXISTING_LOCAL_WORKTREE_PRIVATE_SCRATCH_LOCAL_COMPUTE_AND_COMMITTED_PUBLIC_ONLY_SYNTHETIC_TRUST_KATS","security_reviewer_binding":"NONE_PRODUCTION_SECURITY_REVIEWER_UNBOUND","signing_or_key_generation_authorized":false,"synthetic_trust_root_binding":"COMMITTED_NONSECRET_PUBLIC_ONLY_SYNTHETIC_KAT_NOT_PRODUCTION_TRUST","test_data_scope":"COMMITTED_NONSECRET_PUBLIC_ONLY_SYNTHETIC_KAT_NO_SEEDS_NO_PRIVATE_KEYS","trusted_time_binding":"FIXED_KAT_ONLY_NOT_TRUSTED_TIME"},"rollback":{"local_worktree_delete_allowed":true,"production_kill_switch":"NOT_APPLICABLE_NOT_ENABLED","production_rollback_authority":false,"published_git_revert_plan_required":true,"remote_git_mutation_authority_derived":false,"reversible_only":true,"runtime_disable_action_required":false,"scope_invalidation_requires_new_decision":true,"unpublished_change_revert_allowed":true},"schema":"agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision.v1","schema_version":1,"section_sha256":{"authorized_component_contract_sha256":"6982a387d0481c7603053971ce6b2b60bebadb32aea3eb2c22b1f2ae5bd73b3c","boundary_sha256":"ee43100a159b00f5e97c53b312e6d056e6e91cfcb908ff3acd52b35481f4cdc9","decision_provenance_sha256":"645775c985782fcd1553b146094217bb2d4b6e1c6800aed7091103a078cb1237","implementation_authority_sha256":"8a1737328d04dd0b2d8178d745569d48c25926a47520187f62bd0fcb858a5eb7","nonclaims_sha256":"8a1fdd31d740b46e2793e3218e14257ce8b6bf1a38cbeb389871c621fe797346","owner_implementation_actor_sha256":"6842a9cfc98d8c0b7e0189f10d41b1470d834cf1a77e7288ce27bed76edf3db7","resource_binding_sha256":"2e31bb0e743b776d69bafec4f22bd5b62c785e41c9568b1a0b92cd2caa5f61cf","rollback_sha256":"5a518dfaa3cd7cde371d07ad3ed100fdcecb0e0fbee283b5bd5445e50497395a","state_machine_sha256":"8cd0bc5ff63ab8fa54510c92834481ce7fc64561398aa9427c6ad9f7423de0d3"},"state_machine":{"current_state":"AUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT","decision_full_gate_consumes_new_authority":false,"global_single_use_proved":false,"initial_state":"UNRECORDED_NO_AUTHORITY","positive_provider_authority_state_representable":false,"runtime_authority_state_representable":false,"states":["UNRECORDED_NO_AUTHORITY","AUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT","REJECTED_FAIL_CLOSED","CONSUMED_SCOPE_COMPLETE","INVALIDATED_REQUIRES_NEW_DECISION"],"terminal_states":["REJECTED_FAIL_CLOSED","CONSUMED_SCOPE_COMPLETE","INVALIDATED_REQUIRES_NEW_DECISION"],"transitions":[{"event":"OWNER_CONTINUES_NEXT_BOUNDED_BOOTSTRAP_TRUST_DECISION_PATH","from_state":"UNRECORDED_NO_AUTHORITY","to_state":"AUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT"},{"event":"OWNER_HOLDS_OR_REJECTS","from_state":"UNRECORDED_NO_AUTHORITY","to_state":"REJECTED_FAIL_CLOSED"},{"event":"EXACT_AUTHORIZED_SUCCESSOR_INTEGRATED_AND_FULL_GATE_PASSES","from_state":"AUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT","to_state":"CONSUMED_SCOPE_COMPLETE"},{"event":"OWNER_REVOKES_OR_BASELINE_UNIT_ALGORITHM_MESSAGE_DOMAIN_TRUST_RESOURCE_BUDGET_NETWORK_CREDENTIAL_ENDPOINT_OR_REVIEWER_TOPOLOGY_DRIFTS","from_state":"AUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT","to_state":"INVALIDATED_REQUIRES_NEW_DECISION"}]},"status":"REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_SCOPE_RECORDED_ZERO_EXTERNAL_SPEND_NO_RUNTIME_OR_PROVIDER_AUTHORITY"}'''
EXPECTED_UNSIGNED_RECEIPT_JSON = r'''{"all_nonclaims_explicit":true,"allowed_operation_count":8,"authorization_effective_only_after_integrated_full_gate":true,"authorized_candidate_surface_component_count":1,"authorized_component_contract_sha256":"6982a387d0481c7603053971ce6b2b60bebadb32aea3eb2c22b1f2ae5bd73b3c","authorized_local_threat_specification_count":1,"authorized_local_threat_specifications":"T05","bootstrap_trust_authentication_implemented":false,"boundary_sha256":"ee43100a159b00f5e97c53b312e6d056e6e91cfcb908ff3acd52b35481f4cdc9","component_runtime_network":false,"credential_handle_count":0,"credential_path_count":0,"current_decision_candidate_surface_components_implemented":0,"current_state":"AUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT","date":"2026-07-17","decision":"AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED","decision_record_sha256":"ac37eb0c627512842a2e046dcba98b767ff7356dd7c728dc882e1e8baef35f0b","distinct_synthetic_track_profiles":true,"downstream_gates_authorized":0,"external_paid_spend_cap":0,"forbidden_operation_count":28,"future_successor_candidate_surface_component_total":1,"future_successor_candidate_surface_components_authorized":1,"future_successor_minimum_independent_reviewer_lane_count":2,"global_single_use_proved":false,"implementation_authority_recorded":true,"implementation_authority_sha256":"8a1737328d04dd0b2d8178d745569d48c25926a47520187f62bd0fcb858a5eb7","implementation_authority_single_use_consumed":false,"implementation_resource_binding_recorded":true,"implementation_scope_decision_recorded":true,"implementation_side_effects_unlocked":"REVERSIBLE_LOCAL_CODE_SCHEMA_TEST_DOCS_FOR_EXACT_NEXT_UNIT_ONLY","isolated_lab_predecessor_surface_components_implemented":2,"local_predecessor_threat_specifications_covered":4,"max_public_key_bytes":32,"max_signature_bytes":64,"mode":"ISOLATED_LAB_FIRST","next_unit":"REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_TRUST_CHAIN_EXACT_KEY_VERSION_DECLARED_ROLE_AND_REVOCATION_VERIFIER_ISOLATED_LAB_IMPLEMENTATION","nonclaim_field_count":67,"nonclaims_sha256":"8a1fdd31d740b46e2793e3218e14257ce8b6bf1a38cbeb389871c621fe797346","owner_cryptographic_identity_verified":false,"owner_semantic_actor_binding_recorded":true,"owner_semantic_actor_label":"pallasting","owner_signature_observed":false,"owner_supplied_numeric_budget_cap":false,"predecessor_authorization_consumption_state":"CONSUMED_SCOPE_COMPLETE","predecessor_implementation_authority_single_use_consumed":true,"predecessor_integration_commit":"3bf8ad3a67ff02a4e717db8e29e89079f66c01cf","predecessor_receipt_content_sha256":"4d5752110ebf0c11197bd8667fb9e79948724f5195465e41c6709d98d6177b8c","production_environment_implementation_authorized":false,"production_ingestion_controls_implemented":0,"production_ingestion_controls_runtime_exercised":0,"production_ingestion_enabled":false,"production_ingestion_implemented":false,"production_security_reviewer_bound":false,"production_shaped_component_code_authorized":true,"production_validated_evidence_items":0,"provider_authority":false,"provider_endpoint_count":0,"real_evidence_items_present":0,"resource_binding_sha256":"2e31bb0e743b776d69bafec4f22bd5b62c785e41c9568b1a0b92cd2caa5f61cf","rollback_sha256":"5a518dfaa3cd7cde371d07ad3ed100fdcecb0e0fbee283b5bd5445e50497395a","runtime_admission_granted":false,"runtime_admission_ready":false,"runtime_authority":false,"runtime_evidence_accepted":0,"runtime_owner_decision_recorded":false,"runtime_owner_identity_bound":false,"runtime_prerequisites_satisfied":0,"runtime_side_effects_unlocked":"NONE","schema":"agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1.receipt.v0","state_machine_sha256":"8cd0bc5ff63ab8fa54510c92834481ce7fc64561398aa9427c6ad9f7423de0d3","status":"REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_SCOPE_RECORDED_ZERO_EXTERNAL_SPEND_NO_RUNTIME_OR_PROVIDER_AUTHORITY","synthetic_track_profile_count":2}'''

EXPECTED_MANIFEST_JSON = r'''{"authorized_component_summary":{"authorized_candidate_surface_component_count":1,"authorized_candidate_surface_components":["BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_VERIFIER"],"authorized_component_contract_sha256":"6982a387d0481c7603053971ce6b2b60bebadb32aea3eb2c22b1f2ae5bd73b3c","authorized_local_threat_specification_count":1,"authorized_local_threat_specifications":["T05"],"bootstrap_trust_authentication_implemented":false,"current_decision_candidate_surface_components_implemented":0,"distinct_synthetic_track_profiles":true,"future_successor_minimum_independent_reviewer_lane_count":2,"required_reviewer_lanes":["CONTRACT_CONFORMANCE_REVIEW","SECURITY_AND_SOURCE_BOUND_GATE_REVIEW"],"synthetic_track_profile_count":2,"synthetic_track_profiles":["MANAGED_SPANNER_CLOUD_KMS","SELF_HOSTED_ETCD_OPENBAO"],"target_production_control":"BOOTSTRAP_TRUST_AUTHENTICATION"},"boundary":{"authorization_effective_only_after_integrated_full_gate":true,"bootstrap_trust_authentication_isolated_lab_implementation_authorized":true,"bootstrap_trust_authentication_isolated_lab_implemented":false,"downstream_gate_count":4,"downstream_gates_authorized":0,"implementation_authority_single_use_consumed":false,"isolated_lab_predecessor_surface_components_implemented":2,"local_predecessor_threat_specifications_covered":4,"owner_handoff_eligible":false,"predecessor_implementation_authority_consumed":true,"production_environment_implementation_authorized":false,"production_ingestion_control_count":14,"production_ingestion_controls_implemented":0,"production_ingestion_controls_runtime_exercised":0,"production_ingestion_enabled":false,"production_ingestion_implemented":false,"production_security_reviewer_bound":false,"production_threat_case_count":20,"production_threat_cases_runtime_exercised":0,"production_validated_evidence_items":0,"provider_authority":false,"real_evidence_items_present":0,"runtime_admission_granted":false,"runtime_admission_ready":false,"runtime_authority":false,"runtime_evidence_accepted":0,"runtime_owner_decision_recorded":false,"runtime_owner_identity_bound":false,"runtime_prerequisite_count":16,"runtime_prerequisites_satisfied":0,"runtime_side_effects_unlocked":"NONE"},"date":"2026-07-17","decision":"AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED","evidence_sha256":{"scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py":"f1168fad03ac6366e8d6501cbd4da3a2969d25cc6ef9f5bf85c0624de9ae545c","scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.py":"DYNAMIC_CHECKER_RAW_SHA256","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv":"79502975f438ed644306a392131d102e2efadae37560b3489c91547a0125e43f","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json":"05f2fad20896cd108f0695253c617cd0c050e80ae947ec4c90f7d7684e3e344b"},"logical_baseline_commit":"d0356dbdbd7239ffab972ee21da81891210a055b","logical_baseline_parents":["3bf8ad3a67ff02a4e717db8e29e89079f66c01cf","20368c626bf34c5a1edd07391014ab8716536e7e"],"logical_baseline_tree":"b40c36c5fe73af3079bf3a81d69480d2555271d8","next_unit":"REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_TRUST_CHAIN_EXACT_KEY_VERSION_DECLARED_ROLE_AND_REVOCATION_VERIFIER_ISOLATED_LAB_IMPLEMENTATION","owner_semantics":{"binding_basis":"ESTABLISHED_PROFILE_PLUS_CURRENT_SESSION_CONTINUITY","cryptographic_identity_verified":false,"directive_observed_in_owner_session":true,"directive_semantics":"CONTINUE_NEXT_BOUNDED_BOOTSTRAP_TRUST_AUTHENTICATION_DECISION_UNIT","implementation_authority_effective_only_after_integrated_full_gate":true,"owner_supplied_numeric_budget_cap":false,"runtime_owner_decision_recorded":false,"runtime_owner_identity_bound":false,"semantic_actor_binding_recorded":true,"semantic_actor_label":"pallasting","semantic_actor_role":"PROJECT_OWNER","signature_observed":false,"source_or_fast_replay_effective_authority":false},"packet":{"all_add_required":true,"modes":{"docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.md":"100644","scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh":"100755","scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py":"100644","scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.py":"100644","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv":"100644","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json":"100644","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_v0.json":"100644"},"path_count":7,"paths":["scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py","scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.py","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_v0.json","docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.md","scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh"]},"predecessor":{"artifact_raw_sha256":{"docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-v1.schema.json":"e8cb4964f86de39b16d553537467006454c720dc8bfa8d36e370189627328f55","docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.md":"a93fd00b9dc43f8b9d3717fd07bf3a2eef734724834d75d122d2e8bbbe6e3149","scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.sh":"464b975d61403759221fd3aa41da4c38de12f4ec946b161100d23edadbc2b174","scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1.py":"bfa3badbe2b467fbed610d5acb42ef21f1aec2ceb2d5ccf2c218fecfe438eed1","scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.py":"76e0960cb9afa0e4e655ec122b600fe489a31acd5a7edf659d2fff4727ef0dcf","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.expected.v0.tsv":"775ecfa5169509a5fe0e5a900d8644f47b6b4cf64a1778c7d4ed52214115c847","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_synthetic_v0.json":"324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_v0.json":"9c7ba09368ebd610452ca2799226c1f57dcb63fedabb0319f4b39bc071277d04"},"authorization_consumption_state":"CONSUMED_SCOPE_COMPLETE","bootstrap_trust_authentication_authorized":false,"bootstrap_trust_authentication_implemented":false,"fast_stdout_line_count":82,"fast_stdout_sha256":"f20cbe534841e28c875020c15524ab58d6b6b073c9e3e4dc542ccb56876aa194","full_stdout_line_count":83,"full_stdout_sha256":"dc60317aa4b6048f3763145127bbffe5133e411cfee4ae1740cdf8bc431d8a6b","gate_path":"scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.sh","gate_raw_sha256":"464b975d61403759221fd3aa41da4c38de12f4ec946b161100d23edadbc2b174","implementation_authority_single_use_consumed":true,"integration_commit":"3bf8ad3a67ff02a4e717db8e29e89079f66c01cf","integration_parents":["7ef0f8e9b8048fbd1b308ca2a1d708138a615ed9","e5012eb3fd6742ceaecedf4b36adbee8ecfeb054"],"integration_tree":"1bb4b0d851bb4c1ce8a7bf91cbc489168ae41433","manifest_path":"scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_v0.json","manifest_raw_sha256":"9c7ba09368ebd610452ca2799226c1f57dcb63fedabb0319f4b39bc071277d04","receipt_content_sha256":"4d5752110ebf0c11197bd8667fb9e79948724f5195465e41c6709d98d6177b8c","source_commit":"e5012eb3fd6742ceaecedf4b36adbee8ecfeb054","source_parent":"fa0cb9f088e0da2c55c92efde860d9521d4b7493","source_tree":"efcccdc55d11b0ba84bee37f891121ac987404d4"},"resource_binding":{"allowed_resource_classes":["EXISTING_LOCAL_CPU_AND_MEMORY","ISOLATED_AGENT_BRIDGE_WORKTREE","PRIVATE_LOCAL_TEST_SCRATCH"],"component_runtime_network":false,"credential_handle_count":0,"credential_path_count":0,"currency_scope":"ALL_CURRENCIES_ZERO_ONLY","effective_external_paid_spend_cap":0,"max_private_scratch_checkpoint_bytes":67108864,"max_public_key_bytes":32,"max_signature_bytes":64,"owner_supplied_numeric_budget_cap":false,"private_key_or_seed_material_authorized":false,"production_resource_authority_bound":false,"production_trust_root_binding":"NONE","provider_endpoint_count":0,"signing_or_key_generation_authorized":false,"test_data_scope":"COMMITTED_NONSECRET_PUBLIC_ONLY_SYNTHETIC_KAT_NO_SEEDS_NO_PRIVATE_KEYS"},"results":{"all_nonclaims_explicit":true,"allowed_operation_count":8,"authorized_component_contract_sha256":"6982a387d0481c7603053971ce6b2b60bebadb32aea3eb2c22b1f2ae5bd73b3c","boundary_sha256":"ee43100a159b00f5e97c53b312e6d056e6e91cfcb908ff3acd52b35481f4cdc9","content_sha256":"b15c3a545502dcaf47e4c297d98cd90ce01dfe93c70b93a4cf3771c4b1a48315","decision_provenance_sha256":"645775c985782fcd1553b146094217bb2d4b6e1c6800aed7091103a078cb1237","decision_record_sha256":"ac37eb0c627512842a2e046dcba98b767ff7356dd7c728dc882e1e8baef35f0b","forbidden_operation_count":28,"implementation_authority_sha256":"8a1737328d04dd0b2d8178d745569d48c25926a47520187f62bd0fcb858a5eb7","nonclaim_field_count":67,"nonclaims_sha256":"8a1fdd31d740b46e2793e3218e14257ce8b6bf1a38cbeb389871c621fe797346","owner_implementation_actor_sha256":"6842a9cfc98d8c0b7e0189f10d41b1470d834cf1a77e7288ce27bed76edf3db7","resource_binding_sha256":"2e31bb0e743b776d69bafec4f22bd5b62c785e41c9568b1a0b92cd2caa5f61cf","rollback_sha256":"5a518dfaa3cd7cde371d07ad3ed100fdcecb0e0fbee283b5bd5445e50497395a","state_count":5,"state_machine_sha256":"8cd0bc5ff63ab8fa54510c92834481ce7fc64561398aa9427c6ad9f7423de0d3","transition_count":4},"schema":"agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_manifest.v0","status":"REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_SCOPE_RECORDED_ZERO_EXTERNAL_SPEND_NO_RUNTIME_OR_PROVIDER_AUTHORITY","test_oracle":{"closed_world_negative_tests":"DYNAMIC_CLOSED_WORLD_NEGATIVE_TESTS","directed_negative_tests":"DYNAMIC_DIRECTED_NEGATIVE_TESTS_TOTAL","grounding_matrix_negative_tests":"DYNAMIC_GROUNDING_MATRIX_NEGATIVE_TESTS","json_guard_negative_tests":"DYNAMIC_JSON_GUARD_NEGATIVE_TESTS","overclaim_negative_tests":"DYNAMIC_OVERCLAIM_NEGATIVE_TESTS","predecessor_artifact_hashes_frozen":8,"predecessor_exact_fast_receipt":"PASS","predecessor_exact_full_receipt":"PASS","receipt_negative_tests":"DYNAMIC_RECEIPT_NEGATIVE_TESTS","section_hash_negative_tests":"DYNAMIC_SECTION_HASH_NEGATIVE_TESTS","source_ast_negative_tests":"DYNAMIC_SOURCE_AST_NEGATIVE_TESTS","source_ast_purity":"PASS"}}'''

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

EXPECTED_SELF_TEST_COUNTS: dict[str, int] = {
    "json_guard_negatives": 8,
    "closed_world_negatives": 40,
    "contract_negatives": 37,
    "provenance_negatives": 25,
    "predecessor_negatives": 28,
    "component_profile_negatives": 40,
    "root_chain_negatives": 25,
    "key_version_negatives": 10,
    "revocation_negatives": 8,
    "declared_role_not_t06_negatives": 15,
    "resource_negatives": 41,
    "state_negatives": 35,
    "overclaim_negatives": 150,
    "section_hash_negatives": 9,
    "receipt_negatives": 74,
    "source_ast_negatives": 10,
    "directed_negative_tests": 555,
}


class CheckError(ValueError):
    """Stable independent checker error."""


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise CheckError(f"{code}: {message}")


def exact_keys(value: Mapping[str, Any], expected: Iterable[str], code: str) -> None:
    require(type(value) is dict and set(value) == set(expected),
            code, "closed-world key set drift")


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
    require(type(domain) is str and domain.isascii(),
            "E_HASH_DOMAIN", "domain must be ASCII")
    return hashlib.sha256(
        domain.encode("ascii") + b"\0" + canonical_bytes(value)
    ).hexdigest()


def is_sha256(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def checked_path(relative: str, *, required: bool = True) -> Path:
    parsed = PurePosixPath(relative)
    require(
        not parsed.is_absolute() and ".." not in parsed.parts
        and str(parsed) == relative,
        "E_PATH",
        relative,
    )
    cursor = ROOT
    for component in parsed.parts:
        cursor = cursor / component
        require(not cursor.is_symlink(), "E_PATH_SYMLINK", relative)
    if required:
        require(cursor.is_file() and not cursor.is_symlink(), "E_FILE", relative)
    else:
        require(not cursor.exists() or (cursor.is_file() and not cursor.is_symlink()),
                "E_FILE_TYPE", relative)
    if cursor.exists():
        resolved = cursor.resolve()
        require(ROOT == resolved or ROOT in resolved.parents, "E_PATH_ESCAPE", relative)
    return cursor


def read_bytes(relative: str) -> bytes:
    raw = checked_path(relative).read_bytes()
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
        text_value = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text_value,
            object_pairs_hook=_duplicate_safe_object,
            parse_int=_bounded_integer,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except UnicodeDecodeError as error:
        raise CheckError(f"E_UTF8: {label}") from error
    require(type(value) is dict, "E_JSON_ROOT", label)
    validate_json_value(value)
    return value


def read_json(relative: str) -> dict[str, Any]:
    return parse_json_bytes(read_bytes(relative), relative)


def embedded_json(text_value: str, label: str) -> dict[str, Any]:
    return parse_json_bytes(text_value.encode("utf-8"), label)


def check_decoder_guards() -> int:
    probes = (
        b'{"a":1,"a":2}',
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b'{"value":-Infinity}',
        b'{"value":9223372036854775808}',
        b'{"value":-9223372036854775809}',
        b'{"value":1.25}',
        b'\xef\xbb\xbf{"value":1}',
    )
    for index, raw in enumerate(probes):
        try:
            parse_json_bytes(raw, f"guard-{index}")
        except CheckError:
            continue
        raise CheckError(f"E_JSON_GUARD_PROBE: {index}")
    return len(probes)


def expected_section_hashes(record: Mapping[str, Any]) -> dict[str, str]:
    return {
        f"{section}_sha256": domain_sha256(
            DOMAIN_PREFIXES[section], record[section]
        )
        for section in HASHED_SECTIONS
    }


def verify_frozen_raw_inputs(*, include_expected: bool) -> None:
    require(raw_sha256(SOURCE_REL) == SOURCE_RAW_SHA256,
            "E_SOURCE_RAW_HASH", SOURCE_REL)
    require(raw_sha256(DECISION_REL) == DECISION_RAW_SHA256,
            "E_DECISION_RAW_HASH", DECISION_REL)
    if include_expected:
        require(raw_sha256(EXPECTED_REL) == EXPECTED_RAW_SHA256,
                "E_EXPECTED_RAW_HASH", EXPECTED_REL)


def validate_predecessor_receipt_text(text_value: str) -> None:
    require(text_value == PREDECESSOR_EXPECTED_TSV,
            "E_PREDECESSOR_RECEIPT", "exact frozen receipt bytes")
    lines = text_value.splitlines()
    require(len(lines) == 40, "E_PREDECESSOR_RECEIPT_LINES", str(len(lines)))
    require(
        lines[-1]
        == "content_sha256\t" + PREDECESSOR_RECEIPT_CONTENT_SHA256,
        "E_PREDECESSOR_RECEIPT_CONTENT",
        "40-line receipt content binding",
    )


def verify_predecessor_artifacts(record: Mapping[str, Any]) -> None:
    require(len(PREDECESSOR_RAW_SHA256) == 8,
            "E_PREDECESSOR_ARTIFACT_COUNT", "exactly eight artifacts")
    for relative, expected_hash in PREDECESSOR_RAW_SHA256.items():
        require(raw_sha256(relative) == expected_hash,
                "E_PREDECESSOR_RAW_HASH", relative)
    validate_predecessor_receipt_text(read_text(PREDECESSOR_EXPECTED_REL))
    predecessor = record["predecessor"]
    require(
        exact_equal(predecessor["artifact_raw_sha256"], PREDECESSOR_RAW_SHA256),
        "E_PREDECESSOR_ARTIFACT_BINDING",
        "record does not freeze exact eight artifacts",
    )
    require(
        predecessor["decision_source_baseline_commit"]
        == "d0356dbdbd7239ffab972ee21da81891210a055b"
        and predecessor["decision_source_baseline_parents"]
        == [
            "3bf8ad3a67ff02a4e717db8e29e89079f66c01cf",
            "20368c626bf34c5a1edd07391014ab8716536e7e",
        ]
        and predecessor["decision_source_baseline_tree"]
        == "b40c36c5fe73af3079bf3a81d69480d2555271d8",
        "E_BASELINE_TOPOLOGY",
        "d035 decision baseline drift",
    )
    require(
        predecessor["integration_commit"]
        == "3bf8ad3a67ff02a4e717db8e29e89079f66c01cf"
        and predecessor["integration_parents"]
        == [
            "7ef0f8e9b8048fbd1b308ca2a1d708138a615ed9",
            "e5012eb3fd6742ceaecedf4b36adbee8ecfeb054",
        ]
        and predecessor["integration_tree"]
        == "1bb4b0d851bb4c1ce8a7bf91cbc489168ae41433"
        and predecessor["source_commit"]
        == "e5012eb3fd6742ceaecedf4b36adbee8ecfeb054"
        and predecessor["source_parent"]
        == "fa0cb9f088e0da2c55c92efde860d9521d4b7493",
        "E_PREDECESSOR_TOPOLOGY",
        "3bf predecessor lineage drift",
    )
    require(
        predecessor["authorization_consumption_state"] == "CONSUMED_SCOPE_COMPLETE"
        and predecessor["implementation_authority_single_use_consumed"] is True
        and predecessor["receipt_content_sha256"]
        == PREDECESSOR_RECEIPT_CONTENT_SHA256,
        "E_PREDECESSOR_AUTHORITY",
        "predecessor authority/receipt binding drift",
    )


def validate_exact_tree(actual: Any, expected: Any, path: str = "record") -> None:
    require(type(actual) is type(expected), "E_FROZEN_TYPE", path)
    if type(expected) is dict:
        exact_keys(actual, set(expected), "E_FROZEN_KEYS")
        for key in sorted(expected):
            validate_exact_tree(actual[key], expected[key], f"{path}.{key}")
        return
    if type(expected) is list:
        require(len(actual) == len(expected), "E_FROZEN_LIST_LENGTH", path)
        for index, expected_item in enumerate(expected):
            validate_exact_tree(actual[index], expected_item, f"{path}[{index}]")
        return
    require(actual == expected, "E_FROZEN_VALUE", path)


def validate_semantic_contract(record: Mapping[str, Any]) -> None:
    component = record["authorized_component_contract"]
    algorithm = component["algorithm_profile"]
    require(
        algorithm["algorithm"] == "ED25519"
        and algorithm["signature_scheme"]
        == "ED25519_PURE_RFC8032_NO_CONTEXT_NO_PREHASH"
        and algorithm["external_prehash_allowed"] is False
        and algorithm["public_key_encoding"]
        == "RAW_32_BYTE_RFC8032_CANONICAL_POINT"
        and algorithm["signature_encoding"]
        == "RAW_64_BYTE_RFC8032_CANONICAL_R_AND_SCALAR"
        and algorithm["public_key_prime_subgroup_required"] is True
        and algorithm["signature_scalar_less_than_group_order_required"] is True
        and algorithm["small_order_or_identity_points_rejected"] is True,
        "E_COMPONENT_ALGORITHM",
        "exact Ed25519 verification profile drift",
    )
    input_topology = component["input_topology"]
    require(
        input_topology["authentication_metadata_detached"] is True
        and input_topology[
            "production_and_unknown_mode_rejected_before_any_input_observation"
        ] is True
        and input_topology["trust_policy_may_be_sourced_from_authentication_bundle"]
        is False
        and input_topology["trust_policy_may_be_sourced_from_envelope"] is False,
        "E_COMPONENT_INPUT_TOPOLOGY",
        "detached separately-injected trust boundary drift",
    )
    trust_chain = component["trust_chain_profile"]
    require(
        trust_chain["exact_positive_key_version_required"] is True
        and trust_chain["latest_or_zero_key_version_allowed"] is False
        and trust_chain["maximum_chain_entries"] == 3
        and trust_chain["maximum_trust_roots"] == 2
        and trust_chain["root_injection_from_untrusted_bundle_allowed"] is False
        and trust_chain["separately_injected_trust_policy_required"] is True
        and trust_chain["trust_on_first_use_allowed"] is False,
        "E_ROOT_CHAIN",
        "root-chain or exact-version closure drift",
    )
    revocation = component["revocation_profile"]
    require(
        revocation["frozen_snapshot_is_currentness"] is False
        and revocation["self_asserted_active_state_allowed"] is False
        and revocation["unknown_state"] == "UNKNOWN_FAIL_CLOSED",
        "E_REVOCATION",
        "frozen revocation fail-closed boundary drift",
    )
    role = component["role_boundary"]
    require(
        role["declared_role"] == "SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY"
        and role["declared_role_cryptographically_authenticated_in_kat"] is True
        and role["declared_role_is_role_scope_authorization"] is False
        and role["signer_role_scope_authorization_control_implemented"] is False
        and role["track_subject_binding_control_implemented"] is False,
        "E_DECLARED_ROLE",
        "declared role became scope authorization",
    )
    profiles = component["synthetic_track_profiles"]
    require(
        [profile["track_id"] for profile in profiles]
        == ["MANAGED_SPANNER_CLOUD_KMS", "SELF_HOSTED_ETCD_OPENBAO"],
        "E_TRACK_PROFILE_ORDER",
        "exact two-track order drift",
    )
    profile_sets: list[set[str]] = []
    for profile in profiles:
        require(
            profile["exact_chain_order"]
            == [
                profile["root"]["key_id"],
                profile["issuer"]["key_id"],
                profile["leaf"]["key_id"],
            ],
            "E_TRACK_CHAIN_ORDER",
            profile["track_id"],
        )
        require(
            profile["leaf"]["active_key_version"]
            != profile["leaf"]["revoked_key_version"],
            "E_TRACK_KEY_VERSION",
            profile["track_id"],
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
        require(len(critical_values) == 14,
                "E_TRACK_PROFILE_ALIAS", profile["track_id"])
        profile_sets.append(critical_values)
    require(profile_sets[0].isdisjoint(profile_sets[1]),
            "E_TRACK_SUBSTITUTION", "track profile values overlap")
    authority = record["implementation_authority"]
    boundary = record["boundary"]
    require(
        authority["authorized_candidate_surface_component_count"] == 1
        and authority["authorized_local_threat_specifications"] == ["T05"]
        and boundary["authorized_future_local_threat_specifications"] == ["T05"]
        and "T06" not in authority["authorized_local_threat_specifications"]
        and authority["effective_only_after_integrated_full_gate"] is True
        and authority["non_transitive"] is True
        and authority["runtime_import_authorized"] is False
        and authority["runtime_registration_authorized"] is False
        and authority["subdelegation_authorized"] is False,
        "E_AUTHORITY_SCOPE",
        "T05-only non-transitive implementation authority drift",
    )


def validate_semantic_resources_state_and_nonclaims(
    record: Mapping[str, Any],
) -> None:
    resources = record["resource_binding"]
    limits = resources["component_limits"]
    require(
        resources["component_runtime_network"] is False
        and resources["ambient_or_system_trust_store_allowed"] is False
        and resources["provider_endpoints"] == []
        and resources["credential_handles"] == []
        and resources["credential_paths"] == []
        and resources["effective_external_paid_spend_cap"] == 0
        and resources["private_key_or_seed_material_authorized"] is False
        and resources["signing_or_key_generation_authorized"] is False
        and resources["production_resource_authority_bound"] is False,
        "E_RESOURCE_CLOSURE",
        "offline public-only zero-spend resource closure drift",
    )
    require(
        limits["max_public_key_bytes"] == 32
        and limits["max_signature_bytes"] == 64
        and limits["max_chain_entries"] == 3
        and limits["max_trust_roots"] == 2
        and limits["max_signature_verifications_per_review"] == 3
        and limits["max_private_scratch_bytes"] == 67108864,
        "E_COMPONENT_LIMITS",
        "bounded cryptographic/resource profile drift",
    )
    state = record["state_machine"]
    require(
        state["states"]
        == [
            "UNRECORDED_NO_AUTHORITY",
            CURRENT_STATE,
            "REJECTED_FAIL_CLOSED",
            "CONSUMED_SCOPE_COMPLETE",
            "INVALIDATED_REQUIRES_NEW_DECISION",
        ]
        and state["current_state"] == CURRENT_STATE
        and state["decision_full_gate_consumes_new_authority"] is False
        and state["global_single_use_proved"] is False
        and state["runtime_authority_state_representable"] is False
        and state["positive_provider_authority_state_representable"] is False
        and len(state["transitions"]) == 4,
        "E_STATE_MACHINE",
        "exact fail-closed state graph drift",
    )
    boundary = record["boundary"]
    require(
        boundary["current_decision_candidate_surface_components_implemented"] == 0
        and boundary["isolated_lab_predecessor_surface_components_implemented"] == 2
        and boundary["local_predecessor_threat_specifications_covered"] == 4
        and boundary[
            "bootstrap_trust_authentication_isolated_lab_implemented"
        ] is False
        and boundary["production_ingestion_control_count"] == 14
        and boundary["production_ingestion_controls_implemented"] == 0
        and boundary["production_ingestion_controls_runtime_exercised"] == 0
        and boundary["downstream_gates_authorized"] == 0
        and boundary["runtime_authority"] is False
        and boundary["provider_authority"] is False,
        "E_BOUNDARY",
        "implementation/production accounting drift",
    )
    require(
        len(record["nonclaims"]) == 67
        and all(value is False for value in record["nonclaims"].values()),
        "E_NONCLAIMS",
        "all 67 denied claims must remain false",
    )


def validate_record(
    record: dict[str, Any],
    expected_record: Mapping[str, Any],
    *,
    enforce_frozen_hashes: bool = True,
) -> None:
    validate_json_value(record)
    validate_exact_tree(record, expected_record)
    require(
        record["schema"] == RECORD_SCHEMA
        and type(record["schema_version"]) is int
        and record["schema_version"] == 1
        and record["date"] == DATE
        and record["status"] == STATUS
        and record["decision"] == DECISION
        and record["next_unit"] == NEXT_UNIT,
        "E_RECORD_IDENTITY",
        "record identity drift",
    )
    derived_hashes = expected_section_hashes(record)
    require(exact_equal(record["section_sha256"], derived_hashes),
            "E_SECTION_HASH", "independently-derived section hash drift")
    require(all(is_sha256(value) for value in derived_hashes.values()),
            "E_SECTION_HASH_FORMAT", "lowercase SHA-256 required")
    if enforce_frozen_hashes:
        require(exact_equal(derived_hashes, FROZEN_SECTION_HASHES),
                "E_SECTION_FROZEN_HASH", "frozen section drift")
        require(
            hashlib.sha256(canonical_bytes(record)).hexdigest()
            == DECISION_RECORD_CANONICAL_SHA256,
            "E_RECORD_CANONICAL_HASH",
            "canonical record drift",
        )
        require(
            domain_sha256(DOMAIN_PREFIXES["decision_record"], record)
            == DECISION_RECORD_DOMAIN_SHA256,
            "E_RECORD_DOMAIN_HASH",
            "domain-separated decision binding drift",
        )
    verify_predecessor_artifacts(record)
    validate_semantic_contract(record)
    validate_semantic_resources_state_and_nonclaims(record)


def build_expected_receipt(record: Mapping[str, Any]) -> dict[str, Any]:
    receipt = embedded_json(
        EXPECTED_UNSIGNED_RECEIPT_JSON, "embedded-unsigned-receipt"
    )
    exact_keys(receipt, set(TSV_FIELDS) - {"content_sha256"},
               "E_RECEIPT_TEMPLATE_KEYS")
    hashes = expected_section_hashes(record)
    derived_bindings = {
        "authorized_component_contract_sha256":
            hashes["authorized_component_contract_sha256"],
        "implementation_authority_sha256":
            hashes["implementation_authority_sha256"],
        "resource_binding_sha256": hashes["resource_binding_sha256"],
        "state_machine_sha256": hashes["state_machine_sha256"],
        "rollback_sha256": hashes["rollback_sha256"],
        "boundary_sha256": hashes["boundary_sha256"],
        "nonclaims_sha256": hashes["nonclaims_sha256"],
        "decision_record_sha256":
            domain_sha256(DOMAIN_PREFIXES["decision_record"], record),
        "predecessor_receipt_content_sha256":
            PREDECESSOR_RECEIPT_CONTENT_SHA256,
    }
    for field, value in derived_bindings.items():
        require(receipt[field] == value, "E_RECEIPT_TEMPLATE_BINDING", field)
        receipt[field] = value
    require(
        receipt["schema"] == RECEIPT_SCHEMA
        and receipt["status"] == STATUS
        and receipt["decision"] == DECISION
        and receipt["date"] == DATE
        and receipt["mode"] == MODE
        and receipt["next_unit"] == NEXT_UNIT
        and receipt["allowed_operation_count"]
        == len(record["implementation_authority"]["allowed_operations"])
        and receipt["forbidden_operation_count"]
        == len(record["implementation_authority"]["forbidden_operations"])
        and receipt["nonclaim_field_count"] == len(record["nonclaims"])
        and receipt["synthetic_track_profile_count"]
        == len(record["authorized_component_contract"]["synthetic_track_profiles"])
        and receipt["max_public_key_bytes"]
        == record["resource_binding"]["component_limits"]["max_public_key_bytes"]
        and receipt["max_signature_bytes"]
        == record["resource_binding"]["component_limits"]["max_signature_bytes"],
        "E_RECEIPT_TEMPLATE",
        "independent scalar receipt reconstruction drift",
    )
    receipt["content_sha256"] = domain_sha256(
        DOMAIN_PREFIXES["receipt"], receipt
    )
    require(receipt["content_sha256"] == RECEIPT_CONTENT_SHA256,
            "E_RECEIPT_CONTENT_HASH", "frozen receipt content drift")
    return receipt


def independent_render_tsv(receipt: Mapping[str, Any]) -> str:
    exact_keys(receipt, TSV_FIELDS, "E_RECEIPT_KEYS")
    lines: list[str] = []
    for field in TSV_FIELDS:
        value = receipt[field]
        require(type(value) in (str, int, bool), "E_TSV_SCALAR", field)
        rendered = "true" if value is True else "false" if value is False else str(value)
        require("\t" not in rendered and "\n" not in rendered,
                "E_TSV_INJECTION", field)
        lines.append(f"{field}\t{rendered}")
    return "\n".join(lines) + "\n"


def validate_receipt(
    receipt: dict[str, Any],
    record: Mapping[str, Any],
) -> str:
    expected = build_expected_receipt(record)
    require(exact_equal(receipt, expected), "E_RECEIPT", "scalar receipt drift")
    require(receipt["decision_record_sha256"] == DECISION_RECORD_DOMAIN_SHA256,
            "E_RECEIPT_RECORD_HASH", "decision binding drift")
    return independent_render_tsv(receipt)


def verify_expected_tsv(rendered: str) -> None:
    require(raw_sha256(EXPECTED_REL) == EXPECTED_RAW_SHA256,
            "E_EXPECTED_RAW_HASH", EXPECTED_REL)
    require(read_text(EXPECTED_REL) == rendered,
            "E_EXPECTED_TSV", "frozen expected TSV drift")
    require(len(rendered.splitlines()) == 74,
            "E_EXPECTED_LINES", "receipt must have 74 lines")


def collect_dynamic_tags(value: Any) -> list[str]:
    placeholders: list[str] = []
    if type(value) is dict:
        for item in value.values():
            placeholders.extend(collect_dynamic_tags(item))
    elif type(value) is list:
        for item in value:
            placeholders.extend(collect_dynamic_tags(item))
    elif type(value) is str and value.startswith("DYNAMIC_"):
        placeholders.append(value)
    return placeholders


def manifest_oracle_counts() -> dict[str, int]:
    grounding_keys = (
        "contract_negatives",
        "provenance_negatives",
        "predecessor_negatives",
        "component_profile_negatives",
        "root_chain_negatives",
        "key_version_negatives",
        "revocation_negatives",
        "declared_role_not_t06_negatives",
        "resource_negatives",
        "state_negatives",
    )
    return {
        "closed_world_negative_tests":
            EXPECTED_SELF_TEST_COUNTS["closed_world_negatives"],
        "directed_negative_tests":
            EXPECTED_SELF_TEST_COUNTS["directed_negative_tests"],
        "grounding_matrix_negative_tests": sum(
            EXPECTED_SELF_TEST_COUNTS[key] for key in grounding_keys
        ),
        "json_guard_negative_tests":
            EXPECTED_SELF_TEST_COUNTS["json_guard_negatives"],
        "overclaim_negative_tests":
            EXPECTED_SELF_TEST_COUNTS["overclaim_negatives"],
        "receipt_negative_tests":
            EXPECTED_SELF_TEST_COUNTS["receipt_negatives"],
        "section_hash_negative_tests":
            EXPECTED_SELF_TEST_COUNTS["section_hash_negatives"],
        "source_ast_negative_tests":
            EXPECTED_SELF_TEST_COUNTS["source_ast_negatives"],
    }


def verify_manifest_evidence() -> None:
    manifest = read_json(MANIFEST_REL)
    require(manifest.get("schema") == MANIFEST_SCHEMA,
            "E_MANIFEST_SCHEMA", "manifest schema drift")
    evidence = manifest.get("evidence_sha256")
    require(type(evidence) is dict,
            "E_MANIFEST_EVIDENCE", "missing evidence map")
    exact_keys(evidence, MANIFEST_EVIDENCE_PATHS,
               "E_MANIFEST_EVIDENCE_KEYS")
    actual_evidence = {
        relative: raw_sha256(relative) for relative in MANIFEST_EVIDENCE_PATHS
    }
    require(
        exact_equal(evidence, actual_evidence)
        and evidence[CHECKER_REL] == raw_sha256(CHECKER_REL)
        and evidence[SOURCE_REL] == SOURCE_RAW_SHA256
        and evidence[DECISION_REL] == DECISION_RAW_SHA256
        and evidence[EXPECTED_REL] == EXPECTED_RAW_SHA256,
        "E_MANIFEST_EVIDENCE_HASH",
        "dynamic checker or static evidence binding drift",
    )

    expected_manifest = embedded_json(
        EXPECTED_MANIFEST_JSON, "embedded-manifest-contract"
    )
    placeholders = collect_dynamic_tags(expected_manifest)
    require(
        len(placeholders) == 9 and len(set(placeholders)) == 9,
        "E_MANIFEST_TEMPLATE_PLACEHOLDERS",
        "expected one checker digest plus eight unique oracle placeholders",
    )
    template_evidence = expected_manifest["evidence_sha256"]
    exact_keys(template_evidence, MANIFEST_EVIDENCE_PATHS,
               "E_MANIFEST_TEMPLATE_EVIDENCE_KEYS")
    require(
        template_evidence[SOURCE_REL] == SOURCE_RAW_SHA256
        and template_evidence[DECISION_REL] == DECISION_RAW_SHA256
        and template_evidence[EXPECTED_REL] == EXPECTED_RAW_SHA256
        and template_evidence[CHECKER_REL] == "DYNAMIC_CHECKER_RAW_SHA256",
        "E_MANIFEST_TEMPLATE_EVIDENCE",
        "static/dynamic evidence template drift",
    )
    oracle = expected_manifest["test_oracle"]
    oracle_placeholders = {
        "closed_world_negative_tests": "DYNAMIC_CLOSED_WORLD_NEGATIVE_TESTS",
        "directed_negative_tests": "DYNAMIC_DIRECTED_NEGATIVE_TESTS_TOTAL",
        "grounding_matrix_negative_tests":
            "DYNAMIC_GROUNDING_MATRIX_NEGATIVE_TESTS",
        "json_guard_negative_tests": "DYNAMIC_JSON_GUARD_NEGATIVE_TESTS",
        "overclaim_negative_tests": "DYNAMIC_OVERCLAIM_NEGATIVE_TESTS",
        "receipt_negative_tests": "DYNAMIC_RECEIPT_NEGATIVE_TESTS",
        "section_hash_negative_tests": "DYNAMIC_SECTION_HASH_NEGATIVE_TESTS",
        "source_ast_negative_tests": "DYNAMIC_SOURCE_AST_NEGATIVE_TESTS",
    }
    for field, placeholder in oracle_placeholders.items():
        require(oracle[field] == placeholder,
                "E_MANIFEST_TEMPLATE_ORACLE", field)
    for field, count in manifest_oracle_counts().items():
        oracle[field] = count

    normalized_manifest = copy.deepcopy(manifest)
    normalized_manifest["evidence_sha256"][CHECKER_REL] = (
        "DYNAMIC_CHECKER_RAW_SHA256"
    )
    validate_exact_tree(normalized_manifest, expected_manifest, "manifest")
    require(
        not collect_dynamic_tags(manifest),
        "E_MANIFEST_UNRESOLVED_PLACEHOLDER",
        "final default path rejects every unresolved placeholder",
    )


def load_module(relative: str, name: str) -> ModuleType:
    path = checked_path(relative).resolve()
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None,
            "E_MODULE_LOAD", name)
    require(spec.origin is not None and Path(spec.origin).resolve() == path,
            "E_MODULE_ORIGIN", name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    require(Path(module.__file__).resolve() == path,
            "E_MODULE_PATH", name)
    return module


def check_source_ast_text(text_value: str) -> None:
    tree = ast.parse(text_value, filename=SOURCE_REL)
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
            require(
                node.level == 0
                and module_name.split(".", 1)[0] in allowed_imports,
                "E_AST_IMPORT",
                module_name,
            )
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in forbidden_calls,
                        "E_AST_CALL", node.func.id)
            elif isinstance(node.func, ast.Attribute):
                require(node.func.attr not in forbidden_attributes,
                        "E_AST_CALL", node.func.attr)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            raise CheckError("E_AST_MUTABLE_SCOPE: global/nonlocal")
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom)):
            raise CheckError("E_AST_ASYNC_OR_GENERATOR: unsupported execution surface")
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            public_functions.add(node.name)
        elif isinstance(node, ast.ClassDef):
            bases = [base.id for base in node.bases if isinstance(base, ast.Name)]
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
        "E_AST_PUBLIC_FUNCTIONS",
        str(sorted(public_functions)),
    )
    require(
        classes
        == [("BootstrapTrustAuthorityDecisionReviewError", ["ValueError"])],
        "E_AST_CLASSES",
        str(classes),
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
        return "0" * 64 if is_sha256(value) else value + "_MUTATED"
    if value is None:
        return 0
    if type(value) is list:
        return ["MUTATED"] if not value else list(reversed(value))
    if type(value) is dict:
        mutated = copy.deepcopy(value)
        mutated["extra"] = False
        return mutated
    raise CheckError("E_MUTATOR_TYPE: unsupported value")


def leaf_paths(value: Any, prefix: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    result: list[tuple[Any, ...]] = []
    if type(value) is dict:
        if not value:
            return [prefix]
        for key in sorted(value):
            result.extend(leaf_paths(value[key], prefix + (key,)))
        return result
    if type(value) is list:
        if not value:
            return [prefix]
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


def mutate_path(record: Mapping[str, Any], path: tuple[Any, ...]) -> dict[str, Any]:
    candidate = copy.deepcopy(dict(record))
    set_path(candidate, path, mutate_scalar(get_path(candidate, path)))
    return candidate


def path_label(path: tuple[Any, ...]) -> str:
    return "-".join(str(component) for component in path)


def rehash_record(record: dict[str, Any]) -> None:
    record["section_sha256"] = expected_section_hashes(record)


def expect_record_rejected_by_both(
    candidate: dict[str, Any],
    expected_record: Mapping[str, Any],
    module: ModuleType,
    label: str,
) -> None:
    expect_rejected(
        lambda: validate_record(
            copy.deepcopy(candidate),
            expected_record,
            enforce_frozen_hashes=False,
        ),
        label + "-independent",
    )
    expect_rejected(
        lambda: module.review_decision(copy.deepcopy(candidate)),
        label + "-source-review",
    )


def exercise_paths(
    paths: Iterable[tuple[Any, ...]],
    category: str,
    record: Mapping[str, Any],
    expected_record: Mapping[str, Any],
    module: ModuleType,
) -> int:
    count = 0
    for path in paths:
        candidate = mutate_path(record, path)
        rehash_record(candidate)
        expect_record_rejected_by_both(
            candidate,
            expected_record,
            module,
            category + "-" + path_label(path),
        )
        count += 1
    return count


def prefixed_leaf_paths(record: Mapping[str, Any], prefix: tuple[Any, ...]) -> list[tuple[Any, ...]]:
    return [
        prefix + suffix for suffix in leaf_paths(get_path(record, prefix))
    ]


def run_self_test(
    module: ModuleType,
    record: dict[str, Any],
    expected_record: Mapping[str, Any],
    receipt: dict[str, Any],
) -> dict[str, int]:
    counts: dict[str, int] = {
        "json_guard_negatives": check_decoder_guards(),
        "closed_world_negatives": 0,
        "contract_negatives": 0,
        "provenance_negatives": 0,
        "predecessor_negatives": 0,
        "component_profile_negatives": 0,
        "root_chain_negatives": 0,
        "key_version_negatives": 0,
        "revocation_negatives": 0,
        "declared_role_not_t06_negatives": 0,
        "resource_negatives": 0,
        "state_negatives": 0,
        "overclaim_negatives": 0,
        "section_hash_negatives": 0,
        "receipt_negatives": 0,
        "source_ast_negatives": 0,
    }

    source_text = read_text(SOURCE_REL)
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
    for index, snippet in enumerate(ast_snippets):
        expect_rejected(
            lambda snippet=snippet: check_source_ast_text(source_text + snippet),
            f"source-ast-{index}",
        )
        counts["source_ast_negatives"] += 1

    for key in sorted(expected_record):
        candidate = copy.deepcopy(record)
        del candidate[key]
        expect_record_rejected_by_both(
            candidate, expected_record, module, f"record-drop-{key}"
        )
        counts["closed_world_negatives"] += 1
    candidate = copy.deepcopy(record)
    candidate["extra"] = False
    expect_record_rejected_by_both(
        candidate, expected_record, module, "record-extra"
    )
    counts["closed_world_negatives"] += 1
    for section in sorted(
        key for key, value in expected_record.items() if type(value) is dict
    ):
        candidate = copy.deepcopy(record)
        candidate[section]["extra"] = False
        if section != "section_sha256":
            rehash_record(candidate)
        expect_record_rejected_by_both(
            candidate, expected_record, module, f"section-extra-{section}"
        )
        counts["closed_world_negatives"] += 1
        candidate = copy.deepcopy(record)
        first_key = sorted(candidate[section])[0]
        del candidate[section][first_key]
        if section != "section_sha256":
            rehash_record(candidate)
        expect_record_rejected_by_both(
            candidate,
            expected_record,
            module,
            f"section-drop-{section}-{first_key}",
        )
        counts["closed_world_negatives"] += 1

    contract_paths = prefixed_leaf_paths(
        record, ("implementation_authority", "allowed_operations")
    )
    contract_paths += prefixed_leaf_paths(
        record, ("implementation_authority", "forbidden_operations")
    )
    contract_paths += [
        ("authorized_component_contract", "trust_domain_family")
    ]
    counts["contract_negatives"] = exercise_paths(
        contract_paths, "contract", record, expected_record, module
    )

    provenance_paths = prefixed_leaf_paths(record, ("decision_provenance",))
    provenance_paths += prefixed_leaf_paths(record, ("owner_implementation_actor",))
    counts["provenance_negatives"] = exercise_paths(
        provenance_paths, "provenance", record, expected_record, module
    )

    predecessor_paths = prefixed_leaf_paths(record, ("predecessor",))
    counts["predecessor_negatives"] = exercise_paths(
        predecessor_paths, "predecessor", record, expected_record, module
    )
    expect_rejected(
        lambda: validate_predecessor_receipt_text(
            PREDECESSOR_EXPECTED_TSV.replace(
                PREDECESSOR_RECEIPT_CONTENT_SHA256, "0" * 64
            )
        ),
        "predecessor-receipt-content",
    )
    counts["predecessor_negatives"] += 1

    component_profile_paths: list[tuple[Any, ...]] = []
    for subsection in (
        "algorithm_profile",
        "authentication_state_ceiling",
        "input_topology",
        "local_scope",
        "reviewer_topology",
    ):
        component_profile_paths += prefixed_leaf_paths(
            record, ("authorized_component_contract", subsection)
        )
    counts["component_profile_negatives"] = exercise_paths(
        component_profile_paths,
        "component-profile",
        record,
        expected_record,
        module,
    )

    root_chain_paths = prefixed_leaf_paths(
        record, ("authorized_component_contract", "trust_chain_profile")
    )
    key_version_paths = [
        path for path in root_chain_paths if "key_version" in path_label(path)
    ]
    root_chain_paths = [
        path for path in root_chain_paths if path not in key_version_paths
    ]
    revocation_paths = prefixed_leaf_paths(
        record, ("authorized_component_contract", "revocation_profile")
    )
    role_paths = prefixed_leaf_paths(
        record, ("authorized_component_contract", "role_boundary")
    )
    track_paths = prefixed_leaf_paths(
        record, ("authorized_component_contract", "synthetic_track_profiles")
    )
    for path in track_paths:
        label = path_label(path)
        if "key_version" in label:
            key_version_paths.append(path)
        elif "revocation" in label or "revoked" in label:
            revocation_paths.append(path)
        elif "role" in label:
            role_paths.append(path)
        else:
            root_chain_paths.append(path)
    counts["root_chain_negatives"] = exercise_paths(
        root_chain_paths, "root-chain", record, expected_record, module
    )
    counts["key_version_negatives"] = exercise_paths(
        key_version_paths, "key-version", record, expected_record, module
    )
    counts["revocation_negatives"] = exercise_paths(
        revocation_paths, "revocation", record, expected_record, module
    )
    counts["declared_role_not_t06_negatives"] = exercise_paths(
        role_paths, "declared-role", record, expected_record, module
    )
    t06_paths = (
        ("authorized_component_contract", "local_scope",
         "authorized_local_threat_specifications", 0),
        ("implementation_authority", "authorized_local_threat_specifications", 0),
        ("boundary", "authorized_future_local_threat_specifications", 0),
    )
    for path in t06_paths:
        candidate = copy.deepcopy(record)
        set_path(candidate, path, "T06")
        rehash_record(candidate)
        expect_record_rejected_by_both(
            candidate, expected_record, module, "t06-" + path_label(path)
        )
        counts["declared_role_not_t06_negatives"] += 1

    resource_paths = prefixed_leaf_paths(record, ("resource_binding",))
    counts["resource_negatives"] = exercise_paths(
        resource_paths, "resource", record, expected_record, module
    )

    state_paths = prefixed_leaf_paths(record, ("state_machine",))
    state_paths += prefixed_leaf_paths(record, ("rollback",))
    counts["state_negatives"] = exercise_paths(
        state_paths, "state", record, expected_record, module
    )

    overclaim_paths: list[tuple[Any, ...]] = []
    sentinel_strings = {
        "NONE",
        "NONE_PRODUCTION_SECURITY_REVIEWER_UNBOUND",
        "NOT_APPLICABLE_NOT_ENABLED",
        "FIXED_KAT_ONLY_NOT_TRUSTED_TIME",
    }
    for section in (
        "authorized_component_contract",
        "boundary",
        "decision_provenance",
        "implementation_authority",
        "nonclaims",
        "owner_implementation_actor",
        "resource_binding",
        "rollback",
        "state_machine",
    ):
        for path in prefixed_leaf_paths(record, (section,)):
            value = get_path(record, path)
            if (
                value is False
                or (type(value) is int and value == 0)
                or (type(value) is list and not value)
                or value in sentinel_strings
            ):
                overclaim_paths.append(path)
    require(len(overclaim_paths) == len(set(overclaim_paths)),
            "E_OVERCLAIM_PATHS", "duplicate directed path")
    counts["overclaim_negatives"] = exercise_paths(
        overclaim_paths, "overclaim", record, expected_record, module
    )

    for hash_key in sorted(FROZEN_SECTION_HASHES):
        candidate = copy.deepcopy(record)
        candidate["section_sha256"][hash_key] = "0" * 64
        expect_record_rejected_by_both(
            candidate, expected_record, module, f"section-hash-{hash_key}"
        )
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
        expect_rejected(
            lambda candidate=candidate_receipt: validate_receipt(candidate, record),
            "receipt-" + field,
        )
        counts["receipt_negatives"] += 1

    counts["directed_negative_tests"] = sum(
        value for key, value in counts.items() if key.endswith("_negatives")
    )
    return counts


def evaluate(mode: str) -> str:
    check_decoder_guards()
    include_expected = mode != "emit"
    verify_frozen_raw_inputs(include_expected=include_expected)
    expected_record = embedded_json(EXPECTED_RECORD_JSON, "embedded-record")
    record = read_json(DECISION_REL)
    validate_record(record, expected_record)
    check_source_ast()
    module = load_module(SOURCE_REL, "_bootstrap_trust_authority_source")
    source_receipt = module.review_decision(copy.deepcopy(record))
    require(type(source_receipt) is dict,
            "E_SOURCE_RECEIPT", "source reviewer did not return object")
    rendered = validate_receipt(source_receipt, record)
    require(module.render_tsv(copy.deepcopy(source_receipt)) == rendered,
            "E_SOURCE_RENDER", "source renderer differs from independent renderer")

    if mode == "emit":
        return rendered
    verify_expected_tsv(rendered)
    if mode == "normal":
        verify_manifest_evidence()
        return rendered

    counts = run_self_test(
        module, record, expected_record, build_expected_receipt(record)
    )
    if EXPECTED_SELF_TEST_COUNTS:
        require(counts == EXPECTED_SELF_TEST_COUNTS,
                "E_SELF_TEST_COUNTS", str(counts))
    ordered_categories = (
        "directed_negative_tests",
        "json_guard_negatives",
        "closed_world_negatives",
        "contract_negatives",
        "provenance_negatives",
        "predecessor_negatives",
        "component_profile_negatives",
        "root_chain_negatives",
        "key_version_negatives",
        "revocation_negatives",
        "declared_role_not_t06_negatives",
        "resource_negatives",
        "state_negatives",
        "overclaim_negatives",
        "section_hash_negatives",
        "receipt_negatives",
        "source_ast_negatives",
    )
    lines = ["self_test\tPASS"]
    for category in ordered_categories:
        lines.append(f"{category}\t{counts[category]}")
    lines.extend(
        (
            "predecessor_artifact_hashes_frozen\t8",
            "predecessor_exact_receipt_lines\t40",
            "source_ast_purity\tPASS",
            "manifest_evidence_validation\tDEFAULT_ONLY",
        )
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--emit-current", action="store_true")
    group.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    mode = "emit" if args.emit_current else "self-test" if args.self_test else "normal"
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
        print(
            "bootstrap trust authority/resource decision pack check failed: "
            + str(error),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
