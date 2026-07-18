#!/usr/bin/env python3
"""Pure reviewer for the isolated-lab implementation-authority decision.

This module reviews one closed-world owner decision record.  The decision
authorizes only the exact next unit's reversible local code, schema, test, and
documentation work.  It does not expose a runtime, provider, credential,
endpoint, production-ingestion, evidence-acceptance, or owner-runtime-decision
API.  The reviewer performs no file, environment, clock, process, network,
provider, credential, random, entropy, or mutable-state I/O.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping


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

PREDECESSOR = {
    "gate_path": (
        "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-"
        "runner-runtime-prerequisite-evidence-packet-offline-integration-and-"
        "production-evidence-ingestion-boundary-review-v1-pack.sh"
    ),
    "gate_raw_sha256": (
        "e2a3e5fd49ebd58697838bc3f7e1860ce511f225a4bdd11ac8f2772bd8087cf7"
    ),
    "integration_commit": "d5bbe55d5d95b1163e287415f437cf77c594135d",
    "integration_parents": [
        "3d03193b645ded944b10a310633be8d6a2c1ab1b",
        "0268990ee74a6a958269d1c07f7d575d0284e6bf",
    ],
    "integration_tree": "6fd22d3e8abba06ae5eab26c9c9ce2af5672ada9",
    "manifest_path": (
        "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
        "injection_runner_runtime_prerequisite_evidence_packet_offline_integration_"
        "and_production_evidence_ingestion_boundary_review_v1_pack_v0.json"
    ),
    "manifest_raw_sha256": (
        "59260f9d4d5e00924739f96de567695dfe326413a01fcb3600703d9efb945b54"
    ),
    "receipt_content_sha256": (
        "7d48eb96d1a87894698d396efba848f90da8076cc3271bd9ac8c5250b0c722fa"
    ),
    "source_commit": "0268990ee74a6a958269d1c07f7d575d0284e6bf",
    "source_parent": "3d03193b645ded944b10a310633be8d6a2c1ab1b",
}

DECISION_PROVENANCE = {
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

ALLOWED_OPERATIONS = [
    "ADD_CLOSED_WORLD_PRODUCTION_EVIDENCE_ENVELOPE_SCHEMA",
    "ADD_BOUNDED_DUPLICATE_SAFE_UTF8_JSON_FRAME_PARSER",
    "ADD_DETERMINISTIC_NONSECRET_ADVERSARIAL_KATS",
    "ADD_PURE_REVIEWER_INDEPENDENT_CHECKER_REPORT_AND_GATE",
    "ADD_SYNTHETIC_PRODUCTION_MODE_SEPARATION",
]

FORBIDDEN_OPERATIONS = [
    "ACCESS_CREDENTIAL_OR_SECRET_MATERIAL",
    "ACCEPT_OR_PERSIST_REAL_EVIDENCE",
    "AUTHORIZE_OR_INJECT_FAULT",
    "AUTHORIZE_OUTPUT_OR_CLAIM",
    "BIND_PRODUCTION_SIGNER_OR_TRUST_ROOT",
    "BIND_PROVIDER_OR_PRODUCTION_ENDPOINT",
    "CALL_PROVIDER_OR_ATTEMPT_WIRE",
    "CREATE_RUNTIME_OR_EXPERIMENT_ROW",
    "DEPLOY_OR_ENABLE_PRODUCTION_INGESTION",
    "ESTABLISH_DURABLE_CUSTODY_OR_REPLAY_LEDGER",
    "LAUNCH_RUNNER_OR_BACKGROUND_DAEMON",
    "PROVISION_PAID_OR_EXTERNAL_RESOURCE",
    "READ_AMBIENT_OR_DEFAULT_CREDENTIAL_CHAIN",
    "REPRESENT_RUNTIME_OWNER_DECISION",
    "SATISFY_RUNTIME_PREREQUISITE",
    "USE_AMBIENT_OR_PRODUCTION_TRUSTED_TIME",
]

IMPLEMENTATION_AUTHORITY = {
    "allowed_operations": ALLOWED_OPERATIONS,
    "authority_class": "REVERSIBLE_CODE_SCHEMA_TEST_DOCUMENTATION_ONLY",
    "current_state": CURRENT_STATE,
    "default_off_required": True,
    "exact_next_unit_authorized": True,
    "forbidden_operations": FORBIDDEN_OPERATIONS,
    "implementation_authority_recorded": True,
    "implementation_scope": (
        "ISOLATED_LAB_CODE_ONLY_EXACT_NEXT_UNIT_SINGLE_USE_NON_TRANSITIVE"
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
    "max_input_frame_bytes": 1048576,
    "max_json_depth": 32,
    "max_object_members": 256,
    "max_parallel_workers": 1,
    "max_private_scratch_bytes": 67108864,
}

RESOURCE_BINDING = {
    "allowed_resource_classes": [
        "EXISTING_LOCAL_CPU_AND_MEMORY",
        "ISOLATED_AGENT_BRIDGE_WORKTREE",
        "PRIVATE_LOCAL_TEST_SCRATCH",
    ],
    "component_limits": COMPONENT_LIMITS,
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
    "resource_scope_id": (
        "EXISTING_LOCAL_WORKTREE_PRIVATE_SCRATCH_AND_LOCAL_COMPUTE_ONLY"
    ),
    "security_reviewer_binding": "NONE_INDEPENDENT_CHECKER_IS_NOT_SECURITY_REVIEW",
    "test_data_scope": "COMMITTED_NONSECRET_FIXTURES_ONLY",
    "trust_root_binding": "NONE",
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
        "event": "OWNER_CONTINUES_RECOMMENDED_PATH_WITH_FAIL_CLOSED_DEFAULTS",
        "from_state": "UNRECORDED_NO_AUTHORITY",
        "to_state": CURRENT_STATE,
    },
    {
        "event": "OWNER_HOLDS_OR_REJECTS",
        "from_state": "UNRECORDED_NO_AUTHORITY",
        "to_state": "REJECTED_FAIL_CLOSED",
    },
    {
        "event": "EXACT_AUTHORIZED_SUCCESSOR_INTEGRATED",
        "from_state": CURRENT_STATE,
        "to_state": "CONSUMED_SCOPE_COMPLETE",
    },
    {
        "event": (
            "OWNER_REVOKES_OR_BASELINE_SCOPE_BUDGET_NETWORK_CREDENTIAL_"
            "ENDPOINT_DRIFTS"
        ),
        "from_state": CURRENT_STATE,
        "to_state": "INVALIDATED_REQUIRES_NEW_DECISION",
    },
]

STATE_MACHINE = {
    "current_state": CURRENT_STATE,
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
    "downstream_gates_authorized": 0,
    "exact_next_unit_authorized": True,
    "implementation_authority_recorded": True,
    "implementation_resource_binding_recorded": True,
    "implementation_scope_decision_recorded": True,
    "implementation_side_effects_unlocked": IMPLEMENTATION_SIDE_EFFECTS,
    "owner_handoff_eligible": False,
    "production_environment_implementation_authorized": False,
    "production_ingestion_controls_implemented": 0,
    "production_ingestion_controls_runtime_exercised": 0,
    "production_ingestion_enabled": False,
    "production_ingestion_implemented": False,
    "production_shaped_component_code_authorized": True,
    "production_validated_evidence_items": 0,
    "provider_authority": False,
    "real_evidence_items_present": 0,
    "runtime_admission_granted": False,
    "runtime_admission_ready": False,
    "runtime_authority": False,
    "runtime_evidence_accepted": 0,
    "runtime_owner_decision_recorded": False,
    "runtime_owner_identity_bound": False,
    "runtime_prerequisites_satisfied": 0,
    "runtime_side_effects_unlocked": "NONE",
}

NONCLAIMS = {
    "any_production_ingestion_control_implemented": False,
    "budget_cap_zero_is_budget_reservation": False,
    "condition_output_authorized": False,
    "credential_or_secret_material_accessed": False,
    "deployment_authorized": False,
    "durable_custody_proved": False,
    "durable_replay_cas_proved": False,
    "evidence_acceptance_authorized": False,
    "experiment_rows_created": False,
    "external_paid_spend_authorized": False,
    "fault_injection_authorized": False,
    "fault_injected": False,
    "git_publication_authority_derived": False,
    "global_single_use_proved": False,
    "independent_checker_is_security_approval": False,
    "owner_signature_observed": False,
    "output_permit_defined": False,
    "paid_resource_provisioned": False,
    "production_credentials_authorized": False,
    "production_endpoint_bound": False,
    "production_environment_implementation_authorized": False,
    "production_ingestion_enabled": False,
    "production_ingestion_implemented": False,
    "production_resource_authority_bound": False,
    "production_rollback_authority_bound": False,
    "production_security_approval": False,
    "production_signer_bound": False,
    "production_trust_root_bound": False,
    "provider_authority": False,
    "provider_called": False,
    "real_evidence_accepted": False,
    "real_evidence_authenticated": False,
    "real_evidence_collected": False,
    "real_evidence_ingested": False,
    "real_evidence_quarantined": False,
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
    "trusted_production_time_bound": False,
    "wire_attempted": False,
}

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

TOP_LEVEL_KEYS = (
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

SECTION_HASH_KEYS = (
    "boundary_sha256",
    "decision_provenance_sha256",
    "implementation_authority_sha256",
    "nonclaims_sha256",
    "owner_implementation_actor_sha256",
    "resource_binding_sha256",
    "rollback_sha256",
    "state_machine_sha256",
)


class ImplementationAuthorityDecisionReviewError(ValueError):
    """Fail-closed decision-review error with a stable reason code."""


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ImplementationAuthorityDecisionReviewError(f"{code}: {message}")


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
    """Return compact sorted UTF-8 JSON bytes after strict type validation."""

    _validate_json_value(value)
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def domain_sha256(domain: str, value: Any) -> str:
    require(
        type(domain) is str and domain in DOMAIN_PREFIXES.values(),
        "E_HASH_DOMAIN",
        "unknown domain",
    )
    return hashlib.sha256(domain.encode("ascii") + b"\x00" + canonical_bytes(value)).hexdigest()


def is_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _expected_section_hashes(record: Mapping[str, Any]) -> dict[str, str]:
    return {
        "boundary_sha256": domain_sha256(DOMAIN_PREFIXES["boundary"], record["boundary"]),
        "decision_provenance_sha256": domain_sha256(
            DOMAIN_PREFIXES["decision_provenance"], record["decision_provenance"]
        ),
        "implementation_authority_sha256": domain_sha256(
            DOMAIN_PREFIXES["implementation_authority"], record["implementation_authority"]
        ),
        "nonclaims_sha256": domain_sha256(
            DOMAIN_PREFIXES["nonclaims"], record["nonclaims"]
        ),
        "owner_implementation_actor_sha256": domain_sha256(
            DOMAIN_PREFIXES["owner_implementation_actor"],
            record["owner_implementation_actor"],
        ),
        "resource_binding_sha256": domain_sha256(
            DOMAIN_PREFIXES["resource_binding"], record["resource_binding"]
        ),
        "rollback_sha256": domain_sha256(
            DOMAIN_PREFIXES["rollback"], record["rollback"]
        ),
        "state_machine_sha256": domain_sha256(
            DOMAIN_PREFIXES["state_machine"], record["state_machine"]
        ),
    }


def _validate_fixed_section(actual: Any, expected: Any, code: str) -> None:
    require(exact_equal(actual, expected), code, "closed-world section drift")


def _validate_cross_section_invariants(record: Mapping[str, Any]) -> None:
    provenance = record["decision_provenance"]
    owner = record["owner_implementation_actor"]
    authority = record["implementation_authority"]
    resources = record["resource_binding"]
    machine = record["state_machine"]
    boundary = record["boundary"]
    nonclaims = record["nonclaims"]

    require(
        authority["current_state"] == machine["current_state"] == CURRENT_STATE,
        "E_STATE_BINDING",
        "authority and state-machine state differ",
    )
    require(
        authority["mode"] == MODE and authority["exact_next_unit_authorized"] is True,
        "E_SCOPE_BINDING",
        "implementation scope drift",
    )
    require(
        resources["effective_external_paid_spend_cap"] == 0
        and resources["owner_supplied_numeric_budget_cap"] is False
        and provenance["owner_supplied_numeric_budget_cap"] is False,
        "E_BUDGET_BINDING",
        "zero fail-closed budget provenance drift",
    )
    require(
        resources["provider_endpoints"] == []
        and resources["credential_handles"] == []
        and resources["credential_paths"] == []
        and resources["component_runtime_network"] is False,
        "E_EXTERNAL_RESOURCE_BOUNDARY",
        "endpoint, credential, or network authority present",
    )
    require(
        owner["semantic_actor_binding_recorded"] is True
        and owner["cryptographic_identity_verified"] is False
        and owner["signature_observed"] is False
        and owner["runtime_owner_identity_bound"] is False
        and owner["runtime_owner_decision_recorded"] is False,
        "E_OWNER_SEMANTIC_BOUNDARY",
        "semantic actor was promoted to runtime owner",
    )
    require(
        authority["implementation_authority_recorded"] is True
        and boundary["implementation_authority_recorded"] is True
        and boundary["production_environment_implementation_authorized"] is False,
        "E_IMPLEMENTATION_BOUNDARY",
        "implementation authority scope mismatch",
    )
    require(
        boundary["production_ingestion_controls_implemented"] == 0
        and boundary["production_ingestion_controls_runtime_exercised"] == 0
        and boundary["real_evidence_items_present"] == 0
        and boundary["runtime_prerequisites_satisfied"] == 0
        and boundary["downstream_gates_authorized"] == 0,
        "E_ZERO_COUNTS",
        "runtime or production count advanced",
    )
    require(
        boundary["runtime_owner_decision_recorded"] is False
        and boundary["runtime_admission_granted"] is False
        and boundary["runtime_authority"] is False
        and boundary["provider_authority"] is False,
        "E_RUNTIME_AUTHORITY",
        "runtime or provider authority present",
    )
    require(
        boundary["runtime_side_effects_unlocked"] == "NONE"
        and boundary["implementation_side_effects_unlocked"]
        == IMPLEMENTATION_SIDE_EFFECTS,
        "E_SIDE_EFFECT_SCOPE",
        "implementation and runtime side effects conflated",
    )
    require(
        len(nonclaims) == 48 and all(value is False for value in nonclaims.values()),
        "E_NONCLAIMS",
        "nonclaim closure drift",
    )
    require(
        machine["runtime_authority_state_representable"] is False
        and machine["positive_provider_authority_state_representable"] is False
        and machine["global_single_use_proved"] is False,
        "E_STATE_VOCABULARY",
        "positive external authority became representable",
    )


def review_decision(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the exact decision record and return a scalar receipt."""

    _validate_json_value(record)
    exact_keys(record, TOP_LEVEL_KEYS, "E_RECORD_KEYS")
    require(record["schema"] == RECORD_SCHEMA, "E_RECORD_SCHEMA", "schema")
    require(record["schema_version"] == 1, "E_RECORD_VERSION", "version")
    require(record["date"] == DATE, "E_RECORD_DATE", "date")
    require(record["status"] == STATUS, "E_RECORD_STATUS", "status")
    require(record["decision"] == DECISION, "E_RECORD_DECISION", "decision")
    require(record["next_unit"] == NEXT_UNIT, "E_RECORD_NEXT", "next unit")

    _validate_fixed_section(record["predecessor"], PREDECESSOR, "E_PREDECESSOR")
    _validate_fixed_section(
        record["decision_provenance"], DECISION_PROVENANCE, "E_PROVENANCE"
    )
    _validate_fixed_section(
        record["owner_implementation_actor"],
        OWNER_IMPLEMENTATION_ACTOR,
        "E_OWNER_ACTOR",
    )
    _validate_fixed_section(
        record["implementation_authority"], IMPLEMENTATION_AUTHORITY, "E_AUTHORITY"
    )
    _validate_fixed_section(record["resource_binding"], RESOURCE_BINDING, "E_RESOURCE")
    _validate_fixed_section(record["state_machine"], STATE_MACHINE, "E_STATE_MACHINE")
    _validate_fixed_section(record["rollback"], ROLLBACK, "E_ROLLBACK")
    _validate_fixed_section(record["boundary"], BOUNDARY, "E_BOUNDARY")
    _validate_fixed_section(record["nonclaims"], NONCLAIMS, "E_NONCLAIMS")

    exact_keys(record["section_sha256"], SECTION_HASH_KEYS, "E_SECTION_HASH_KEYS")
    expected_hashes = _expected_section_hashes(record)
    require(
        exact_equal(record["section_sha256"], expected_hashes),
        "E_SECTION_HASH",
        "section hash drift",
    )
    require(
        all(is_sha256(value) for value in record["section_sha256"].values()),
        "E_SECTION_HASH_FORMAT",
        "invalid hash format",
    )
    _validate_cross_section_invariants(record)

    decision_record_sha256 = domain_sha256(
        DOMAIN_PREFIXES["decision_record"], record
    )
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
        "allowed_operation_count": len(ALLOWED_OPERATIONS),
        "forbidden_operation_count": len(FORBIDDEN_OPERATIONS),
        "provider_endpoint_count": 0,
        "credential_handle_count": 0,
        "credential_path_count": 0,
        "component_runtime_network": False,
        "state_count": len(STATES),
        "transition_count": len(TRANSITIONS),
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
        "nonclaim_field_count": len(NONCLAIMS),
        "all_nonclaims_explicit": True,
        "owner_implementation_actor_sha256": expected_hashes[
            "owner_implementation_actor_sha256"
        ],
        "implementation_authority_sha256": expected_hashes[
            "implementation_authority_sha256"
        ],
        "resource_binding_sha256": expected_hashes["resource_binding_sha256"],
        "state_machine_sha256": expected_hashes["state_machine_sha256"],
        "rollback_sha256": expected_hashes["rollback_sha256"],
        "boundary_sha256": expected_hashes["boundary_sha256"],
        "nonclaims_sha256": expected_hashes["nonclaims_sha256"],
        "decision_record_sha256": decision_record_sha256,
        "predecessor_receipt_content_sha256": PREDECESSOR["receipt_content_sha256"],
    }
    receipt["content_sha256"] = domain_sha256(DOMAIN_PREFIXES["receipt"], receipt)
    return receipt


TSV_FIELDS = (
    "schema",
    "status",
    "decision",
    "date",
    "mode",
    "next_unit",
    "current_state",
    "implementation_authority_recorded",
    "implementation_scope_decision_recorded",
    "implementation_resource_binding_recorded",
    "production_shaped_component_code_authorized",
    "production_environment_implementation_authorized",
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
    "state_count",
    "transition_count",
    "global_single_use_proved",
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
    "owner_implementation_actor_sha256",
    "implementation_authority_sha256",
    "resource_binding_sha256",
    "state_machine_sha256",
    "rollback_sha256",
    "boundary_sha256",
    "nonclaims_sha256",
    "decision_record_sha256",
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
        if type(value) is bool:
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        require("\t" not in rendered and "\n" not in rendered, "E_TSV_TEXT", field)
        lines.append(f"{field}\t{rendered}")
    return "\n".join(lines) + "\n"
