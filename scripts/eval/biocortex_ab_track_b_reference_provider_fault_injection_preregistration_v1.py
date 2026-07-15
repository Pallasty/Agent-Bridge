#!/usr/bin/env python3
"""Pure builder for the Track B reference-provider fault-injection v1 preregistration.

The module validates a closed two-track experiment plan and a zero-execution
observation, then returns a deterministic non-authorizing receipt.  It performs
no filesystem, process, network, provider, credential, generator, or sink I/O.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


BASELINE_COMMIT = "3ca858bd6f0097dd0f7f928e7acb4aef030a47a2"
CONTRACT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "experiment_preregistration.v1"
)
OBSERVATION_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "pre_execution_observation.v0"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "preregistration_receipt.v1"
)
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_EXPERIMENT_V1_PREREGISTERED_"
    "NO_PROVIDER_INVOCATION_NO_PERMIT"
)
DECISION = "PREREGISTRATION_PASS_EXECUTION_BLOCKED_NO_AUTHORITY_OR_RUN_EVIDENCE"
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_HARNESS_V1_"
    "OFFLINE_DOUBLE_IMPLEMENTATION"
)
MANAGED_TRACK = "MANAGED_SPANNER_CLOUD_KMS"
SELF_HOSTED_TRACK = "SELF_HOSTED_ETCD_OPENBAO"

MANAGED_CASE_IDS = tuple(f"M{index:02d}" for index in range(16))
SELF_HOSTED_CASE_IDS = tuple(f"S{index:02d}" for index in range(18))
MANAGED_INVARIANT_IDS = tuple(f"M{index:02d}" for index in range(1, 13))
SELF_HOSTED_INVARIANT_IDS = tuple(f"S{index:02d}" for index in range(1, 15))
GLOBAL_INVARIANT_IDS = tuple(f"X{index:02d}" for index in range(1, 9))
SOURCE_IDS = (
    "ETC01",
    "ETC02",
    "ETC03",
    "ETC04",
    "GKM01",
    "GKM02",
    "GKM03",
    "GKM04",
    "GSP01",
    "GSP02",
    "GSP03",
    "OBA01",
    "OBA02",
    "OBA03",
    "OBA04",
    "OBA05",
)
ALLOWED_CLASSIFICATIONS = {
    "AMBIGUOUS_QUARANTINED",
    "CONFORMING_OBSERVED",
    "FAIL_CLOSED_REJECTED",
    "INCIDENT_QUARANTINED",
    "RECOVERED_BY_DATABASE_ONLY_RETRY",
    "RECOVERED_BY_STRONG_LOOKUP",
    "REBASED_NEW_INCARNATION",
    "RUN_ABORTED_RETAINED",
}
ALLOWED_EVIDENCE_LOCI = {
    "CLIENT_CONFORMANCE_DOUBLE",
    "MANAGED_SERVICE_WITH_CLIENT_FAULT_PROXY",
    "SELF_HOSTED_ADVERSARIAL_LAB",
}
OFFICIAL_HOSTS = {
    "docs.cloud.google.com",
    "etcd.io",
    "openbao.org",
}

EXPECTED_CASE_VARIANTS = {
    "M04": [
        "DROP_COMMIT_RESPONSE_AFTER_SERVER_COMMIT",
        "DROP_COMMIT_RESPONSE_WHILE_COMMIT_OUTCOME_IS_UNRESOLVED",
    ],
    "M07": [
        "COMPUTE_DATA_CRC32C_OVER_BASE64_TEXT",
        "RETURN_VERIFIED_DATA_CRC32C_FALSE",
    ],
    "M08": [
        "OMIT_CRYPTOKEYVERSION_SEGMENT",
        "SET_CRYPTOKEYVERSION_SEGMENT_TO_ZERO",
        "USE_PARENT_CRYPTOKEY_RESOURCE",
        "USE_NONCANONICAL_LEADING_ZERO_VERSION",
        "RETURN_DIFFERENT_CRYPTOKEYVERSION_NAME",
    ],
    "S09": [
        "RESTORE_OLDER_SNAPSHOT_WITHOUT_BUMP",
        "RETURN_STALE_REPLAYED_OR_FORKED_WITNESS_RECORD",
        "MAKE_INDEPENDENT_WITNESS_UNAVAILABLE_OR_CAS_CONFLICT",
    ],
}
EXPECTED_CRITICAL_CASE_FIELDS = {
    "M00": {
        "candidate_requirement": "SERIALIZABLE_AUTHORITY_TRANSACTION_COMMITS_A_DURABLE_OUTBOX_THEN_ONE_DURABLY_PREPARED_EXACT_VERSION_KMS_ATTEMPT_COMMITS_ONE_FULLY_VALIDATED_SIGNATURE_RECEIPT",
        "invariant_ids": [
            "M01", "M02", "M05", "M06", "M07", "M08", "M09", "M10",
            "M11", "M12", "X01", "X07",
        ],
    },
    "M01": {
        "allowed_classifications": ["RECOVERED_BY_DATABASE_ONLY_RETRY"],
    },
    "M04": {
        "candidate_requirement": "AFTER_UNKNOWN_COMMIT_EXACT_RECORD_RESOLVES_COMMIT_WHILE_BARE_ABSENCE_REQUIRES_SAME_OPERATION_KEY_ABSENT_TO_TERMINAL_FENCE_TRANSACTION_AND_CONFIRMING_STRONG_READ_BEFORE_RESOLUTION",
        "forbidden_claims": [
            "BARE_ABSENT_STRONG_READ_PROVES_UNKNOWN_COMMIT_CANNOT_LATER_APPEAR",
            "TIMEOUT_MEANS_NOT_COMMITTED",
        ],
        "injection_cut": "CYCLE_RESPONSE_LOSS_AFTER_COMMIT_AND_BEFORE_COMMIT_RESOLUTION_BY_REPETITION_MODULO_TWO",
    },
    "M07": {
        "candidate_requirement": "DATA_CRC32C_IS_COMPUTED_OVER_THE_DECODED_137_RAW_BYTES_AND_VERIFIED_DATA_CRC32C_IS_TRUE",
        "injection_cut": "CYCLE_CLOSED_REQUEST_INTEGRITY_VARIANTS_BY_REPETITION_MODULO_TWO",
    },
    "M08": {
        "candidate_requirement": "REQUEST_USES_A_NONZERO_EXACT_CRYPTOKEYVERSION_RESOURCE_AND_RESPONSE_NAME_IS_BYTE_EQUAL_TO_THAT_REQUEST",
        "injection_cut": "CYCLE_CLOSED_VERSION_RESOURCE_VARIANTS_BY_REPETITION_MODULO_FIVE",
    },
    "M10": {
        "candidate_requirement": "PROTECTION_PROFILE_ACCEPTS_ONLY_THE_EXACT_PINNED_PROTECTION_LEVEL_ENUM",
        "injection_cut": "RETURN_DIFFERENT_PROTECTION_LEVEL_FROM_PINNED_EXPECTATION",
    },
    "M12": {
        "candidate_requirement": "KMS_RESPONSE_LOSS_DURABLY_QUARANTINES_THE_PREPARED_ATTEMPT_AND_RESTART_NEVER_REISSUES_SIGNING_OR_EMITS_OUTPUT",
        "forbidden_claims": [
            "RESTART_MAY_REISSUE_AFTER_PREPARED_OR_AMBIGUOUS_STATE",
            "TIMEOUT_MEANS_NO_SIGNATURE_WAS_CREATED",
        ],
        "injection_cut": "DROP_KMS_RESPONSE_AFTER_SERVICE_PROCESSING_THEN_RESTART_WORKER",
    },
    "M13": {
        "allowed_classifications": [
            "AMBIGUOUS_QUARANTINED",
            "RECOVERED_BY_STRONG_LOOKUP",
        ],
        "candidate_requirement": "AFTER_VALID_SIGNATURE_AND_RECEIPT_PERSIST_FAILURE_STRONG_READ_RECOVERS_AN_EXACT_RECEIPT_OR_DURABLY_QUARANTINES_THE_PREPARED_ATTEMPT_BEFORE_RESTART",
        "forbidden_claims": [
            "IN_MEMORY_SIGNATURE_IS_DURABLE_EVIDENCE",
            "PERSIST_FAILURE_REOPENS_SIGNING_AFTER_RESTART",
        ],
        "injection_cut": "FAIL_RECEIPT_PERSIST_AFTER_SIGNATURE_VALIDATION_THEN_RESTART_WORKER",
    },
    "M14": {
        "candidate_requirement": "TWO_WORKERS_COMPETING_FOR_ONE_OPERATION_CREATE_ONE_DURABLE_OUTBOX_ONE_PREPARED_ATTEMPT_OWNER_ONE_APPLICATION_KMS_CALL_AND_ONE_ACCEPTED_RECEIPT_WITHOUT_CLAIMING_ONE_PROVIDER_PROCESSING_EVENT",
        "forbidden_claims": [
            "LOSING_WORKER_MAY_SIGN_AFTER_ATTEMPT_CAS_FAILURE",
            "ONE_DURABLE_RECEIPT_PROVES_ONE_KMS_RPC",
        ],
    },
    "M15": {
        "candidate_requirement": "DURABLE_OUTBOX_READY_RECOVERY_AFTER_PREATTEMPT_CRASH_PREPARES_ONE_SIGN_ATTEMPT_AND_NEVER_REAUTHORIZES_OR_RECONSUMES_THE_CHALLENGE",
        "injection_cut": "CRASH_AFTER_SPANNER_OUTBOX_READY_COMMIT_BEFORE_ATTEMPT_CAS_AND_KMS_CALL",
    },
    "S00": {
        "candidate_requirement": "NON_NESTED_ETCD_CAS_WITH_LINEARIZABLE_READS_A_DURABLE_PREPARED_SIGN_ATTEMPT_AND_EXACT_VERSION_TRANSIT_ED25519_RECEIPT_COMMIT",
        "invariant_ids": [
            "S01", "S02", "S03", "S04", "S10", "S11", "S12", "S14",
            "X01", "X05",
        ],
    },
    "S04": {
        "candidate_requirement": "AFTER_UNKNOWN_LEADER_LOSS_EXACT_RECORD_RESOLVES_COMMIT_WHILE_BARE_ABSENCE_REQUIRES_SAME_OPERATION_KEY_ABSENT_TO_TERMINAL_FENCE_CAS_AND_CONFIRMING_LINEARIZABLE_READ_BEFORE_RESOLUTION",
        "forbidden_claims": [
            "BARE_ABSENT_LINEARIZABLE_READ_PROVES_UNKNOWN_WRITE_CANNOT_LATER_COMMIT",
            "LEADER_ELECTION_PROVES_THE_WRITE_ABORTED",
        ],
        "injection_cut": "REMOVE_LEADER_AFTER_REQUEST_ADMISSION_BEFORE_OBSERVED_COMMIT",
        "invariant_ids": ["S03", "S05", "X03"],
    },
    "S09": {
        "candidate_requirement": "RESTORE_OR_WITNESS_ROLLBACK_UNAVAILABILITY_FORK_OR_CONFLICT_IS_INCIDENT_QUARANTINED_AND_CANNOT_REJOIN_THE_INCUMBENT_EPOCH",
        "injection_cut": "CYCLE_CLOSED_RESTORE_WITNESS_FAILURE_VARIANTS_BY_REPETITION_MODULO_THREE",
    },
    "S10": {
        "candidate_requirement": "BUMPED_RESTORE_WITH_REUSED_INCUMBENT_IDENTITY_OR_MISMATCHED_WITNESS_BINDING_IS_INCIDENT_QUARANTINED",
    },
    "S11": {
        "candidate_requirement": "VERIFIED_SNAPSHOT_HASH_BUMP_AND_MARK_COMPACTED_RESTORE_REBASES_ONLY_AFTER_AUTHORIZED_WITNESS_CAS_TO_A_NEW_CLUSTER_AND_INCARNATION_PLUS_WATCH_INVALIDATION_AND_FULL_LINEARIZABLE_RECONCILIATION",
        "forbidden_claims": [
            "NEW_RANDOM_INCARNATION_OR_REVISION_BUMP_IS_SELF_AUTHORIZING",
            "REBASE_CERTIFIES_OLD_OPERATION_CONTINUITY",
        ],
        "invariant_ids": ["S07", "S08", "S06", "S09", "X03", "X04", "X05", "X06"],
    },
    "S12": {
        "candidate_requirement": "DIRECT_TARGET_SEAL_STATUS_HA_ROLE_NODE_CLUSTER_REQUEST_AND_FORWARD_EVIDENCE_DISTINGUISH_TARGET_SEAL_FROM_EXECUTING_NODE_WHILE_ANY_SUCCESSOR_RESPONSE_REQUIRES_FULL_VALIDATION",
    },
    "S13": {
        "candidate_requirement": "LOSS_OF_TRANSIT_RESPONSE_DURABLY_QUARANTINES_THE_PREPARED_ATTEMPT_AND_RESTART_NEVER_REISSUES_SIGNING_OR_EMITS_OUTPUT",
        "forbidden_claims": [
            "RESTART_MAY_REISSUE_AFTER_PREPARED_OR_AMBIGUOUS_STATE",
            "TIMEOUT_MEANS_NO_SIGNING_OCCURRED",
        ],
        "injection_cut": "DROP_TRANSIT_RESPONSE_AFTER_SIGN_PROCESSING_THEN_RESTART_WORKER",
    },
    "S14": {
        "allowed_classifications": [
            "AMBIGUOUS_QUARANTINED",
            "RECOVERED_BY_STRONG_LOOKUP",
        ],
        "candidate_requirement": "AFTER_VALID_SIGNATURE_AND_ETCD_RECEIPT_PERSIST_FAILURE_STRONG_READ_RECOVERS_AN_EXACT_RECEIPT_OR_DURABLY_QUARANTINES_THE_PREPARED_ATTEMPT_BEFORE_RESTART",
        "forbidden_claims": [
            "IN_MEMORY_SIGNATURE_IS_DURABLE_EVIDENCE",
            "PERSIST_FAILURE_REOPENS_SIGNING_AFTER_RESTART",
        ],
        "injection_cut": "FAIL_ETCD_PERSIST_AFTER_SIGNATURE_VALIDATION_THEN_RESTART_WORKER",
    },
    "S17": {
        "candidate_requirement": "SINGLE_NONBATCH_REQUEST_OMITS_CONTEXT_HAS_EXACT_137_BYTE_INPUT_AND_SIGNATURE_VERSION_PREFIX_PINNED_PUBLIC_KEY_OFFLINE_VERIFICATION_ALL_MATCH",
    },
}
EXPECTED_CRITICAL_INVARIANTS = {
    "M04": (
        "POST_UNKNOWN_STRONG_LOOKUP_SAME_OPERATION_KEY_ABSENT_TO_TERMINAL_FENCE_TRANSACTION_AND_CONFIRMING_STRONG_READ",
        "UNKNOWN_SPANNER_COMMIT_RESOLVES_ONLY_TO_AN_EXACT_RECORD_OR_A_DURABLY_FENCED_ABSENCE_AND_IS_NEVER_BLINDLY_REISSUED",
    ),
    "M05": (
        "SAME_TRANSACTION_AUTHORITY_CHALLENGE_LOGICAL_SLOT_MESSAGE_KEY_BINDING_AND_DURABLE_OUTBOX_ROW",
        "AUTHORITY_STATE_CHALLENGE_CONSUMPTION_LOGICAL_SINK_RESERVATION_AND_DURABLE_SIGNING_OUTBOX_COMMIT_TOGETHER",
    ),
    "M06": (
        "PREDECESSOR_MESSAGE_DERIVATION_POINTER_KAT_SHA256_DECODED_REQUEST_BYTES_AND_DIGEST_UNION_ABSENCE",
        "KMS_SIGNS_EXACTLY_137_RAW_DATA_BYTES_NOT_A_DIGEST_SLOT",
    ),
    "M07": (
        "INDEPENDENT_CASTAGNOLI_CRC32C_OVER_DECODED_RAW_137_BYTES_BASE64_TEXT_NEGATIVE_KAT_PROVIDER_ERROR_AND_TRUE_VERIFIED_DATA_CRC32C",
        "KMS_REQUEST_DATA_INTEGRITY_IS_VERIFIED",
    ),
    "M08": (
        "FULL_CRYPTOKEYVERSION_GRAMMAR_NONZERO_CANONICAL_DECIMAL_SEGMENT_NO_PARENT_ALIAS_FALLBACK_AND_RESPONSE_BYTE_EQUALITY",
        "KMS_USES_AN_EXPLICIT_NONZERO_EXACT_KEY_VERSION",
    ),
    "M10": (
        "PINNED_AND_RESPONSE_EXACT_PROTECTION_LEVEL_ENUM_EQUALITY_INCLUDING_HSM_VERSUS_HSM_SINGLE_TENANT_DISTINCTION",
        "HSM_CLAIM_REQUIRES_MATCHING_HSM_PROTECTION_LEVEL",
    ),
    "M12": (
        "DURABLE_PREATTEMPT_CAS_EXACT_REQUEST_BINDINGS_DISABLED_HIDDEN_RETRIES_STRONG_POSTFAILURE_READ_TERMINAL_QUARANTINE_AND_RESTART_WIRE_COUNT",
        "EVERY_KMS_WIRE_ATTEMPT_REQUIRES_A_DURABLE_PREPARED_MARKER_AND_ANY_UNRESOLVED_OR_QUARANTINED_ATTEMPT_NEVER_REISSUES_SIGNING_OR_OUTPUTS_AFTER_RESTART",
    ),
    "S03": (
        "NONLEASED_OPERATION_KEY_ABSENT_OR_EXACT_MOD_VALUE_COMPARE_SINGLE_SUCCESS_MUTATION_AND_FAILURE_BRANCH_LINEARIZABLE_READ",
        "AUTHORITY_OPERATION_OUTBOX_ATTEMPT_AND_RECEIPT_TRANSITIONS_USE_NON_NESTED_NONLEASED_EXACT_KEY_CAS_WITH_STRONG_CONFLICT_READBACK",
    ),
    "S05": (
        "POST_UNKNOWN_LINEARIZABLE_LOOKUP_SAME_OPERATION_KEY_ABSENT_TO_TERMINAL_FENCE_CAS_AND_CONFIRMING_LINEARIZABLE_READ",
        "UNKNOWN_ETCD_OPERATION_RESOLVES_ONLY_TO_AN_EXACT_RECORD_OR_A_DURABLY_FENCED_ABSENCE_AND_IS_NEVER_BLINDLY_REISSUED",
    ),
    "S06": (
        "OUT_OF_RESTORE_DOMAIN_LINEARIZABLE_WITNESS_RECORD_EXACT_PREVIOUS_HASH_MONOTONIC_CAS_AND_FULL_RESTORE_BINDING",
        "MISSING_UNAVAILABLE_STALE_REPLAYED_FORKED_OR_CONFLICTING_RESTORE_WITNESS_STATE_FAILS_CLOSED",
    ),
    "S07": (
        "VERIFIED_SNAPSHOT_SHA256_RESTORE_STATUS_NEW_CLUSTER_AND_INCARNATION_IDENTITIES_AND_NO_SKIP_HASH_CHECK",
        "ONLY_AN_INTEGRITY_VERIFIED_SNAPSHOT_CAN_START_A_NEW_CLUSTER_AND_INCARNATION",
    ),
    "S08": (
        "BUMP_REVISION_MARK_COMPACTED_NEW_FLOOR_WATCH_CANCELLATION_AND_FULL_LINEARIZABLE_CACHE_REBUILD_RECEIPT",
        "REVISION_BUMP_AND_MARK_COMPACTED_REQUIRE_WATCH_INVALIDATION_AND_FULL_LINEARIZABLE_RECONCILIATION_AND_ARE_NOT_CONTINUITY_PROOF",
    ),
    "S11": (
        "NONDERIVED_NONBATCH_REQUEST_BATCH_INPUT_AND_CONTEXT_ABSENT_SINGLE_INPUT_EXACT_137_BYTES_PREHASHED_FALSE_AND_EXACT_REQUEST_DIGEST_PER_ATTEMPT",
        "TRANSIT_ED25519_USES_ONE_NONBATCH_CONTEXT_FREE_RAW_FRAME_REQUEST_BOUND_TO_EACH_DURABLE_ATTEMPT",
    ),
    "S13": (
        "DIRECT_TARGET_SYS_SEAL_STATUS_JSON_HA_ROLE_CLUSTER_NODE_REQUEST_ID_REDIRECT_FORWARD_AUDIT_WIRE_ATTEMPTS_AND_NO_SIGNATURE_RECEIPT",
        "EXECUTING_NODE_IDENTITY_IS_EVIDENCED_SEPARATELY_FROM_CLIENT_ROUTE_AND_TARGET_NODE_SEAL_NEVER_IMPLIES_SERVICE_WIDE_UNAVAILABILITY",
    ),
    "S14": (
        "DURABLE_PREATTEMPT_CAS_EXACT_REQUEST_BINDINGS_DISABLED_HIDDEN_RETRIES_STRONG_POSTFAILURE_READ_TERMINAL_QUARANTINE_RESTART_AND_WIRE_COUNT",
        "EVERY_TRANSIT_WIRE_ATTEMPT_REQUIRES_A_DURABLE_PREPARED_MARKER_AND_ANY_UNRESOLVED_OR_QUARANTINED_ATTEMPT_NEVER_REISSUES_SIGNING_OR_OUTPUTS_AFTER_RESTART",
    ),
}
EXPECTED_SIGNING_STATE_MACHINES = {
    MANAGED_TRACK: {
        "ambiguous_transition": "SIGN_ATTEMPT_PREPARED_TO_AMBIGUOUS_QUARANTINED_BY_SERIALIZABLE_CAS",
        "attempt_consumption_rule": "EACH_PREPARED_ATTEMPT_AUTHORIZES_AT_MOST_ONE_APPLICATION_KMS_CALL_AND_IS_NEVER_REUSED",
        "claim_ceiling": "ONE_ACCEPTED_DURABLE_RECEIPT_DOES_NOT_PROVE_ONE_KMS_RPC_OR_SIGNATURE_CREATION",
        "hidden_provider_retries": "FORBIDDEN",
        "persist_failure_resolution": "STRONG_EXACT_READ_THEN_COMMITTED_RECEIPT_RECOVERS_PREPARED_CAS_TO_AMBIGUOUS_OTHER_CONFLICT_INCIDENT",
        "prepare_transition": "SIGN_PENDING_TO_SIGN_ATTEMPT_PREPARED_BY_SERIALIZABLE_CAS_BEFORE_EVERY_WIRE_ATTEMPT",
        "prepared_binding": [
            "OPERATION_ID",
            "CANONICAL_REQUEST_DIGEST",
            "EXACT_KEY_VERSION",
            "PUBLIC_KEY_PIN",
            "MESSAGE_SHA256",
            "ATTEMPT_SEQUENCE",
        ],
        "provider_call_precondition": "EXACT_PREPARED_RECORD_DURABLY_CONFIRMED",
        "restart_rule": "PREPARED_AMBIGUOUS_OR_UNRESOLVED_STATE_NEVER_REISSUES_SIGNING_AND_NEVER_OUTPUTS",
        "store_unavailable_resolution": "BLOCKED_UNRESOLVED_NO_PROVIDER_RETRY_NO_OUTPUT",
        "valid_response_transition": "SIGN_ATTEMPT_PREPARED_TO_SIGNATURE_RECEIPT_COMMITTED_BY_SERIALIZABLE_CAS_AFTER_FULL_VALIDATION",
    },
    SELF_HOSTED_TRACK: {
        "ambiguous_transition": "SIGN_ATTEMPT_PREPARED_TO_AMBIGUOUS_QUARANTINED_BY_LINEARIZABLE_ETCD_CAS",
        "attempt_consumption_rule": "EACH_PREPARED_ATTEMPT_AUTHORIZES_AT_MOST_ONE_APPLICATION_TRANSIT_CALL_AND_IS_NEVER_REUSED",
        "claim_ceiling": "ONE_ACCEPTED_DURABLE_RECEIPT_DOES_NOT_PROVE_ONE_TRANSIT_RPC_OR_SIGNATURE_CREATION",
        "hidden_provider_retries": "FORBIDDEN",
        "persist_failure_resolution": "LINEARIZABLE_EXACT_READ_THEN_COMMITTED_RECEIPT_RECOVERS_PREPARED_CAS_TO_AMBIGUOUS_OTHER_CONFLICT_INCIDENT",
        "prepare_transition": "SIGN_PENDING_TO_SIGN_ATTEMPT_PREPARED_BY_LINEARIZABLE_ETCD_CAS_BEFORE_EVERY_WIRE_ATTEMPT",
        "prepared_binding": [
            "OPERATION_ID",
            "CANONICAL_REQUEST_DIGEST",
            "EXACT_KEY_VERSION",
            "PUBLIC_KEY_PIN",
            "MESSAGE_SHA256",
            "ATTEMPT_SEQUENCE",
        ],
        "provider_call_precondition": "EXACT_PREPARED_RECORD_DURABLY_CONFIRMED",
        "restart_rule": "PREPARED_AMBIGUOUS_OR_UNRESOLVED_STATE_NEVER_REISSUES_SIGNING_AND_NEVER_OUTPUTS",
        "store_unavailable_resolution": "BLOCKED_UNRESOLVED_NO_PROVIDER_RETRY_NO_OUTPUT",
        "valid_response_transition": "SIGN_ATTEMPT_PREPARED_TO_SIGNATURE_RECEIPT_COMMITTED_BY_LINEARIZABLE_ETCD_CAS_AFTER_FULL_VALIDATION",
    },
}
EXPECTED_RESTORE_WITNESS_PROTOCOL = {
    "advance_rule": "LINEARIZABLE_COMPARE_EXACT_PREVIOUS_RECORD_SHA256_AND_GENERATION_THEN_PUT_NEW_RECORD",
    "authority": "SEPARATELY_AUTHORIZED_ABSTRACT_LINEARIZABLE_CAS_SERVICE_OUTSIDE_ETCD_SNAPSHOT_AND_RESTORE_ACTOR_DOMAIN",
    "binding_fields": [
        "DOMAIN",
        "AUTHORITY_ID",
        "PRIOR_CLUSTER_ID",
        "PRIOR_INCARNATION_ID",
        "PRIOR_REVISION_FLOOR",
        "SNAPSHOT_SHA256",
        "SNAPSHOT_REVISION",
        "NEW_CLUSTER_ID",
        "NEW_INCARNATION_ID",
        "NEW_REVISION_FLOOR",
        "BUMP_REVISION",
        "MARK_COMPACTED",
        "REBASE_AUTHORIZATION_SHA256",
        "PREVIOUS_RECORD_SHA256",
        "GENERATION",
    ],
    "implementation_status": "UNBOUND_NO_LAB_EXECUTION_AUTHORITY",
    "invalid_state_rule": "MISSING_UNAVAILABLE_STALE_REPLAYED_FORKED_MISMATCHED_OR_CAS_CONFLICTING_WITNESS_STATE_IS_INCIDENT_QUARANTINED",
    "key_rule": "SHA256_DOMAIN_AUTHORITY_ID_AND_LOGICAL_CLUSTER_LINEAGE_ID",
    "read_rule": "CURRENT_LINEARIZABLE_READ_ONLY",
    "rebase_rule": "NEW_CLUSTER_AND_NEW_INCARNATION_ONLY_AFTER_EXACT_WITNESS_CAS_AND_FULL_LINEARIZABLE_RECONCILIATION",
    "watch_rule": "ALL_PRE_RESTORE_WATCH_STREAMS_ARE_INVALIDATED_AND_NEVER_AUTHORIZE_REBASE",
}
EXPECTED_MESSAGE_FRAME_REFERENCE = {
    "expected_message_bytes": 137,
    "json_pointer": "/authority_grain/signature_receipt_contract/message_derivation",
    "message_sha256": "f5dcb16eec00a302bf56c9cc681b5c09d598589c4c3e9ab2413b68c21f16982d",
    "predecessor_contract_path": "docs/design/fixtures/biocortex-ab-track-b-external-atomic-live-output-execution-boundary-contract-v1.json",
    "predecessor_contract_sha256": "9688c4df6ce4a8cf84539a400b488f2c108da606ab2a9eb22e459376bd525046",
}
EXPECTED_PREFLIGHT_REQUIREMENTS = {
    MANAGED_TRACK: [
        "PIN_CLIENT_LIBRARY_VERSION_BUILD_HASH_RETRY_AND_TIMEOUT_CONFIGURATION",
        "PIN_SPANNER_DATABASE_DIALECT_INSTANCE_DATABASE_AND_EXPLICIT_SERIALIZABLE_PROFILE",
        "PIN_EXACT_CRYPTOKEYVERSION_RESOURCE_PUBLIC_KEY_ALGORITHM_ENABLED_STATE_AND_EXPECTED_PROTECTION_LEVEL",
        "PIN_FAULT_PROXY_VERSION_CONFIGURATION_DISABLE_HIDDEN_PROVIDER_RETRIES_AND_RECORD_EVERY_WIRE_ATTEMPT",
        "CAPTURE_CLOCK_RANDOMNESS_AND_ALL_NONDETERMINISTIC_INPUTS_ONCE_BEFORE_RETRYABLE_CLOSURE",
        "BIND_OWNER_CUSTODIAN_RESOURCE_CREDENTIAL_AND_COST_AUTHORITY_BEFORE_ANY_PROVIDER_CALL",
    ],
    SELF_HOSTED_TRACK: [
        "PIN_ETCD_AND_OPENBAO_BINARY_OR_IMAGE_DIGESTS_CLIENT_VERSIONS_AND_CONFIGURATION_HASHES",
        "PIN_ETCD_CLUSTER_MEMBER_IDENTITIES_SNAPSHOT_HASH_REVISION_RESTORE_PARAMETERS_AND_AN_OUT_OF_RESTORE_DOMAIN_LINEARIZABLE_WITNESS_IMPLEMENTATION",
        "PIN_OPENBAO_CLUSTER_NODE_TRANSIT_MOUNT_KEY_NAME_NONDERIVED_NONBATCH_CONTEXT_FREE_ED25519_VERSION_PUBLIC_KEY_AND_MINIMUM_VERSION_STATE",
        "DISABLE_HIDDEN_PROVIDER_RETRIES_AND_RECORD_EVERY_WIRE_ATTEMPT_AND_REDIRECT_TARGET",
        "PIN_FAULT_CONTROLLER_TOPOLOGY_RESOURCE_CAPS_SEEDS_AND_MONOTONIC_CLOCK",
        "BIND_OWNER_CUSTODIAN_LAB_CREDENTIAL_AND_RESOURCE_AUTHORITY_BEFORE_START",
    ],
}


class PreregistrationError(ValueError):
    """Raised when the frozen preregistration contract drifts."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PreregistrationError(message)


def exact_keys(value: Any, expected: tuple[str, ...], label: str) -> None:
    require(type(value) is dict, f"{label} must be an object")
    require(tuple(sorted(value)) == tuple(sorted(expected)), f"{label} key drift")


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
        raise PreregistrationError(f"cannot canonicalize value: {exc}") from exc


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _validate_boundary(boundary: Any) -> None:
    exact_keys(
        boundary,
        (
            "condition_output_authorized",
            "cost_authority_bound",
            "credentials_accessed",
            "experiment_executed",
            "live_generator_in_scope",
            "live_output_permit_defined",
            "paid_resources_provisioned",
            "production_adapter_in_scope",
            "provider_called",
            "receipt_is_output_permit",
            "side_effects_unlocked",
        ),
        "boundary",
    )
    for key, value in boundary.items():
        if key == "side_effects_unlocked":
            require(value == "NONE", "boundary side effects are not NONE")
        else:
            require(value is False, f"boundary {key} must be false")


def _validate_source_claims(claims: Any) -> None:
    require(type(claims) is list and len(claims) == 16, "official source claim count drift")
    seen: set[str] = set()
    for index, claim in enumerate(claims):
        label = f"official_source_claims[{index}]"
        exact_keys(
            claim,
            (
                "claim",
                "claim_id",
                "content_hash_attested",
                "evidence_class",
                "retrieved_on",
                "url",
            ),
            label,
        )
        claim_id = claim["claim_id"]
        require(type(claim_id) is str and claim_id in SOURCE_IDS, f"{label} unknown claim id")
        require(claim_id not in seen, f"{label} duplicate claim id")
        seen.add(claim_id)
        require(
            type(claim["claim"]) is str and len(claim["claim"]) >= 40,
            f"{label} claim is not decision-useful",
        )
        require(claim["content_hash_attested"] is False, f"{label} content hash overclaim")
        require(
            claim["evidence_class"] == "OFFICIAL_DOCUMENTATION_DIRECT",
            f"{label} evidence class drift",
        )
        require(claim["retrieved_on"] == "2026-07-15", f"{label} retrieval date drift")
        url = claim["url"]
        require(type(url) is str and url.startswith("https://"), f"{label} URL is not HTTPS")
        host = url.split("/", 3)[2]
        require(host in OFFICIAL_HOSTS, f"{label} URL is not an approved official host")
        if claim_id == "GSP03":
            require(
                claim["claim"]
                == "A Spanner commit deadline can expire even though the transaction may already have committed.",
                f"{label} direct-fact boundary drift",
            )
        if claim_id == "ETC04":
            require(
                claim["claim"]
                == "etcd snapshot restore creates a new logical cluster with rewritten member and cluster IDs, can move perceived revisions backward, and supports revision bump plus mark-compacted recovery controls.",
                f"{label} restore direct-fact boundary drift",
            )
    require(seen == set(SOURCE_IDS), "official source claim identity closure drift")


def _validate_invariants(
    invariants: Any,
    expected_ids: tuple[str, ...],
    label: str,
) -> set[str]:
    require(
        type(invariants) is list and len(invariants) == len(expected_ids),
        f"{label} count drift",
    )
    seen: set[str] = set()
    for index, invariant in enumerate(invariants):
        row_label = f"{label}[{index}]"
        exact_keys(
            invariant,
            ("evidence_needed", "invariant_id", "statement"),
            row_label,
        )
        invariant_id = invariant["invariant_id"]
        require(invariant_id in expected_ids, f"{row_label} unknown invariant")
        require(invariant_id not in seen, f"{row_label} duplicate invariant")
        seen.add(invariant_id)
        for field in ("evidence_needed", "statement"):
            require(
                type(invariant[field]) is str
                and len(invariant[field]) >= 20
                and re.fullmatch(r"[A-Z0-9_]+", invariant[field]) is not None,
                f"{row_label} {field} shape drift",
            )
        if invariant_id in EXPECTED_CRITICAL_INVARIANTS:
            expected_evidence, expected_statement = EXPECTED_CRITICAL_INVARIANTS[invariant_id]
            require(
                invariant["evidence_needed"] == expected_evidence,
                f"{row_label} critical evidence drift",
            )
            require(
                invariant["statement"] == expected_statement,
                f"{row_label} critical statement drift",
            )
    require(seen == set(expected_ids), f"{label} identity closure drift")
    return seen


def _validate_cases(
    cases: Any,
    expected_ids: tuple[str, ...],
    track_invariants: set[str],
    track_id: str,
) -> tuple[set[str], set[str]]:
    require(type(cases) is list and len(cases) == len(expected_ids), f"{track_id} case count drift")
    seen: set[str] = set()
    referenced_sources: set[str] = set()
    referenced_track_invariants: set[str] = set()
    for index, case in enumerate(cases):
        label = f"{track_id}.cases[{index}]"
        require(type(case) is dict and type(case.get("case_id")) is str, f"{label} shape drift")
        case_id = case["case_id"]
        expected_case_keys = {
            "allowed_classifications",
            "candidate_requirement",
            "case_id",
            "evidence_locus",
            "family",
            "forbidden_claims",
            "injection_cut",
            "invariant_ids",
            "permit_allowed",
            "source_ids",
        }
        if case_id in EXPECTED_CASE_VARIANTS:
            expected_case_keys.add("injection_variants")
        require(set(case) == expected_case_keys, f"{label} key drift")
        require(case_id in expected_ids, f"{label} unknown case id")
        require(case_id not in seen, f"{label} duplicate case id")
        seen.add(case_id)
        require(case["permit_allowed"] is False, f"{label} permit must be false")
        require(case["evidence_locus"] in ALLOWED_EVIDENCE_LOCI, f"{label} evidence locus drift")
        if track_id == MANAGED_TRACK:
            require(
                case["evidence_locus"] != "SELF_HOSTED_ADVERSARIAL_LAB",
                f"{label} cross-track evidence locus",
            )
        else:
            require(
                case["evidence_locus"] != "MANAGED_SERVICE_WITH_CLIENT_FAULT_PROXY",
                f"{label} cross-track evidence locus",
            )
        for field in ("candidate_requirement", "family", "injection_cut"):
            require(
                type(case[field]) is str
                and len(case[field]) >= 4
                and re.fullmatch(r"[A-Z0-9_]+", case[field]) is not None,
                f"{label} {field} shape drift",
            )
        classifications = case["allowed_classifications"]
        require(type(classifications) is list and classifications, f"{label} classifications empty")
        require(
            len(classifications) == len(set(classifications))
            and set(classifications) <= ALLOWED_CLASSIFICATIONS,
            f"{label} classification drift",
        )
        forbidden = case["forbidden_claims"]
        require(type(forbidden) is list and forbidden, f"{label} forbidden claims empty")
        require(len(forbidden) == len(set(forbidden)), f"{label} duplicate forbidden claim")
        require(
            all(
                type(item) is str and re.fullmatch(r"[A-Z0-9_]+", item) is not None
                for item in forbidden
            ),
            f"{label} forbidden claim shape drift",
        )
        invariant_ids = case["invariant_ids"]
        require(type(invariant_ids) is list and invariant_ids, f"{label} invariant refs empty")
        require(len(invariant_ids) == len(set(invariant_ids)), f"{label} duplicate invariant ref")
        allowed_invariants = track_invariants | set(GLOBAL_INVARIANT_IDS)
        require(set(invariant_ids) <= allowed_invariants, f"{label} unknown invariant ref")
        referenced_track_invariants.update(set(invariant_ids) & track_invariants)
        source_ids = case["source_ids"]
        require(type(source_ids) is list and source_ids, f"{label} source refs empty")
        require(len(source_ids) == len(set(source_ids)), f"{label} duplicate source ref")
        require(set(source_ids) <= set(SOURCE_IDS), f"{label} unknown source ref")
        referenced_sources.update(source_ids)
        if case_id in EXPECTED_CASE_VARIANTS:
            require(
                case["injection_variants"] == EXPECTED_CASE_VARIANTS[case_id],
                f"{label} injection variant closure drift",
            )
        if case_id in EXPECTED_CRITICAL_CASE_FIELDS:
            for field, expected in EXPECTED_CRITICAL_CASE_FIELDS[case_id].items():
                require(case[field] == expected, f"{label} critical {field} drift")
    require(seen == set(expected_ids), f"{track_id} case identity closure drift")
    require(
        referenced_track_invariants == track_invariants,
        f"{track_id} has an unexercised invariant",
    )
    return referenced_sources, referenced_track_invariants


def _validate_track(track: Any, expected_track: str) -> set[str]:
    expected_track_keys = {
        "cases",
        "claim_ceiling",
        "invariants",
        "preflight_requirements",
        "question",
        "resource_authority",
        "signing_attempt_state_machine",
        "systems",
        "track_id",
    }
    if expected_track == MANAGED_TRACK:
        expected_track_keys.add("message_frame_reference")
    else:
        expected_track_keys.add("restore_witness_protocol")
    require(type(track) is dict and set(track) == expected_track_keys, f"{expected_track} key drift")
    require(track["track_id"] == expected_track, f"{expected_track} track id drift")
    require(
        track["resource_authority"].startswith("UNBOUND_NO_"),
        f"{expected_track} resource authority overclaim",
    )
    require(
        type(track["question"]) is str
        and re.fullmatch(r"[A-Z0-9_]+", track["question"]) is not None,
        f"{expected_track} question drift",
    )
    preflight = track["preflight_requirements"]
    require(type(preflight) is list and len(preflight) == 6, f"{expected_track} preflight drift")
    require(len(preflight) == len(set(preflight)), f"{expected_track} duplicate preflight")
    require(
        all(type(item) is str and re.fullmatch(r"[A-Z0-9_]+", item) for item in preflight),
        f"{expected_track} preflight shape drift",
    )
    require(
        preflight == EXPECTED_PREFLIGHT_REQUIREMENTS[expected_track],
        f"{expected_track} preflight semantic drift",
    )
    require(
        track["signing_attempt_state_machine"]
        == EXPECTED_SIGNING_STATE_MACHINES[expected_track],
        f"{expected_track} signing attempt state machine drift",
    )
    if expected_track == MANAGED_TRACK:
        require(
            track["message_frame_reference"] == EXPECTED_MESSAGE_FRAME_REFERENCE,
            "managed message-frame reference drift",
        )
        require(
            track["claim_ceiling"] == "CLIENT_CONFORMANCE_AND_MANAGED_SERVICE_SEMANTICS_ONLY",
            "managed claim ceiling drift",
        )
        require(track["systems"] == ["GOOGLE_CLOUD_SPANNER", "GOOGLE_CLOUD_KMS"], "managed systems drift")
        invariant_ids = _validate_invariants(
            track["invariants"], MANAGED_INVARIANT_IDS, "managed invariants"
        )
        source_refs, _ = _validate_cases(
            track["cases"], MANAGED_CASE_IDS, invariant_ids, MANAGED_TRACK
        )
    else:
        require(
            track["restore_witness_protocol"] == EXPECTED_RESTORE_WITNESS_PROTOCOL,
            "self-hosted restore witness protocol drift",
        )
        require(
            track["claim_ceiling"] == "OWNED_LAB_ADVERSARIAL_BEHAVIOR_ONLY",
            "self-hosted claim ceiling drift",
        )
        require(track["systems"] == ["ETCD_3_6", "OPENBAO_TRANSIT"], "self-hosted systems drift")
        invariant_ids = _validate_invariants(
            track["invariants"], SELF_HOSTED_INVARIANT_IDS, "self-hosted invariants"
        )
        source_refs, _ = _validate_cases(
            track["cases"], SELF_HOSTED_CASE_IDS, invariant_ids, SELF_HOSTED_TRACK
        )
    return source_refs


def validate_contract(contract: Any) -> None:
    exact_keys(
        contract,
        (
            "acceptance_policy",
            "assignment_protocol",
            "baseline_commit",
            "boundary",
            "cross_track_non_equivalence",
            "data_quality_plan",
            "date",
            "experimental_unit",
            "global_invariants",
            "next_unit",
            "non_claims",
            "official_source_claims",
            "predecessor_packet",
            "purpose",
            "schema",
            "status",
            "tracks",
        ),
        "contract",
    )
    require(contract["schema"] == CONTRACT_SCHEMA, "contract schema drift")
    require(contract["date"] == "2026-07-15", "contract date drift")
    require(contract["baseline_commit"] == BASELINE_COMMIT, "baseline commit drift")
    require(contract["status"] == STATUS, "contract status drift")
    require(contract["next_unit"] == NEXT_UNIT, "contract next unit drift")
    require(
        contract["purpose"]
        == "PREREGISTER_TWO_NON_AUTHORIZING_NON_EQUIVALENT_REFERENCE_PROVIDER_FAULT_INJECTION_TRACKS",
        "contract purpose drift",
    )
    _validate_boundary(contract["boundary"])
    predecessor = contract["predecessor_packet"]
    exact_keys(predecessor, ("integration_commit", "manifest_path", "source_commit"), "predecessor")
    require(predecessor["integration_commit"] == BASELINE_COMMIT, "predecessor integration drift")
    require(
        predecessor["source_commit"] == "3054ffe692e2e8f4edf22bda86fcbe4c9e1077d2",
        "predecessor source drift",
    )
    require(
        predecessor["manifest_path"]
        == "scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack_v0.json",
        "predecessor manifest path drift",
    )
    acceptance = contract["acceptance_policy"]
    exact_keys(
        acceptance,
        (
            "all_planned_rows_required",
            "hard_fail_conditions",
            "per_case_required_repetitions",
            "post_outcome_exclusions_allowed",
            "statistical_claim_mode",
            "track_comparison_allowed",
        ),
        "acceptance policy",
    )
    require(acceptance["all_planned_rows_required"] is True, "all rows requirement drift")
    require(acceptance["per_case_required_repetitions"] == 30, "repetition count drift")
    require(acceptance["post_outcome_exclusions_allowed"] is False, "post-outcome exclusion allowed")
    require(acceptance["track_comparison_allowed"] is False, "cross-track comparison allowed")
    require(
        acceptance["statistical_claim_mode"] == "NONE_CATEGORICAL_CONFORMANCE_ONLY",
        "statistical claim mode drift",
    )
    hard_fails = acceptance["hard_fail_conditions"]
    require(type(hard_fails) is list and len(hard_fails) == 10, "hard-fail closure drift")
    require(len(hard_fails) == len(set(hard_fails)), "duplicate hard-fail condition")
    require(
        hard_fails[-1]
        == "ANY_RESOURCE_USE_OUTSIDE_SEPARATELY_AUTHORIZED_TRACK_RESOURCE_AND_COST_SCOPE",
        "hard-fail resource scope drift",
    )
    assignment = contract["assignment_protocol"]
    exact_keys(
        assignment,
        (
            "configuration_frozen_before_assignment",
            "deterministic_order_domain",
            "deterministic_order_rule",
            "fresh_namespace_per_run",
            "injection_armed_after_assignment_before_candidate_start",
            "planned_balanced_blocks_per_track",
            "run_id_rule",
            "track_interleaving",
            "zero_post_assignment_case_substitution",
        ),
        "assignment protocol",
    )
    for key in (
        "configuration_frozen_before_assignment",
        "fresh_namespace_per_run",
        "injection_armed_after_assignment_before_candidate_start",
        "zero_post_assignment_case_substitution",
    ):
        require(assignment[key] is True, f"assignment {key} drift")
    require(assignment["planned_balanced_blocks_per_track"] == 30, "balanced block count drift")
    require(assignment["track_interleaving"] == "FORBIDDEN", "track interleaving drift")
    unit = contract["experimental_unit"]
    exact_keys(
        unit,
        ("grain", "planned_run_rows", "repetitions_per_case", "retention_rule", "run_key"),
        "experimental unit",
    )
    require(unit["planned_run_rows"] == 1020, "planned run-row count drift")
    require(unit["repetitions_per_case"] == 30, "unit repetition count drift")
    require(unit["run_key"] == ["TRACK_ID", "CASE_ID", "REPETITION_INDEX"], "run key drift")
    _validate_invariants(contract["global_invariants"], GLOBAL_INVARIANT_IDS, "global invariants")
    _validate_source_claims(contract["official_source_claims"])
    non_claims = contract["non_claims"]
    require(type(non_claims) is list and len(non_claims) == 10, "non-claim closure drift")
    require(len(non_claims) == len(set(non_claims)), "duplicate non-claim")
    cross_track = contract["cross_track_non_equivalence"]
    require(type(cross_track) is list and len(cross_track) == 6, "cross-track closure drift")
    tracks = contract["tracks"]
    require(type(tracks) is list and len(tracks) == 2, "track count drift")
    require([track.get("track_id") for track in tracks] == [MANAGED_TRACK, SELF_HOSTED_TRACK], "track order drift")
    referenced_sources = _validate_track(tracks[0], MANAGED_TRACK)
    referenced_sources.update(_validate_track(tracks[1], SELF_HOSTED_TRACK))
    require(referenced_sources == set(SOURCE_IDS), "one or more official claims are not linked to a case")
    quality = contract["data_quality_plan"]
    exact_keys(
        quality,
        (
            "completeness",
            "consistency",
            "experiment_assignment",
            "integrity",
            "referential_integrity",
            "timeliness",
            "uniqueness",
            "validity",
        ),
        "data quality plan",
    )


def validate_observation(observation: Any) -> None:
    exact_keys(
        observation,
        (
            "audit_scope",
            "credentials_accessed",
            "execution_evidence_sha256",
            "experiment_executed",
            "external_organization_state_observed",
            "future_state_automatically_reaudited",
            "observed_at_utc",
            "official_sources_refetched_before_execution",
            "paid_resources_provisioned",
            "provider_resources_bound",
            "run_rows",
            "schema",
            "side_effects_unlocked",
            "track_case_counts",
        ),
        "observation",
    )
    require(observation["schema"] == OBSERVATION_SCHEMA, "observation schema drift")
    require(
        observation["audit_scope"]
        == "REPOSITORY_AND_CURRENT_PROCESS_HOST_VISIBILITY_NON_SECRET_AUDIT",
        "observation audit scope drift",
    )
    require(observation["observed_at_utc"] == "2026-07-15T18:00:00Z", "observation time drift")
    for key in (
        "credentials_accessed",
        "experiment_executed",
        "external_organization_state_observed",
        "future_state_automatically_reaudited",
        "official_sources_refetched_before_execution",
        "paid_resources_provisioned",
        "provider_resources_bound",
    ):
        require(observation[key] is False, f"observation {key} must be false")
    require(observation["execution_evidence_sha256"] is None, "execution evidence must be absent")
    require(observation["run_rows"] == [], "preregistration observation must have zero run rows")
    require(observation["side_effects_unlocked"] == "NONE", "observation side effects drift")
    require(
        observation["track_case_counts"]
        == {MANAGED_TRACK: 16, SELF_HOSTED_TRACK: 18},
        "observation track case counts drift",
    )


def build_preregistration_receipt(contract: Any, observation: Any) -> dict[str, Any]:
    validate_contract(contract)
    validate_observation(observation)
    return {
        "boundary": {
            "condition_output_authorized": False,
            "cost_authority_bound": False,
            "credentials_accessed": False,
            "experiment_executed": False,
            "live_generator_in_scope": False,
            "live_output_permit_defined": False,
            "paid_resources_provisioned": False,
            "production_adapter_in_scope": False,
            "provider_called": False,
            "receipt_is_output_permit": False,
            "side_effects_unlocked": "NONE",
        },
        "contract_sha256": sha256_value(contract),
        "data_quality": {
            "completeness": "PLAN_PASS_EXECUTION_NOT_EVALUATED",
            "consistency": "PLAN_PASS_EXECUTION_NOT_EVALUATED",
            "execution_rows": 0,
            "integrity": "PLAN_PASS_EXECUTION_NOT_EVALUATED",
            "referential_integrity": "PLAN_PASS_EXECUTION_NOT_EVALUATED",
            "timeliness": "REFETCH_REQUIRED_BEFORE_EXECUTION",
            "uniqueness": "PLAN_PASS_EXECUTION_NOT_EVALUATED",
            "validity": "PLAN_PASS_EXECUTION_NOT_EVALUATED",
        },
        "date": "2026-07-15",
        "decision": DECISION,
        "experiment_counts": {
            "invariants": 34,
            "managed_cases": 16,
            "official_source_claims": 16,
            "planned_run_rows": 1020,
            "repetitions_per_case": 30,
            "self_hosted_cases": 18,
            "tracks": 2,
        },
        "next_unit": NEXT_UNIT,
        "observation_sha256": sha256_value(observation),
        "schema": RECEIPT_SCHEMA,
        "status": STATUS,
        "track_results": {
            MANAGED_TRACK: "PREREGISTERED_NOT_EXECUTED",
            SELF_HOSTED_TRACK: "PREREGISTERED_NOT_EXECUTED",
        },
    }


TSV_FIELDS = (
    ("schema", ("schema",)),
    ("status", ("status",)),
    ("decision", ("decision",)),
    ("date", ("date",)),
    ("contract_sha256", ("contract_sha256",)),
    ("observation_sha256", ("observation_sha256",)),
    ("tracks", ("experiment_counts", "tracks")),
    ("managed_cases", ("experiment_counts", "managed_cases")),
    ("self_hosted_cases", ("experiment_counts", "self_hosted_cases")),
    ("official_source_claims", ("experiment_counts", "official_source_claims")),
    ("invariants", ("experiment_counts", "invariants")),
    ("repetitions_per_case", ("experiment_counts", "repetitions_per_case")),
    ("planned_run_rows", ("experiment_counts", "planned_run_rows")),
    ("execution_rows", ("data_quality", "execution_rows")),
    ("quality_completeness", ("data_quality", "completeness")),
    ("quality_uniqueness", ("data_quality", "uniqueness")),
    ("quality_validity", ("data_quality", "validity")),
    ("quality_consistency", ("data_quality", "consistency")),
    ("quality_integrity", ("data_quality", "integrity")),
    ("quality_referential_integrity", ("data_quality", "referential_integrity")),
    ("quality_timeliness", ("data_quality", "timeliness")),
    ("experiment_executed", ("boundary", "experiment_executed")),
    ("provider_called", ("boundary", "provider_called")),
    ("credentials_accessed", ("boundary", "credentials_accessed")),
    ("paid_resources_provisioned", ("boundary", "paid_resources_provisioned")),
    ("cost_authority_bound", ("boundary", "cost_authority_bound")),
    ("live_generator_in_scope", ("boundary", "live_generator_in_scope")),
    ("production_adapter_in_scope", ("boundary", "production_adapter_in_scope")),
    ("live_output_permit_defined", ("boundary", "live_output_permit_defined")),
    ("receipt_is_output_permit", ("boundary", "receipt_is_output_permit")),
    ("condition_output_authorized", ("boundary", "condition_output_authorized")),
    ("side_effects_unlocked", ("boundary", "side_effects_unlocked")),
    ("managed_track_result", ("track_results", MANAGED_TRACK)),
    ("self_hosted_track_result", ("track_results", SELF_HOSTED_TRACK)),
    ("next_unit", ("next_unit",)),
)


def _lookup(value: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for key in path:
        current = current[key]
    return current


def _tsv_scalar(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return str(value)


def render_receipt_tsv(receipt: dict[str, Any]) -> str:
    rows = [f"{label}\t{_tsv_scalar(_lookup(receipt, path))}" for label, path in TSV_FIELDS]
    return "\n".join(rows) + "\n"


def self_test(contract: Any, observation: Any) -> dict[str, Any]:
    first = build_preregistration_receipt(contract, observation)
    second = build_preregistration_receipt(contract, observation)
    require(canonical_bytes(first) == canonical_bytes(second), "receipt is nondeterministic")
    require(render_receipt_tsv(first) == render_receipt_tsv(second), "TSV is nondeterministic")
    return first


__all__ = [
    "BASELINE_COMMIT",
    "CONTRACT_SCHEMA",
    "DECISION",
    "NEXT_UNIT",
    "OBSERVATION_SCHEMA",
    "PreregistrationError",
    "RECEIPT_SCHEMA",
    "STATUS",
    "build_preregistration_receipt",
    "canonical_bytes",
    "render_receipt_tsv",
    "self_test",
    "sha256_value",
    "validate_contract",
    "validate_observation",
]
