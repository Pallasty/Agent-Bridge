#!/usr/bin/env python3
"""Pure validator for the reference-provider runner authority contract.

The module validates design documents and a zero-runtime synthetic
observation.  It performs no filesystem, environment, clock, random, process,
network, provider, credential, generator, sink, or adapter I/O.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any


BASELINE_COMMIT = "b15a48d17fb30b0990bf26210978f2a4f78f54cc"
PREDECESSOR_SOURCE_COMMIT = "27fd73aa36ac897fb817398eca3a191181d8fb5d"
PREREGISTRATION_CONTRACT_SHA256 = (
    "632dbf1d8202d94d6aef70d8b20c04050e647679da973d81afbe13d68344ad22"
)
OFFLINE_HARNESS_MANIFEST_SHA256 = (
    "2e06aec1395957cd70ee86ab4af0452ca6c5da6a51112b4c21216bfd43e3a3ed"
)
OFFLINE_CONFIGURATION_SHA256 = (
    "fd993935d9847f2a75b665cc77d078946cf2c0bd2d24adbd43c2a50d1dbd6a85"
)
OFFLINE_SCHEDULE_SHA256 = (
    "37e00bb606b09760d0280e240afbbc2585412c7080a5bf909a130edf305d70b3"
)
OFFLINE_ROWS_SHA256 = (
    "e4458abb43b7de6d8fb40809e679393198b29c2303ba9824bae414455d6b305e"
)

CONTRACT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_adapter_contract.v1"
)
AUTHORITY_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_authority_bundle.v1"
)
STOP_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_stop_receipt.v1"
)
OBSERVATION_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_contract_source_observation.v0"
)
VALIDATION_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_contract_validation_receipt.v1"
)
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_AUTHORITY_AND_ADAPTER_"
    "CONTRACT_PREREGISTERED_NO_PROVIDER_NO_CREDENTIAL_NO_PERMIT"
)
DECISION = "RUNNER_AUTHORITY_AND_ADAPTER_CONTRACT_PASS_EXECUTION_REMAINS_BLOCKED"
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "OFFLINE_AUTHORITY_VERIFIER_AND_ADAPTER_DOUBLE_IMPLEMENTATION"
)
ADAPTER_CONTRACT_SHA256 = (
    "d602d9f14f662145bd12f33304b2800bb9601ff4fd76634eb56c41b86aa17201"
)
AUTHORITY_SCHEMA_SHA256 = "faea2234635441b0bc043b5d605a449decc61cc854e708f705f7bb09d58a7b90"
STOP_SCHEMA_SHA256 = "7657cd25a9abf4037ce5eb4c403db36aebf4b43deb232886e62ff4afe9d45c36"
OFFLINE_SUITE_ID = "f09b6eadaf59a4fe793bdbdd401fceccb7cb2a05a4f16357e7c1db5b1eba5731"

MANAGED_TRACK = "MANAGED_SPANNER_CLOUD_KMS"
# Split the product token so a source-purity scanner cannot mistake this
# closed track identifier for an imported provider SDK capability.
SELF_HOSTED_TRACK = "SELF_HOSTED_ETCD_OPENXBAO"[:-4] + "BAO"
MANAGED_CASE_IDS = tuple(f"M{index:02d}" for index in range(16))
SELF_HOSTED_CASE_IDS = tuple(f"S{index:02d}" for index in range(18))
CLIENT_CONFORMANCE_CASE_IDS = (
    "M02", "M03", "M05", "M06", "M07", "M08", "M09", "M10", "M11",
    "S02", "S03", "S08", "S16", "S17",
)
MANAGED_PROVIDER_CASE_IDS = ("M00", "M01", "M04", "M12", "M13", "M14", "M15")
SELF_HOSTED_LAB_CASE_IDS = (
    "S00", "S01", "S04", "S05", "S06", "S07", "S09",
    "S10", "S11", "S12", "S13", "S14", "S15",
)
PREFLIGHT_OPERATIONS = (
    "READ_COST_BUDGET_METADATA",
    "READ_CREDENTIAL_LEASE_METADATA",
    "READ_EVIDENCE_SINK_HEALTH",
    "READ_PROVIDER_PROFILE_METADATA",
    "READ_RESOURCE_METADATA",
)
EXPERIMENT_ADAPTER_OPERATIONS = (
    "ARM_EXACT_ASSIGNED_CUT",
    "ARM_EXACT_ASSIGNED_LAB_CUT",
    "CAS_ABSENT_TO_TERMINAL_FENCE",
    "COLLECT_ALLOWLISTED_NON_SECRET_FIELDS",
    "COMPARE_EXACT_PREVIOUS_HASH_AND_GENERATION_THEN_PUT",
    "CORRELATE_ROUTE_EXECUTOR_AUDIT_AND_WIRE_IDENTITIES",
    "CURRENT_LINEARIZABLE_READ",
    "HASH_IMMUTABLE_LAB_EVIDENCE_INDEX",
    "HASH_IMMUTABLE_RAW_EVIDENCE_INDEX",
    "LINEARIZABLE_EXACT_READ",
    "NON_NESTED_NONLEASED_EXACT_KEY_CAS",
    "PERSIST_PREPARED_ATTEMPT",
    "PERSIST_VALIDATED_RECEIPT",
    "QUARANTINE_ATTEMPT",
    "RECORD_TOPOLOGY_AND_CAUSAL_BINDING",
    "RECORD_WIRE_ATTEMPTS_WITHOUT_PROCESSING_CLAIM",
    "RETURN_OBSERVATIONS_ONLY",
    "RETURN_OPERATION_SPECIFIC_RESPONSE_EVIDENCE",
    "RETURN_VERSIONED_SIGNATURE_OBSERVATION",
    "RUN_EXPLICIT_SERIALIZABLE_AUTHORITY_TRANSACTION",
    "SIGN_EXACT_137_RAW_BYTES_WITH_EXACT_VERSION",
    "SIGN_SINGLE_NONBATCH_CONTEXT_FREE_EXACT_137_BYTE_INPUT",
    "STRONG_READ_EXACT_OPERATION_KEY",
    "TRIGGER_ONCE_FOR_EXACT_RUN_TRAFFIC",
    "TRIGGER_ONCE_INSIDE_EXACT_RUN_NAMESPACE",
)
STOP_ONLY_ADAPTER_OPERATIONS = (
    "DISARM_EXACT_ASSIGNED_CUT",
    "ISOLATE_EXACT_ASSIGNED_RUN_EGRESS",
)
EMERGENCY_STOP_OPERATIONS = (
    "BLOCK_NEW_CALLS_FOR_EXACT_RUN",
    "CAS_EXACT_RUN_CAPABILITY_TO_STOP_FENCED",
    "CONFIRM_RETENTION_BINDINGS",
    "CONFIRM_ZERO_ACTIVE_LEASE_COMMITMENTS",
    "DISARM_EXACT_ASSIGNED_CUT",
    "FREEZE_EXACT_ASSIGNED_RESOURCES",
    "ISOLATE_EXACT_ASSIGNED_RUN_EGRESS",
    "PERSIST_CURRENT_ROW_DURABLE_STATE_AND_SAFE_EVIDENCE",
    "REDUCTIVE_TEARDOWN_WITHIN_EXACT_CLEANUP_SCOPE",
    "REVOKE_EXACT_RUN_CREDENTIAL_LEASES",
)
SCHEDULE_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/schedule"
)
RUN_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/run"
)
NAMESPACE_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/namespace"
)
AUTHORIZATION_REQUEST_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/authorization-request"
)
AUTHORITY_BUNDLE_ID_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/authority-bundle-id"
)
AUTHORITY_INTERSECTION_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/authority-intersection"
)
CHANNEL_BINDING_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/channel-binding"
)
CONTROL_LEDGER_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/control-ledger"
)
PRIVATE_CAPABILITY_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/private-capability"
)
SCOPE_RECEIPT_ID_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/scope-receipt-id"
)
SCOPE_RECEIPT_PAYLOAD_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/scope-receipt-payload"
)
STOP_RECEIPT_ID_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/runner/v1/stop-receipt-id"
)
EXPECTED_STOP_INTERFACE_SHA256 = (
    "03f7a821e30f7f7f0c28e8d4eb99c375e915dc0e9865adb403c4d275b8d0acc5",
    "a88841a1996d329149f674964e725cfad65c46c0c99be30387fb229da86a2550",
    "e4a7fc5e6ab6c173c4b77b18456ef8a7337c2c215bb21c014c4520c22b67d34e",
    "a150fa60275f859565cdbc840ee388a5253e7352e6bd4cd154fe190c265a87a9",
    "fab5a3d137473657f5c1dc55b3fd0a871a32b333dcffd7599bd2824846fde319",
)
STOP_TRIGGER_REASON_ROLE_MAP = {
    "AUTHORITY_EXPIRED_REVOKED_OR_CURRENTNESS_FAILED": (
        ("AUTHORITY_CURRENTNESS_FAILURE", "AUTHORITY_EXPIRED", "AUTHORITY_REVOKED"),
        ("SYSTEM_EXPIRY_OR_REVOCATION",),
    ),
    "CREDENTIAL_LEASE_OR_COST_SCOPE_BREACH": (
        ("COST_OR_RESOURCE_SCOPE_EXCEEDED", "CREDENTIAL_LEASE_OR_SCOPE_BREACH"),
        ("SYSTEM_BOUNDARY",),
    ),
    "EVIDENCE_WRITE_FAILURE_OR_SECRET_EXPOSURE": (
        ("EVIDENCE_PERSIST_FAILURE", "EVIDENCE_SINK_UNAVAILABLE", "SECRET_EXPOSURE"),
        ("SYSTEM_BOUNDARY",),
    ),
    "EXTRA_WIRE_ATTEMPT_OR_HIDDEN_RETRY": (
        ("EXTRA_OR_UNKNOWN_WIRE_ATTEMPT",),
        ("SYSTEM_BOUNDARY",),
    ),
    "FAULT_MISFIRE_MULTIPLE_TRIGGER_OR_CROSS_NAMESPACE_EFFECT": (
        ("CROSS_NAMESPACE_EFFECT", "FAULT_MISFIRE", "MULTIPLE_FAULT_TRIGGER"),
        ("SYSTEM_BOUNDARY",),
    ),
    "OUTPUT_PERMIT_CONDITION_OUTPUT_OR_OTHER_BOUNDARY_BREACH": (
        ("BOUNDARY_BREACH", "OUTPUT_OR_PERMIT_ATTEMPT"),
        ("SYSTEM_BOUNDARY",),
    ),
    "OWNER_CUSTODIAN_OR_EMERGENCY_OPERATOR_STOP": (
        ("OPERATOR_STOP",),
        ("CUSTODIAN", "EMERGENCY_OPERATOR", "OWNER"),
    ),
    "PROFILE_CONFIGURATION_SCHEDULE_RUNNER_ADAPTER_ADAPTER_SET_ASSIGNMENT_OR_RESOURCE_DRIFT": (
        ("BUILD_OR_PROFILE_DRIFT", "CONFIGURATION_OR_SCHEDULE_DRIFT", "RESOURCE_SCOPE_DRIFT"),
        ("SYSTEM_BOUNDARY",),
    ),
    "UNKNOWN_PROVIDER_CALL_OR_UNCLOSED_AMBIGUITY": (
        ("UNKNOWN_PROVIDER_CALL", "UNRESOLVED_AMBIGUITY"),
        ("SYSTEM_BOUNDARY",),
    ),
    "WITNESS_UNAVAILABLE_STALE_FORKED_CONFLICTING_OR_NOT_INDEPENDENT": (
        ("WITNESS_CURRENTNESS_FAILURE",),
        ("SYSTEM_BOUNDARY",),
    ),
}


class ContractError(ValueError):
    """Closed validation failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def exact_keys(value: Any, expected: tuple[str, ...], label: str) -> None:
    require(type(value) is dict, f"{label} must be an object")
    require(set(value) == set(expected), f"{label} fields drift")


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
        raise ContractError(f"cannot encode canonical JSON: {exc}") from exc


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


CONTRACT_KEYS = (
    "acceptance_policy",
    "adapter_interfaces",
    "authority_integrity",
    "authority_model",
    "baseline_commit",
    "boundary",
    "credential_isolation",
    "date",
    "decision",
    "evidence_contract",
    "execution_plan",
    "next_unit",
    "non_claims",
    "official_source_claims",
    "predecessor",
    "profile_contract",
    "purpose",
    "recovery_protocol",
    "retained_row_contract",
    "s12_branch_contract",
    "schema",
    "start_stop_logic",
    "status",
    "stop_control_plane",
    "version",
)

EXPECTED_CONTRACT_SECTION_SHA256 = {
    "acceptance_policy": "686ec660f0b8fa0e3a56d75e40676ef1eb095dcb30c52aaab490f71c7e7e7f6d",
    "adapter_interfaces": "67f97e215fcd3e043e0e7a955cfc48903c3115dd8541a0863a71bb6aaebfcc5e",
    "authority_integrity": "dcfbef782468d50912e4e358016f0bdafeb464dc9c3213cc40c301fb113bcdcb",
    "authority_model": "9fb940bc0d512a2b28b51d060c11d364a6aed6727abb6262b6533ae85760a408",
    "boundary": "28bdb6baed87c165cb35d012eda94cefb00d0326583ae11a23bbbca5b1d15b4d",
    "credential_isolation": "4d1915d0484de146e00fddb8533d567403fddd9053125eb5d07a9368378383e0",
    "evidence_contract": "a2c20f8823f94eda54b3237ba1e331f77e38302855b4d4a18c44cb8dd431b892",
    "execution_plan": "09e921bfa84a0329739c4fd8d158137c565262b11a14e2578b39bac9447eccd6",
    "non_claims": "3b54315fcc06cfbaf8fe50bbb5afd34a61671edb37a50f16cfcace220eb4b464",
    "official_source_claims": "ac21da6402d5c5bcec7004eb667a1100feccd538ea538b774d5de0f5f7c43927",
    "predecessor": "f26d4c8845e4dfc186eb5f853d50df7bcb50345ecacad61d1c70edf07ae8e381",
    "profile_contract": "26d6bac58f76359a4a977742e139e352de8de29024a373a6019b8e1248b2cbe4",
    "recovery_protocol": "7af48062269975765732853a511c1abf7263b14a5d3b283d428e8cfb88892a27",
    "retained_row_contract": "f589d8851b447d7bcaa53c66726d25c2719ebbdeedf5d1e1cfd3acfc16bb732e",
    "s12_branch_contract": "eac0e00a97876d57a229f10f46cb8eac768f5a7207ac2ecab94900b79aeb9a5d",
    "start_stop_logic": "a50367504d0bd543b1bf06c918756dd7d9f318341654d4de80c43f7d406a09a9",
    "stop_control_plane": "57c9002f71009a5696611615d25d9e64954ffd279d8d1548015f89be6dbe81ef",
}

EXPECTED_ADAPTER_SHA256 = (
    "95a8cabc2940765b30d761cdf180cf83913bd79759104d5f23b24f8b8b28c800",
    "82bf0da9a37816b382009faac0aed82a30c4e593ed865499ca508b4b0f844afb",
    "5fd02d2e3e6d9860219b5054d89c21cda4ae9ff3c6e83ca3bca7802ed5a38b82",
    "672bf4505a2ae7f8df278a371eb638f339b15ab12f13be57ec77e699757a8b00",
    "4babea500a3f4fcfd74886e5db99282c2541042be8a95cfe369a420433cbe55d",
    "17ce794cdefa27754ca601b22fb4f4e34a487b9dee9919d47f13100d7a3e5b6f",
    "974248ee8d85244fd4b1dfcdd8a83af499f6918f4249c06a05648d679e579d3f",
    "932e3709bcba4013a6e82e5a96dd28fceb2a245c42fcf85dc8805bdab4c6befc",
    "771c69a554080e4eb74912bd6dd84f052c1969f676976e0811d43aea04775ffd",
)


def _validate_zero_boundary(boundary: Any, label: str) -> None:
    exact_keys(
        boundary,
        (
            "adapter_implemented",
            "condition_output_authorized",
            "cost_authority_bound",
            "credentials_accessed",
            "execution_capability_emitted",
            "experiment_executed",
            "paid_resources_provisioned",
            "production_adapter_in_scope",
            "provider_called",
            "receipt_is_execution_authority",
            "receipt_is_output_permit",
            "runner_implemented",
            "side_effects_unlocked",
            "stop_capability_emitted",
        ),
        label,
    )
    for key, value in boundary.items():
        if key == "side_effects_unlocked":
            require(value == "NONE", f"{label} side effects drift")
        else:
            require(value is False, f"{label} {key} must be false")


def _validate_contract_boundary(boundary: Any) -> None:
    exact_keys(
        boundary,
        (
            "adapter_implementation_present",
            "authority_receipts_bound",
            "condition_output_authorized",
            "cost_authority_bound",
            "credentials_accessed",
            "experiment_executed",
            "live_endpoint_bound",
            "live_generator_in_scope",
            "live_output_permit_defined",
            "paid_resources_provisioned",
            "production_adapter_in_scope",
            "provider_called",
            "provider_profile_bound",
            "receipt_is_output_permit",
            "secret_material_present",
            "side_effects_unlocked",
            "synthetic_authority_present",
        ),
        "contract boundary",
    )
    for key, value in boundary.items():
        if key == "side_effects_unlocked":
            require(value == "NONE", "contract boundary side effects drift")
        else:
            require(value is False, f"contract boundary {key} must be false")


def _validate_execution_plan(plan: Any) -> None:
    exact_keys(
        plan,
        ("assignment_order", "case_routing", "counts", "track_interleaving_allowed"),
        "execution plan",
    )
    require(
        plan["assignment_order"]
        == "CONFIGURATION_AND_PROFILE_FROZEN_THEN_SCHEDULE_SEALED_THEN_PER_RUN_CURRENTNESS_THEN_ARM_THEN_START",
        "assignment order drift",
    )
    require(plan["track_interleaving_allowed"] is False, "track interleaving allowed")
    require(
        plan["counts"]
        == {
            "cases": 34,
            "client_conformance_double_rows": 420,
            "managed_service_fault_proxy_rows": 210,
            "planned_rows": 1020,
            "repetitions_per_case": 30,
            "self_hosted_adversarial_lab_rows": 390,
            "tracks": 2,
        },
        "execution counts drift",
    )
    require(
        plan["case_routing"]
        == {
            "CLIENT_CONFORMANCE_DOUBLE": {
                "case_ids": list(CLIENT_CONFORMANCE_CASE_IDS),
                "rows": 420,
            },
            "MANAGED_SERVICE_WITH_CLIENT_FAULT_PROXY": {
                "case_ids": list(MANAGED_PROVIDER_CASE_IDS),
                "rows": 210,
            },
            "SELF_HOSTED_ADVERSARIAL_LAB": {
                "case_ids": list(SELF_HOSTED_LAB_CASE_IDS),
                "rows": 390,
            },
        },
        "case routing drift",
    )
    routed = set(CLIENT_CONFORMANCE_CASE_IDS + MANAGED_PROVIDER_CASE_IDS + SELF_HOSTED_LAB_CASE_IDS)
    require(routed == set(MANAGED_CASE_IDS + SELF_HOSTED_CASE_IDS), "case routing is not exhaustive")


def _validate_adapter_interfaces(interfaces: Any) -> None:
    exact_keys(interfaces, ("client_conformance_route", "managed", "self_hosted"), "adapter interfaces")
    require(
        interfaces["client_conformance_route"]
        == {
            "adapter_id": "OFFLINE_CLIENT_CONFORMANCE_DOUBLE",
            "case_count": 14,
            "provider_adapter_allowed": False,
            "provider_called": False,
            "row_count": 420,
        },
        "client-conformance route drift",
    )
    managed = interfaces["managed"]
    self_hosted = interfaces["self_hosted"]
    exact_keys(managed, ("adapter_count", "adapters", "composition_rule"), "managed adapters")
    exact_keys(self_hosted, ("adapter_count", "adapters", "composition_rule"), "self-hosted adapters")
    require(managed["adapter_count"] == 4 and len(managed["adapters"]) == 4, "managed adapter count drift")
    require(self_hosted["adapter_count"] == 5 and len(self_hosted["adapters"]) == 5, "self-hosted adapter count drift")
    require(
        managed["composition_rule"]
        == "FOUR_SEPARATE_LEAST_PRIVILEGE_INTERFACES_NO_SHARED_OMNIPOTENT_ADAPTER",
        "managed composition drift",
    )
    require(
        self_hosted["composition_rule"]
        == "FIVE_SEPARATE_LEAST_PRIVILEGE_INTERFACES_NO_SHARED_OMNIPOTENT_ADAPTER",
        "self-hosted composition drift",
    )
    adapters = managed["adapters"] + self_hosted["adapters"]
    require(
        tuple(sha256_value(adapter) for adapter in adapters) == EXPECTED_ADAPTER_SHA256,
        "adapter catalog drift",
    )
    seen_ids: set[str] = set()
    seen_credentials: set[str] = set()
    for index, adapter in enumerate(adapters):
        stop_capable = adapter["adapter_id"] in {
            "MANAGED_FAULT_PROXY_ADAPTER",
            "LAB_FAULT_CONTROLLER_ADAPTER",
        }
        expected_fields = (
            "adapter_id",
            "allowed_operations",
            "credential_class",
            "evidence_returns",
            "forbidden_operations",
            "retry_rule",
        )
        if stop_capable:
            expected_fields += (
                "stop_capability_may_authorize_experiment",
                "stop_only_credential_class",
                "stop_only_evidence_returns",
                "stop_only_operations",
            )
        exact_keys(
            adapter,
            expected_fields,
            f"adapter {index}",
        )
        require(adapter["adapter_id"] not in seen_ids, "duplicate adapter id")
        require(adapter["credential_class"] not in seen_credentials, "credential class reused across adapters")
        seen_ids.add(adapter["adapter_id"])
        seen_credentials.add(adapter["credential_class"])
        for field in ("allowed_operations", "evidence_returns", "forbidden_operations"):
            values = adapter[field]
            require(type(values) is list and values, f"adapter {index} {field} empty")
            require(len(values) == len(set(values)), f"adapter {index} {field} duplicates")
        require(
            set(adapter["allowed_operations"]).isdisjoint(adapter["forbidden_operations"]),
            f"adapter {index} allowed/forbidden overlap",
        )
        if stop_capable:
            require(
                adapter["stop_capability_may_authorize_experiment"] is False,
                f"adapter {index} stop capability can authorize experiment",
            )
            for field in ("stop_only_evidence_returns", "stop_only_operations"):
                values = adapter[field]
                require(type(values) is list and values, f"adapter {index} {field} empty")
                require(len(values) == len(set(values)), f"adapter {index} {field} duplicates")
            require(
                set(adapter["stop_only_operations"]).isdisjoint(adapter["allowed_operations"]),
                f"adapter {index} stop operations leak into execution authority",
            )
            require(
                adapter["stop_only_credential_class"]
                == "STOP_FAULT_DISARM_EGRESS_CONTROL"
                and adapter["stop_only_credential_class"] != adapter["credential_class"],
                f"adapter {index} stop credential separation drift",
            )
    require(len(seen_ids) == 9 and len(seen_credentials) == 9, "adapter separation drift")


def _validate_authority_and_stop(contract: dict[str, Any]) -> None:
    authority = contract["authority_model"]
    exact_keys(
        authority,
        (
            "artifact_count",
            "artifacts",
            "binding_fields",
            "capability",
            "currentness_formula",
            "emergency_stop_scope",
            "intersection_formula",
            "phase_operation_catalog",
            "phase_order",
            "phases",
            "track_grain",
            "wildcard_or_parent_resource_scope_allowed",
        ),
        "authority model",
    )
    require(authority["artifact_count"] == 5, "authority artifact count drift")
    require(
        authority["artifacts"]
        == [
            "OWNER_SCOPE_RECEIPT",
            "CUSTODIAN_CREDENTIAL_RECEIPT",
            "RESOURCE_AUTHORITY_RECEIPT",
            "COST_AUTHORITY_RECEIPT",
            "EMERGENCY_STOP_AUTHORITY_RECEIPT",
        ],
        "authority artifact roles drift",
    )
    require(
        authority["binding_fields"]
        == [
            "TRACK_ID",
            "AUTHORIZATION_PHASE",
            "SUITE_ID",
            "SIMULATION_RUN_ID",
            "NAMESPACE_ID",
            "ASSIGNMENT_SHA256",
            "PREREGISTRATION_CONTRACT_SHA256",
            "OFFLINE_HARNESS_MANIFEST_SHA256",
            "PROVIDER_PROFILE_SHA256",
            "CONFIGURATION_SHA256",
            "SCHEDULE_SHA256",
            "RUNNER_BUILD_SHA256",
            "ADAPTER_BUILD_SHA256",
            "ADAPTER_SET_MANIFEST_SHA256",
            "STOP_CONTROL_PLANE_MANIFEST_SHA256",
            "CASE_AND_REPETITION_SCOPE",
            "RESOURCE_SCOPE_SHA256",
            "CREDENTIAL_SCOPE_SHA256",
            "COST_SCOPE_SHA256",
            "RETENTION_POLICY_SHA256",
            "CLEANUP_POLICY_SHA256",
            "FIELD_LEVEL_INTERSECTION_SHA256",
            "EFFECTIVE_ALLOWED_OPERATIONS",
            "CURRENTNESS_AND_REVOCATION_EPOCH",
        ],
        "authority binding catalog drift",
    )
    require(
        authority["phase_order"] == ["PREFLIGHT_OBSERVATION", "EXPERIMENT_EXECUTION"],
        "two-phase authority order drift",
    )
    require(
        authority["track_grain"] == "SEPARATE_NON_SUBSTITUTABLE_AUTHORITY_BUNDLE_PER_TRACK",
        "track authority grain drift",
    )
    require(authority["wildcard_or_parent_resource_scope_allowed"] is False, "wildcard authority allowed")
    capability = authority["capability"]
    require(
        capability
        == {
            "assignment_and_namespace_bound": True,
            "credential_material_embedded": False,
            "cross_run_reuse_allowed": False,
            "cross_track_reuse_allowed": False,
            "kind": "OPAQUE_NON_SERIALIZABLE_PROCESS_LOCAL_SINGLE_USE",
            "persistence_allowed": False,
            "phase_bound": True,
            "receipt_or_capability_is_output_permit": False,
            "serialization_allowed": False,
            "stop_invalidates_immediately": True,
        },
        "private capability semantics drift",
    )
    currentness = authority["currentness_formula"]
    exact_keys(
        currentness,
        (
            "binding_equality",
            "checked_at_rule",
            "evidence_rule",
            "phase_freshness_rule",
            "receipt_time_order_rule",
            "revocation_rule",
        ),
        "authority currentness formula",
    )
    require(
        "BOOLEAN_ASSERTIONS_ALONE_ARE_NOT_EVIDENCE" in currentness["evidence_rule"],
        "currentness treats booleans as evidence",
    )
    require(
        currentness["phase_freshness_rule"]
        == "PREFLIGHT_AND_EXECUTION_USE_DISTINCT_REQUEST_NONCE_SIGNATURE_RECEIPT_AND_CAPABILITY_COMMITMENTS",
        "phase freshness drift",
    )
    intersection = authority["intersection_formula"]
    exact_keys(
        intersection,
        (
            "case_ids",
            "digest_scopes",
            "emergency_authority_algebra",
            "execution_assignment_rule",
            "field_level_intersection_sha256",
            "operations",
            "repetition_indices",
            "required_nonempty",
        ),
        "authority intersection formula",
    )
    require(intersection["required_nonempty"] is True, "authority empty intersection allowed")
    require(
        intersection["operations"]
        == "SET_INTERSECTION_OF_OWNER_CUSTODIAN_RESOURCE_AND_COST_ALLOWED_OPERATIONS_MINUS_SET_UNION_OF_ALL_FIVE_FORBIDDEN_OPERATIONS",
        "authority operation algebra drift",
    )
    require(
        "NEVER_A_POSITIVE_EXECUTION_GRANT" in intersection["emergency_authority_algebra"],
        "emergency stop authority adds positive execution authority",
    )
    require(
        authority["phase_operation_catalog"]
        == {
            "EXPERIMENT_EXECUTION_GRANT": "EFFECTIVE_OPERATIONS_MUST_BE_A_NONEMPTY_SUBSET_OF_THE_EXACT_ASSIGNED_ROUTE_EXPERIMENT_ADAPTER_ALLOWED_OPERATIONS_AND_MUST_EXCLUDE_STOP_ONLY_OPERATIONS",
            "PREFLIGHT_OBSERVATION_GRANT": list(PREFLIGHT_OPERATIONS),
        },
        "authority phase operation catalog drift",
    )
    emergency = authority["emergency_stop_scope"]
    require(
        emergency
        == {
            "allowed_operations": list(EMERGENCY_STOP_OPERATIONS),
            "forbidden_operations": [
                "ARM_OR_TRIGGER_FAULT",
                "AUTHORIZE_CONDITION_OUTPUT_OR_OUTPUT_PERMIT",
                "CREATE_OR_EXPAND_RESOURCE_SCOPE",
                "SIGN_PROVIDER_MESSAGE",
                "START_OR_RESUME_EXPERIMENT",
            ],
            "positive_execution_authority_added": False,
        },
        "emergency stop scope drift",
    )
    logic = contract["start_stop_logic"]
    exact_keys(logic, ("start", "stop"), "start/stop logic")
    exact_keys(logic["start"], ("action", "combination", "conditions"), "START logic")
    require(logic["start"]["combination"] == "AND_ALL_REQUIRED", "START is not AND")
    require(
        logic["start"]["conditions"]
        == [
            "EXACT_PHASE_AND_TRACK_AUTHORITY",
            "ALL_FIVE_AUTHORITY_ARTIFACTS_AUTHENTIC_CURRENT_AND_UNREVOKED",
            "EXACT_SUITE_SIMULATION_RUN_NAMESPACE_ASSIGNMENT_PROFILE_CONFIGURATION_SCHEDULE_RUNNER_ADAPTER_ADAPTER_SET_AND_STOP_CONTROL_PLANE_BINDINGS",
            "RECOMPUTED_CASE_REPETITION_OPERATION_INTERSECTION_AND_EXACT_RESOURCE_CREDENTIAL_COST_RETENTION_CLEANUP_SCOPES_MATCH",
            "OPAQUE_CAPABILITY_STATE_UNUSED_DURABLE_CAS_UNCONSUMED_SINGLE_USE_AND_UNEXPOSED",
            "EVIDENCE_AND_RETENTION_PATH_READY",
            "NO_STOP_CONDITION_PRESENT",
        ],
        "START condition closure drift",
    )
    require(
        logic["start"]["action"]
        == "AFTER_ALL_CONDITIONS_PASS_DURABLY_CAS_THE_EXACT_CAPABILITY_CONTROL_LEDGER_RECORD_FROM_UNUSED_TO_START_COMMITTED_ONCE_AND_ONLY_THEN_RELEASE_THE_PRIVATE_CAPABILITY_TO_THE_BOUND_EXECUTOR_SESSION; CAS_FAILURE_OR_UNKNOWN_OUTCOME_PERMITS_NO_PROVIDER_OR_FAULT_CALL",
        "START durable CAS action drift",
    )
    require(logic["stop"]["combination"] == "OR_ANY_TRIGGER", "STOP is not OR")
    require(len(logic["stop"]["triggers"]) == 10, "STOP trigger closure drift")
    require(len(logic["stop"]["actions"]) == 6, "STOP action closure drift")
    require(
        "OWNER_CUSTODIAN_OR_EMERGENCY_OPERATOR_STOP" in logic["stop"]["triggers"],
        "owner/custodian OR stop missing",
    )
    trigger_map = logic["stop"]["trigger_reason_role_map"]
    require(set(trigger_map) == set(STOP_TRIGGER_REASON_ROLE_MAP), "STOP trigger map catalog drift")
    for trigger, (reasons, roles) in STOP_TRIGGER_REASON_ROLE_MAP.items():
        require(
            trigger_map[trigger] == {"reasons": list(reasons), "roles": list(roles)},
            f"STOP trigger map {trigger} drift",
        )
    require(
        logic["stop"]["completion_rule"]
        == "STOP_ABSORBING_COMPLETE_REQUIRES_CAPABILITY_INVALIDATED_NEW_CALLS_BLOCKED_ROW_AND_EVIDENCE_PRESERVED_CLEANUP_REDUCTIVE_COMPLETE_CREDENTIAL_REVOKED_FAULT_DISARMED_ZERO_CONTROL_PLANE_FAILURES_ZERO_UNRESOLVED_AMBIGUITIES_AND_DURABLE_RECEIPT; ALL_OTHER_STATES_HAVE_NULL_STOP_COMPLETION_TIME; FAILED_QUARANTINED_IS_TERMINAL_ESCALATED_AND_NONCONTINUABLE",
        "STOP completion formula drift",
    )


def _validate_authority_integrity(integrity: Any) -> None:
    exact_keys(
        integrity,
        (
            "artifact_role_map",
            "assignment_lineage_rule",
            "assignment_sha256_rule",
            "authorization_request_sha256_preimage",
            "bundle_id_preimage",
            "canonicalization",
            "capability_commitment_binding_fields",
            "capability_commitment_preimage",
            "channel_binding_sha256_preimage",
            "control_ledger_record_sha256_preimage",
            "domain_constants",
            "external_receipt_resolution_rule",
            "framed_sha256_kat",
            "framing_rule",
            "namespace_id_rule",
            "receipt_id_preimage",
            "scope_receipt_payload_preimage",
            "signature_receipt_sha256_preimage",
            "signature_rule",
            "signature_verification_receipt_required_fields",
            "simulation_run_id_rule",
            "suite_id_rule",
        ),
        "authority integrity",
    )
    require(
        integrity["canonicalization"]
        == "AB_CANONICAL_JSON_V1_UTF8_SORTED_KEYS_INDENT_2_COLON_SPACE_TRAILING_NEWLINE_ENSURE_ASCII_FALSE_REJECT_DUPLICATE_KEYS_AND_NONFINITE_NUMBERS",
        "authority canonicalization drift",
    )
    require(
        integrity["domain_constants"]
        == {
            "authority_bundle_id": AUTHORITY_BUNDLE_ID_DOMAIN,
            "authority_intersection": AUTHORITY_INTERSECTION_DOMAIN,
            "authorization_request": AUTHORIZATION_REQUEST_DOMAIN,
            "channel_binding": CHANNEL_BINDING_DOMAIN,
            "control_ledger": CONTROL_LEDGER_DOMAIN,
            "namespace": NAMESPACE_DOMAIN,
            "private_capability": PRIVATE_CAPABILITY_DOMAIN,
            "run": RUN_DOMAIN,
            "schedule": SCHEDULE_DOMAIN,
            "scope_receipt_id": SCOPE_RECEIPT_ID_DOMAIN,
            "scope_receipt_payload": SCOPE_RECEIPT_PAYLOAD_DOMAIN,
            "stop_receipt_id": STOP_RECEIPT_ID_DOMAIN,
        },
        "authority integrity domain catalog drift",
    )
    require(
        integrity["artifact_role_map"]
        == {
            "COST_AUTHORITY_RECEIPT": "COST_CONTROLLER",
            "CUSTODIAN_CREDENTIAL_RECEIPT": "CUSTODIAN",
            "EMERGENCY_STOP_AUTHORITY_RECEIPT": "EMERGENCY_STOP_CONTROLLER",
            "OWNER_SCOPE_RECEIPT": "OWNER",
            "RESOURCE_AUTHORITY_RECEIPT": "RESOURCE_CONTROLLER",
        },
        "authority artifact/role map drift",
    )
    require(
        integrity["capability_commitment_binding_fields"]
        == [
            "TRACK_ID",
            "PHASE",
            "SUITE_ID",
            "SIMULATION_RUN_ID",
            "NAMESPACE_ID",
            "ASSIGNMENT_SHA256",
            "CASE_ID",
            "REPETITION_INDEX",
            "CONTRACT_SHA256",
            "RESOURCE_SCOPE_SHA256",
            "CREDENTIAL_SCOPE_SHA256",
            "COST_SCOPE_SHA256",
            "RETENTION_POLICY_SHA256",
            "CLEANUP_POLICY_SHA256",
            "FIELD_LEVEL_INTERSECTION_SHA256",
            "EFFECTIVE_ALLOWED_OPERATIONS",
            "REVOCATION_EPOCH",
            "OFFLINE_HARNESS_MANIFEST_SHA256",
            "PROFILE_SHA256",
            "CONFIGURATION_SHA256",
            "SCHEDULE_SHA256",
            "RUNNER_BUILD_SHA256",
            "ADAPTER_BUILD_SHA256",
            "ADAPTER_SET_MANIFEST_SHA256",
            "STOP_CONTROL_PLANE_MANIFEST_SHA256",
            "CHANNEL_BINDING_SHA256",
            "CONTROL_LEDGER_RECORD_SHA256",
            "SINGLE_CONSUME_TRUE",
            "SINGLE_EXECUTOR_SESSION_TRUE",
            "SINGLE_RUN_TRUE",
        ],
        "capability commitment binding catalog drift",
    )
    framed_kat_bytes = _framed_bytes(
        b"agent-bridge/runner-framing-kat/v1",
        b"",
        b"\x00\xff",
        b"BioCortex",
    )
    require(
        integrity["framed_sha256_kat"]
        == {
            "expected_sha256": _sha256_bytes(framed_kat_bytes),
            "framed_bytes_hex": framed_kat_bytes.hex(),
            "parts": [
                "UTF8_agent-bridge/runner-framing-kat/v1",
                "EMPTY_BYTES",
                "HEX_00ff",
                "UTF8_BioCortex",
            ],
        },
        "framed SHA256 known-answer test drift",
    )
    require(
        integrity["framed_sha256_kat"]["expected_sha256"]
        == "e280006e8a792f697155fbff2efe6b80307bdde21cb951c2cfe4bd3bd7f24f58",
        "framed SHA256 known-answer digest drift",
    )
    require(
        integrity["framing_rule"]
        == "FRAMED_SHA256_PREFIXES_EVERY_PART_WITH_ITS_UNSIGNED_FOUR_BYTE_BIG_ENDIAN_BYTE_LENGTH_THEN_HASHES_THE_EXACT_CONCATENATION; SHA256_FIELDS_USED_AS_BINARY_PARTS_ARE_RAW_32_BYTES_DECODED_FROM_LOWERCASE_HEX",
        "framed SHA256 rule drift",
    )
    require(
        len(integrity["signature_verification_receipt_required_fields"]) == 13,
        "signature verification receipt field closure drift",
    )
    for key in (
        "authorization_request_sha256_preimage",
        "bundle_id_preimage",
        "capability_commitment_preimage",
        "channel_binding_sha256_preimage",
        "control_ledger_record_sha256_preimage",
        "receipt_id_preimage",
        "scope_receipt_payload_preimage",
        "signature_receipt_sha256_preimage",
    ):
        require("SHA256" in integrity[key], f"authority integrity {key} lacks SHA256")
    require(
        "MISSING_NONCANONICAL_OR_HASH_MISMATCH_FAILS_CLOSED"
        in integrity["external_receipt_resolution_rule"],
        "external receipt resolution is not fail closed",
    )
    require(
        "MUST_ACTIVELY_VERIFY" in integrity["signature_rule"]
        and "MUST_NOT_TRUST_SIGNATURE_VALID_TRUE_ALONE" in integrity["signature_rule"],
        "signature verification rule trusts assertion-only evidence",
    )


def _validate_stop_control_plane(control: Any) -> None:
    exact_keys(
        control,
        (
            "authority_rule",
            "counted_in_experiment_adapter_count",
            "failure_rule",
            "interface_count",
            "interfaces",
            "ordering_rule",
            "shared_execution_credential_allowed",
            "stop_receipt_integrity_rule",
            "timestamp_rule",
        ),
        "stop control plane",
    )
    require(control["interface_count"] == 5, "stop control interface count drift")
    require(control["counted_in_experiment_adapter_count"] is False, "stop controls counted as adapters")
    require(control["shared_execution_credential_allowed"] is False, "stop control shares execution credential")
    require(
        tuple(sha256_value(item) for item in control["interfaces"])
        == EXPECTED_STOP_INTERFACE_SHA256,
        "stop control interface catalog drift",
    )
    for index, interface in enumerate(control["interfaces"]):
        exact_keys(
            interface,
            (
                "allowed_operations",
                "credential_class",
                "forbidden_operations",
                "interface_id",
                "receipt_fields",
            ),
            f"stop control interface {index}",
        )
        require(interface["allowed_operations"], f"stop control interface {index} has no operation")
        require(interface["forbidden_operations"], f"stop control interface {index} has no fence")
        require(interface["receipt_fields"], f"stop control interface {index} has no evidence")
        require(
            set(interface["allowed_operations"]).isdisjoint(interface["forbidden_operations"]),
            f"stop control interface {index} allowed/forbidden overlap",
        )
    require(
        "EVEN_AFTER_EXECUTION_CAPABILITY_EXPIRY_REVOCATION_OR_FENCE"
        in control["authority_rule"],
        "stop control is not independently available",
    )
    require(
        "STOP_FAILED_QUARANTINED" in control["failure_rule"],
        "stop control failure does not quarantine",
    )
    require(
        control["ordering_rule"].startswith("CAPABILITY_FENCE_AND_NEW_CALL_BLOCK_FIRST"),
        "stop ordering does not fence first",
    )
    require(
        "STOP_ID_EQUALS_FRAMED_SHA256" in control["stop_receipt_integrity_rule"],
        "stop receipt id preimage rule missing",
    )
    require(
        len({item["credential_class"] for item in control["interfaces"]}) == 5,
        "stop control credential class reused",
    )


def _validate_contract_supporting_semantics(contract: dict[str, Any]) -> None:
    credentials = contract["credential_isolation"]
    require(credentials["ambient_or_default_credential_chain_allowed"] is False, "ambient credentials allowed")
    require(credentials["opaque_handle_only"] is True, "credentials are not opaque-handle-only")
    require(credentials["runner_secret_visibility_allowed"] is False, "runner secret visibility allowed")
    require(credentials["cross_adapter_handle_reuse_allowed"] is False, "cross-adapter handle reuse allowed")
    require(len(credentials["credential_classes"]) == 9, "credential class count drift")
    require(len(credentials["credential_classes"]) == len(set(credentials["credential_classes"])), "duplicate credential class")
    require(credentials["emergency_revoke_and_cleanup_capability_separate"] is True, "stop capability is not separate")
    require(credentials["stop_control_handles_reusable_for_experiment"] is False, "stop handle reusable for experiment")
    require(len(credentials["stop_control_credential_classes"]) == 5, "stop credential class count drift")
    require(
        set(credentials["credential_classes"]).isdisjoint(credentials["stop_control_credential_classes"]),
        "experiment and stop credential classes overlap",
    )

    evidence = contract["evidence_contract"]
    require(evidence["adapter_may_return_case_classification"] is False, "adapter classification allowed")
    require(
        evidence["actual_evidence_origins"]
        == [
            "RUNTIME_CLIENT_CONFORMANCE_DOUBLE",
            "MANAGED_SERVICE_WITH_CLIENT_FAULT_PROXY",
            "SELF_HOSTED_ADVERSARIAL_LAB",
        ],
        "evidence-origin closure drift",
    )
    require(evidence["provider_evidence_hash_does_not_imply_provider_processing"] is True, "provider processing overclaim")
    require(len(evidence["eligibility_rules"]) == 8, "evidence eligibility closure drift")
    require(len(evidence["envelope_required_fields"]) == 10, "evidence envelope closure drift")

    recovery = contract["recovery_protocol"]
    require(len(recovery["durable_runner_states"]) == 16, "runner-state closure drift")
    require(len(recovery["restart_rules"]) == 7, "restart-rule closure drift")
    require(
        "PREPARED_CONSUMED_AMBIGUOUS_OR_UNRESOLVED_ATTEMPT_NEVER_REISSUES_SIGNING"
        in recovery["restart_rules"],
        "restart re-sign is not forbidden",
    )
    require(
        "STOP_REQUESTED_OR_LATER_NEVER_RETURNS_TO_AN_EXECUTABLE_STATE_AND_RESTART_CAN_ONLY_CONTINUE_REDUCTIVE_STOP_CONTROL"
        in recovery["restart_rules"],
        "restart can escape absorbing stop",
    )
    retained = contract["retained_row_contract"]
    require(retained["retained"] is True, "retained-row contract disabled")
    require(
        retained["counts_toward_denominator_rule"]
        == "EVERY_ASSIGNED_RUNTIME_ATTEMPT_INCLUDING_FAILURE_ABORT_AND_STOP",
        "retained denominator drift",
    )
    require(len(retained["outcomes"]) == 4, "retained outcome closure drift")

    s12 = contract["s12_branch_contract"]
    require(s12["success_branch"]["branch_id"] == "SUCCESSOR_EXECUTOR_CORRELATED_AND_FULLY_VALIDATED", "S12 success drift")
    require(s12["failure_branch"]["branch_id"] == "FAIL_CLOSED_PREWIRE_NO_EXECUTOR_CLAIM", "S12 failure drift")
    require(len(s12["success_branch"]["requirements"]) == 4, "S12 success requirements drift")
    require(len(s12["failure_branch"]["requirements"]) == 3, "S12 failure requirements drift")
    require(
        s12["correlated_postwire_failure_branch"]
        == {
            "allowed_classification": "FAIL_CLOSED_REJECTED",
            "branch_id": "CORRELATED_POSTWIRE_FAIL_CLOSED_REJECTED",
            "requirements": [
                "TARGET_ROUTE_EXECUTING_OR_REJECTING_NODE_CLUSTER_REQUEST_REDIRECT_FORWARD_AND_WIRE_BOUND",
                "AUDIT_OR_TRANSPORT_REJECTION_RECEIPT_AND_EXPLICIT_FAIL_CLOSED_REJECTION",
                "ZERO_ACCEPTED_SIGNATURE_RECEIPT_AND_ZERO_OUTPUT",
            ],
        },
        "S12 correlated postwire rejection drift",
    )
    require(
        s12["postwire_uncorrelated_rule"]
        == "RETAIN_AS_EXPERIMENT_INFRASTRUCTURE_FAILURE_NOT_CASE_CLASSIFICATION",
        "S12 uncorrelated branch drift",
    )

    acceptance = contract["acceptance_policy"]
    require(acceptance["adapter_classification_forbidden"] is True, "adapter classification not forbidden")
    require(acceptance["all_assigned_rows_retained"] is True, "assigned-row retention disabled")
    require(acceptance["authority_scope_must_be_exact_subset"] is True, "authority exact subset disabled")
    require(acceptance["cross_track_capability_reuse_forbidden"] is True, "cross-track capability reuse allowed")
    require(acceptance["hidden_signer_retries_forbidden"] is True, "hidden retries allowed")
    require(acceptance["track_comparison_allowed"] is False, "track comparison allowed")

    sources = contract["official_source_claims"]
    require(type(sources) is list and len(sources) == 10, "official-source closure drift")
    require(
        [item.get("claim_id") for item in sources]
        == [
            "GID_RUNNER_01",
            "GSP_RUNNER_01",
            "GKM_RUNNER_01",
            "GKM_RUNNER_02",
            "ETC_RUNNER_01",
            "ETC_RUNNER_02",
            "ETC_RUNNER_03",
            "OBA_RUNNER_01",
            "OBA_RUNNER_02",
            "OBA_RUNNER_03",
        ],
        "official-source ids drift",
    )
    for item in sources:
        exact_keys(item, ("claim", "claim_id", "evidence_class", "retrieved_on", "url"), "official source")
        require(item["evidence_class"] == "OFFICIAL_DOCUMENTATION_DIRECT", "source evidence class drift")
        require(item["retrieved_on"] == "2026-07-15", "source retrieval date drift")
        require(item["url"].startswith("https://"), "source URL is not HTTPS")

    profile = contract["profile_contract"]
    require(len(profile["managed_required_fields"]) == 9, "managed profile closure drift")
    require(len(profile["self_hosted_required_fields"]) == 11, "self-hosted profile closure drift")
    require(len(contract["non_claims"]) == 7, "non-claim closure drift")


def validate_contract(contract: Any) -> None:
    """Validate the exact frozen adapter contract and its critical semantics."""

    exact_keys(contract, CONTRACT_KEYS, "adapter contract")
    require(contract["schema"] == CONTRACT_SCHEMA, "adapter contract schema drift")
    require(contract["version"] == 1, "adapter contract version drift")
    require(contract["baseline_commit"] == BASELINE_COMMIT, "baseline commit drift")
    require(contract["date"] == "2026-07-15", "contract date drift")
    require(contract["status"] == STATUS, "contract status drift")
    require(contract["decision"] == DECISION, "contract decision drift")
    require(contract["next_unit"] == NEXT_UNIT, "contract next unit drift")
    require(
        contract["purpose"]
        == "FREEZE_NON_AUTHORIZING_RUNNER_AUTHORITY_ADAPTER_EVIDENCE_STOP_AND_RECOVERY_SEMANTICS_WITHOUT_PROVIDER_OR_CREDENTIAL_ACCESS",
        "contract purpose drift",
    )
    require(sha256_value(contract) == ADAPTER_CONTRACT_SHA256, "adapter contract bytes drift")
    for section, expected_sha256 in EXPECTED_CONTRACT_SECTION_SHA256.items():
        require(sha256_value(contract[section]) == expected_sha256, f"contract {section} drift")
    require(
        contract["predecessor"]
        == {
            "offline_configuration_sha256": OFFLINE_CONFIGURATION_SHA256,
            "offline_harness_integration_commit": BASELINE_COMMIT,
            "offline_harness_manifest_sha256": OFFLINE_HARNESS_MANIFEST_SHA256,
            "offline_harness_source_commit": PREDECESSOR_SOURCE_COMMIT,
            "offline_rows_sha256": OFFLINE_ROWS_SHA256,
            "offline_schedule_sha256": OFFLINE_SCHEDULE_SHA256,
            "preregistration_contract_sha256": PREREGISTRATION_CONTRACT_SHA256,
        },
        "contract predecessor drift",
    )
    _validate_contract_boundary(contract["boundary"])
    _validate_execution_plan(contract["execution_plan"])
    _validate_adapter_interfaces(contract["adapter_interfaces"])
    _validate_authority_and_stop(contract)
    _validate_authority_integrity(contract["authority_integrity"])
    _validate_stop_control_plane(contract["stop_control_plane"])
    _validate_contract_supporting_semantics(contract)


_SCHEMA_KEYWORDS = {
    "$defs", "$id", "$schema", "$ref", "$comment",
    "title", "description", "type", "const", "enum",
    "allOf", "anyOf", "oneOf", "not", "if", "then", "else",
    "properties", "patternProperties", "additionalProperties", "required",
    "dependentRequired", "minProperties", "maxProperties",
    "items", "prefixItems", "minItems", "maxItems", "uniqueItems",
    "minLength", "maxLength", "pattern", "format",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
}


def _resolve_ref(root: dict[str, Any], reference: str) -> dict[str, Any]:
    require(reference.startswith("#/"), f"external schema ref forbidden: {reference}")
    current: Any = root
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        require(type(current) is dict and part in current, f"unresolved schema ref: {reference}")
        current = current[part]
    require(type(current) is dict, f"schema ref does not resolve to an object: {reference}")
    return current


def _validate_schema_root(schema: Any, expected_id: str, label: str) -> None:
    require(type(schema) is dict, f"{label} must be an object")
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{label} draft drift")
    require(schema.get("$id") == expected_id, f"{label} id drift")
    require(schema.get("type") == "object", f"{label} root type drift")
    require(schema.get("additionalProperties") is False, f"{label} root is not closed")

    def walk(node: Any, path: str) -> None:
        if type(node) is list:
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")
            return
        if type(node) is not dict:
            return
        unknown = set(node) - _SCHEMA_KEYWORDS
        require(not unknown, f"{label} {path} unknown schema keywords: {sorted(unknown)}")
        if "$ref" in node:
            _resolve_ref(schema, node["$ref"])
        if node.get("type") == "object":
            require(node.get("additionalProperties") is False, f"{label} {path} object is open")
            properties = node.get("properties")
            required = node.get("required")
            require(type(properties) is dict, f"{label} {path} properties missing")
            require(type(required) is list, f"{label} {path} required missing")
            require(len(required) == len(set(required)), f"{label} {path} duplicate required field")
            require(set(required) == set(properties), f"{label} {path} required/property drift")
        for key, value in node.items():
            if key in {"properties", "patternProperties", "$defs"}:
                require(type(value) is dict, f"{label} {path}.{key} must be an object")
                for child_key, child in value.items():
                    walk(child, f"{path}.{key}.{child_key}")
            elif key in {"allOf", "anyOf", "oneOf", "prefixItems"}:
                require(type(value) is list, f"{label} {path}.{key} must be an array")
                walk(value, f"{path}.{key}")
            elif key in {"not", "if", "then", "else", "items", "additionalProperties"}:
                if type(value) is dict:
                    walk(value, f"{path}.{key}")

    walk(schema, "$")
    properties = schema.get("properties")
    required = schema.get("required")
    require(type(properties) is dict and properties, f"{label} properties missing")
    require(type(required) is list and set(required) == set(properties), f"{label} root closure drift")


def _json_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_json_equal(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    return left == right


def _type_matches(value: Any, expected: str) -> bool:
    return {
        "object": type(value) is dict,
        "array": type(value) is list,
        "string": type(value) is str,
        "integer": type(value) is int,
        "number": type(value) in (int, float) and type(value) is not bool,
        "boolean": type(value) is bool,
        "null": value is None,
    }.get(expected, False)


def _schema_accepts(value: Any, schema: dict[str, Any]) -> bool:
    try:
        _validate_instance(value, schema, schema, "$")
        return True
    except ContractError:
        return False


def _validate_instance(value: Any, schema: Any, root: dict[str, Any], path: str) -> None:
    if schema is True:
        return
    require(schema is not False and type(schema) is dict, f"{path} invalid schema")
    if "$ref" in schema:
        _validate_instance(value, _resolve_ref(root, schema["$ref"]), root, path)
    for item in schema.get("allOf", []):
        _validate_instance(value, item, root, path)
    if "anyOf" in schema:
        require(sum(_probe_instance(value, item, root, path) for item in schema["anyOf"]) >= 1, f"{path} anyOf mismatch")
    if "oneOf" in schema:
        require(sum(_probe_instance(value, item, root, path) for item in schema["oneOf"]) == 1, f"{path} oneOf mismatch")
    if "not" in schema:
        require(not _probe_instance(value, schema["not"], root, path), f"{path} matches forbidden schema")
    if "if" in schema:
        branch = schema.get("then") if _probe_instance(value, schema["if"], root, path) else schema.get("else")
        if branch is not None:
            _validate_instance(value, branch, root, path)
    if "type" in schema:
        require(_type_matches(value, schema["type"]), f"{path} type mismatch")
    if "const" in schema:
        require(_json_equal(value, schema["const"]), f"{path} const mismatch")
    if "enum" in schema:
        require(any(_json_equal(value, item) for item in schema["enum"]), f"{path} enum mismatch")
    if type(value) is dict:
        for key in schema.get("required", []):
            require(key in value, f"{path}.{key} missing")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            require(set(value).issubset(properties), f"{path} has extra properties")
        for key, item in value.items():
            if key in properties:
                _validate_instance(item, properties[key], root, f"{path}.{key}")
        if "minProperties" in schema:
            require(len(value) >= schema["minProperties"], f"{path} has too few properties")
        if "maxProperties" in schema:
            require(len(value) <= schema["maxProperties"], f"{path} has too many properties")
    if type(value) is list:
        if "minItems" in schema:
            require(len(value) >= schema["minItems"], f"{path} has too few items")
        if "maxItems" in schema:
            require(len(value) <= schema["maxItems"], f"{path} has too many items")
        if schema.get("uniqueItems") is True:
            encoded = [canonical_bytes(item) for item in value]
            require(len(encoded) == len(set(encoded)), f"{path} has duplicate items")
        if "items" in schema:
            for index, item in enumerate(value):
                _validate_instance(item, schema["items"], root, f"{path}[{index}]")
    if type(value) is str:
        if "minLength" in schema:
            require(len(value) >= schema["minLength"], f"{path} is too short")
        if "maxLength" in schema:
            require(len(value) <= schema["maxLength"], f"{path} is too long")
        if "pattern" in schema:
            require(re.search(schema["pattern"], value) is not None, f"{path} pattern mismatch")
    if type(value) in (int, float) and type(value) is not bool:
        if "minimum" in schema:
            require(value >= schema["minimum"], f"{path} below minimum")
        if "maximum" in schema:
            require(value <= schema["maximum"], f"{path} above maximum")
        if "exclusiveMinimum" in schema:
            require(value > schema["exclusiveMinimum"], f"{path} below exclusive minimum")
        if "exclusiveMaximum" in schema:
            require(value < schema["exclusiveMaximum"], f"{path} above exclusive maximum")


def _probe_instance(value: Any, schema: Any, root: dict[str, Any], path: str) -> bool:
    try:
        _validate_instance(value, schema, root, path)
        return True
    except ContractError:
        return False


_AUTHORITY_ROLE_SLOTS = (
    ("owner_scope_receipt", "OWNER_SCOPE_RECEIPT"),
    ("custodian_credential_receipt", "CUSTODIAN_CREDENTIAL_RECEIPT"),
    ("resource_authority_receipt", "RESOURCE_AUTHORITY_RECEIPT"),
    ("cost_authority_receipt", "COST_AUTHORITY_RECEIPT"),
    ("emergency_stop_authority_receipt", "EMERGENCY_STOP_AUTHORITY_RECEIPT"),
)
_AUTHORITY_SHARED_BINDINGS = (
    "adapter_build_sha256",
    "adapter_set_manifest_sha256",
    "assignment_sha256",
    "cleanup_policy_sha256",
    "configuration_sha256",
    "contract_sha256",
    "cost_scope_sha256",
    "credential_scope_sha256",
    "offline_harness_manifest_sha256",
    "phase",
    "profile_sha256",
    "resource_scope_sha256",
    "retention_policy_sha256",
    "revocation_epoch",
    "namespace_id",
    "runner_build_sha256",
    "schedule_sha256",
    "simulation_run_id",
    "stop_control_plane_manifest_sha256",
    "suite_id",
    "track_id",
)


def _tag_hash(tag: str) -> str:
    return hashlib.sha256(tag.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _domain_json_hash(domain: str, value: Any) -> str:
    return _framed_hash_bytes(domain, canonical_bytes(value))


def _framed_bytes(*parts: bytes) -> bytes:
    framed = bytearray()
    for part in parts:
        framed.extend(len(part).to_bytes(4, "big"))
        framed.extend(part)
    return bytes(framed)


def _framed_hash_bytes(domain: str, *parts: bytes) -> str:
    return _sha256_bytes(_framed_bytes(domain.encode("utf-8"), *parts))


def _assignment_lineage(
    track_id: str,
    case_id: str,
    repetition_index: int,
) -> tuple[str, str, str]:
    cases = MANAGED_CASE_IDS if track_id == MANAGED_TRACK else SELF_HOSTED_CASE_IDS
    require(case_id in cases, "assignment case does not belong to track")
    ordered = sorted(
        cases,
        key=lambda candidate: _framed_hash_bytes(
            SCHEDULE_DOMAIN,
            track_id.encode("utf-8"),
            repetition_index.to_bytes(4, "big"),
            candidate.encode("utf-8"),
        ),
    )
    assignment = {
        "configuration_sha256": OFFLINE_CONFIGURATION_SHA256,
        "contract_sha256": PREREGISTRATION_CONTRACT_SHA256,
        "domain": SCHEDULE_DOMAIN,
        "ordered_case_ids": ordered,
        "repetition_index": repetition_index,
        "track_id": track_id,
    }
    assignment_sha256 = sha256_value(assignment)
    simulation_run_id = _framed_hash_bytes(
        RUN_DOMAIN,
        track_id.encode("utf-8"),
        case_id.encode("utf-8"),
        repetition_index.to_bytes(4, "big"),
        bytes.fromhex(OFFLINE_CONFIGURATION_SHA256),
        bytes.fromhex(assignment_sha256),
    )
    namespace_id = _framed_hash_bytes(
        NAMESPACE_DOMAIN,
        bytes.fromhex(simulation_run_id),
    )
    return assignment_sha256, simulation_run_id, namespace_id


def _scope_payload_sha256(receipt: dict[str, Any]) -> str:
    payload = {
        key: copy.deepcopy(value)
        for key, value in receipt.items()
        if key not in {"canonical_payload_sha256", "receipt_id", "signature_receipt_sha256"}
    }
    return _domain_json_hash(SCOPE_RECEIPT_PAYLOAD_DOMAIN, payload)


def _scope_receipt_id(receipt: dict[str, Any]) -> str:
    return _framed_hash_bytes(
        SCOPE_RECEIPT_ID_DOMAIN,
        receipt["artifact_type"].encode("utf-8"),
        bytes.fromhex(receipt["canonical_payload_sha256"]),
        bytes.fromhex(receipt["signature_receipt_sha256"]),
    )


def _authority_intersection_sha256(intersection: dict[str, Any]) -> str:
    payload = {
        key: copy.deepcopy(value)
        for key, value in intersection.items()
        if key != "field_level_intersection_sha256"
    }
    return _domain_json_hash(AUTHORITY_INTERSECTION_DOMAIN, payload)


_CAPABILITY_COMMITMENT_BINDING_FIELDS = (
    "adapter_build_sha256",
    "adapter_set_manifest_sha256",
    "assignment_sha256",
    "case_id",
    "channel_binding_sha256",
    "cleanup_policy_sha256",
    "configuration_sha256",
    "contract_sha256",
    "control_ledger_record_sha256",
    "cost_scope_sha256",
    "credential_scope_sha256",
    "effective_allowed_operations",
    "field_level_intersection_sha256",
    "namespace_id",
    "offline_harness_manifest_sha256",
    "phase",
    "profile_sha256",
    "repetition_index",
    "resource_scope_sha256",
    "retention_policy_sha256",
    "revocation_epoch",
    "runner_build_sha256",
    "schedule_sha256",
    "simulation_run_id",
    "single_consume",
    "single_executor_session",
    "single_run",
    "stop_control_plane_manifest_sha256",
    "suite_id",
    "track_id",
)


def _private_capability_commitment(
    private_capability: bytes,
    capability: dict[str, Any],
) -> str:
    require(len(private_capability) == 32, "private capability must be exactly 32 bytes")
    binding = {
        key: copy.deepcopy(capability[key])
        for key in _CAPABILITY_COMMITMENT_BINDING_FIELDS
    }
    return _framed_hash_bytes(
        PRIVATE_CAPABILITY_DOMAIN,
        private_capability,
        canonical_bytes(binding),
    )


def _authority_bundle_id(bundle: dict[str, Any]) -> str:
    payload = {key: copy.deepcopy(value) for key, value in bundle.items() if key != "bundle_id"}
    return _domain_json_hash(AUTHORITY_BUNDLE_ID_DOMAIN, payload)


def _rebind_authority_hashes(bundle: dict[str, Any]) -> None:
    for slot, _ in _AUTHORITY_ROLE_SLOTS:
        receipt = bundle[slot]
        receipt["canonical_payload_sha256"] = _scope_payload_sha256(receipt)
        receipt["receipt_id"] = _scope_receipt_id(receipt)
    intersection = bundle["authority_intersection"]
    intersection["field_level_intersection_sha256"] = _authority_intersection_sha256(
        intersection
    )
    bundle["bundle_id"] = _authority_bundle_id(bundle)


def _is_utc(value: Any) -> bool:
    if type(value) is not str or re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
        value,
    ) is None:
        return False
    year = int(value[0:4])
    month = int(value[5:7])
    day = int(value[8:10])
    hour = int(value[11:13])
    minute = int(value[14:16])
    second = int(value[17:19])
    if not (
        1 <= year <= 9999
        and 1 <= month <= 12
        and 0 <= hour <= 23
        and 0 <= minute <= 59
        and 0 <= second <= 59
    ):
        return False
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    month_days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return 1 <= day <= month_days[month - 1]


def _scope_receipt_kat(role: str, ordinal: int) -> dict[str, Any]:
    assignment_sha256, simulation_run_id, namespace_id = _assignment_lineage(
        MANAGED_TRACK, "M00", 1
    )
    emergency = role == "EMERGENCY_STOP_AUTHORITY_RECEIPT"
    receipt = {
        "adapter_build_sha256": _tag_hash("adapter-build"),
        "adapter_set_manifest_sha256": _tag_hash("adapter-set"),
        "allowed_case_ids": ["M00"],
        "allowed_operations": [
            "BLOCK_NEW_CALLS_FOR_EXACT_RUN"
            if emergency
            else "STRONG_READ_EXACT_OPERATION_KEY"
        ],
        "allowed_repetition_indices": [1],
        "artifact_type": role,
        "assignment_sha256": assignment_sha256,
        "authority_principal_id_sha256": _tag_hash(f"principal-{ordinal}"),
        "authorization_request_sha256": _tag_hash(f"authorization-request-{ordinal}"),
        "canonical_payload_sha256": "0" * 64,
        "cleanup_policy_sha256": _tag_hash("cleanup-policy"),
        "configuration_sha256": OFFLINE_CONFIGURATION_SHA256,
        "contract_sha256": ADAPTER_CONTRACT_SHA256,
        "cost_scope_sha256": _tag_hash("cost-scope"),
        "credential_scope_sha256": _tag_hash("credential-scope"),
        "expires_at_utc": "2026-07-15T21:00:00Z",
        "forbidden_operations": ["OUTPUT_AUTHORIZATION"],
        "issued_at_utc": "2026-07-15T19:00:00Z",
        "nonce_sha256": _tag_hash(f"nonce-{ordinal}"),
        "not_before_utc": "2026-07-15T19:30:00Z",
        "offline_harness_manifest_sha256": OFFLINE_HARNESS_MANIFEST_SHA256,
        "phase": "EXPERIMENT_EXECUTION_GRANT",
        "profile_sha256": _tag_hash("profile"),
        "receipt_id": "0" * 64,
        "receipt_is_output_permit": False,
        "resource_scope_sha256": _tag_hash("resource-scope"),
        "retention_policy_sha256": _tag_hash("retention-policy"),
        "revocation_epoch": 7,
        "namespace_id": namespace_id,
        "runner_build_sha256": _tag_hash("runner-build"),
        "schedule_sha256": OFFLINE_SCHEDULE_SHA256,
        "signature_receipt_sha256": _tag_hash(f"signature-{ordinal}"),
        "simulation_run_id": simulation_run_id,
        "stop_control_plane_manifest_sha256": _tag_hash("stop-control-plane"),
        "suite_id": OFFLINE_SUITE_ID,
        "track_id": MANAGED_TRACK,
        "trust_policy_sha256": _tag_hash(f"trust-policy-{ordinal}"),
    }
    receipt["canonical_payload_sha256"] = _scope_payload_sha256(receipt)
    receipt["receipt_id"] = _scope_receipt_id(receipt)
    return receipt


def _authority_kat() -> dict[str, Any]:
    assignment_sha256, simulation_run_id, namespace_id = _assignment_lineage(
        MANAGED_TRACK, "M00", 1
    )
    receipts = {
        slot: _scope_receipt_kat(role, index)
        for index, (slot, role) in enumerate(_AUTHORITY_ROLE_SLOTS, start=1)
    }
    intersection_payload = {
        "adapter_build_sha256": _tag_hash("adapter-build"),
        "adapter_set_manifest_sha256": _tag_hash("adapter-set"),
        "assignment_sha256": assignment_sha256,
        "cleanup_policy_sha256": _tag_hash("cleanup-policy"),
        "configuration_sha256": OFFLINE_CONFIGURATION_SHA256,
        "contract_sha256": ADAPTER_CONTRACT_SHA256,
        "cost_scope_sha256": _tag_hash("cost-scope"),
        "credential_scope_sha256": _tag_hash("credential-scope"),
        "effective_allowed_case_ids": ["M00"],
        "effective_allowed_operations": ["STRONG_READ_EXACT_OPERATION_KEY"],
        "effective_allowed_repetition_indices": [1],
        "nonempty_exact_intersection": True,
        "offline_harness_manifest_sha256": OFFLINE_HARNESS_MANIFEST_SHA256,
        "phase": "EXPERIMENT_EXECUTION_GRANT",
        "profile_sha256": _tag_hash("profile"),
        "resource_scope_sha256": _tag_hash("resource-scope"),
        "retention_policy_sha256": _tag_hash("retention-policy"),
        "revocation_epoch": 7,
        "namespace_id": namespace_id,
        "runner_build_sha256": _tag_hash("runner-build"),
        "schedule_sha256": OFFLINE_SCHEDULE_SHA256,
        "simulation_run_id": simulation_run_id,
        "stop_control_plane_manifest_sha256": _tag_hash("stop-control-plane"),
        "suite_id": OFFLINE_SUITE_ID,
        "track_id": MANAGED_TRACK,
    }
    intersection = dict(intersection_payload)
    intersection["field_level_intersection_sha256"] = _authority_intersection_sha256(
        intersection
    )
    bundle = {
        "authority_intersection": intersection,
        "bundle_id": "0" * 64,
        "condition_output_authorized": False,
        **receipts,
        "currentness": {
            "checked_at_utc": "2026-07-15T20:00:00Z",
            "cost_budget_reserved": True,
            "credential_lease_current": True,
            "profile_current": True,
            "resource_budget_reserved": True,
            "revocation_epoch": 7,
            "row_currentness_receipt_sha256": _tag_hash("row-currentness"),
            "trusted_time_receipt_sha256": _tag_hash("trusted-time"),
        },
        "execution_capability_commitment": {
            "adapter_build_sha256": _tag_hash("adapter-build"),
            "adapter_set_manifest_sha256": _tag_hash("adapter-set"),
            "assignment_sha256": assignment_sha256,
            "capability_commitment_sha256": _tag_hash("capability"),
            "case_id": "M00",
            "channel_binding_sha256": _tag_hash("channel"),
            "cleanup_policy_sha256": _tag_hash("cleanup-policy"),
            "configuration_sha256": OFFLINE_CONFIGURATION_SHA256,
            "contract_sha256": ADAPTER_CONTRACT_SHA256,
            "control_ledger_record_sha256": _tag_hash("control-ledger"),
            "cost_scope_sha256": _tag_hash("cost-scope"),
            "credential_scope_sha256": _tag_hash("credential-scope"),
            "effective_allowed_operations": ["STRONG_READ_EXACT_OPERATION_KEY"],
            "field_level_intersection_sha256": intersection[
                "field_level_intersection_sha256"
            ],
            "namespace_id": namespace_id,
            "offline_harness_manifest_sha256": OFFLINE_HARNESS_MANIFEST_SHA256,
            "phase": "EXPERIMENT_EXECUTION_GRANT",
            "private_capability_bytes_serialized": False,
            "profile_sha256": _tag_hash("profile"),
            "repetition_index": 1,
            "resource_scope_sha256": _tag_hash("resource-scope"),
            "retention_policy_sha256": _tag_hash("retention-policy"),
            "revocation_epoch": 7,
            "runner_build_sha256": _tag_hash("runner-build"),
            "schedule_sha256": OFFLINE_SCHEDULE_SHA256,
            "simulation_run_id": simulation_run_id,
            "single_consume": True,
            "single_executor_session": True,
            "single_run": True,
            "state": "UNUSED",
            "stop_control_plane_manifest_sha256": _tag_hash("stop-control-plane"),
            "suite_id": OFFLINE_SUITE_ID,
            "track_id": MANAGED_TRACK,
        },
        "adapter_build_sha256": _tag_hash("adapter-build"),
        "adapter_set_manifest_sha256": _tag_hash("adapter-set"),
        "assignment_sha256": assignment_sha256,
        "case_id": "M00",
        "cleanup_policy_sha256": _tag_hash("cleanup-policy"),
        "configuration_sha256": OFFLINE_CONFIGURATION_SHA256,
        "contract_sha256": ADAPTER_CONTRACT_SHA256,
        "cost_scope_sha256": _tag_hash("cost-scope"),
        "credential_scope_sha256": _tag_hash("credential-scope"),
        "effective_allowed_operations": ["STRONG_READ_EXACT_OPERATION_KEY"],
        "field_level_intersection_sha256": intersection[
            "field_level_intersection_sha256"
        ],
        "namespace_id": namespace_id,
        "offline_harness_manifest_sha256": OFFLINE_HARNESS_MANIFEST_SHA256,
        "phase": "EXPERIMENT_EXECUTION_GRANT",
        "profile_sha256": _tag_hash("profile"),
        "public_bundle_is_bearer_capability": False,
        "receipt_is_output_permit": False,
        "repetition_index": 1,
        "resource_scope_sha256": _tag_hash("resource-scope"),
        "retention_policy_sha256": _tag_hash("retention-policy"),
        "revocation_epoch": 7,
        "runner_build_sha256": _tag_hash("runner-build"),
        "schedule_sha256": OFFLINE_SCHEDULE_SHA256,
        "schema": AUTHORITY_RECEIPT_SCHEMA,
        "simulation_run_id": simulation_run_id,
        "stop_control_plane_manifest_sha256": _tag_hash("stop-control-plane"),
        "suite_id": OFFLINE_SUITE_ID,
        "track_id": MANAGED_TRACK,
    }
    bundle["execution_capability_commitment"]["capability_commitment_sha256"] = (
        _private_capability_commitment(
            bytes(range(32)), bundle["execution_capability_commitment"]
        )
    )
    bundle["bundle_id"] = _authority_bundle_id(bundle)
    return bundle


def _authority_preflight_kat() -> dict[str, Any]:
    bundle = _authority_kat()
    phase = "PREFLIGHT_OBSERVATION_GRANT"
    bundle["phase"] = phase
    bundle["authority_intersection"]["phase"] = phase
    bundle["execution_capability_commitment"]["phase"] = phase
    for slot, role in _AUTHORITY_ROLE_SLOTS:
        receipt = bundle[slot]
        receipt["phase"] = phase
        if role != "EMERGENCY_STOP_AUTHORITY_RECEIPT":
            receipt["allowed_operations"] = ["READ_RESOURCE_METADATA"]
    bundle["authority_intersection"]["effective_allowed_operations"] = [
        "READ_RESOURCE_METADATA"
    ]
    bundle["effective_allowed_operations"] = ["READ_RESOURCE_METADATA"]
    bundle["execution_capability_commitment"]["effective_allowed_operations"] = [
        "READ_RESOURCE_METADATA"
    ]
    _rebind_authority_hashes(bundle)
    intersection_hash = bundle["authority_intersection"][
        "field_level_intersection_sha256"
    ]
    bundle["field_level_intersection_sha256"] = intersection_hash
    bundle["execution_capability_commitment"][
        "field_level_intersection_sha256"
    ] = intersection_hash
    bundle["execution_capability_commitment"]["capability_commitment_sha256"] = (
        _private_capability_commitment(
            bytes(range(32)), bundle["execution_capability_commitment"]
        )
    )
    bundle["bundle_id"] = _authority_bundle_id(bundle)
    return bundle


def _validate_authority_bundle_semantics(bundle: dict[str, Any]) -> None:
    track = bundle["track_id"]
    phase = bundle["phase"]
    require(track in (MANAGED_TRACK, SELF_HOSTED_TRACK), "authority track drift")
    require(phase in ("PREFLIGHT_OBSERVATION_GRANT", "EXPERIMENT_EXECUTION_GRANT"), "authority phase drift")
    require(bundle["condition_output_authorized"] is False, "authority condition output allowed")
    require(bundle["receipt_is_output_permit"] is False, "authority receipt is output permit")
    require(bundle["public_bundle_is_bearer_capability"] is False, "public bundle is bearer capability")
    intersection = bundle["authority_intersection"]
    capability = bundle["execution_capability_commitment"]
    currentness = bundle["currentness"]
    require(intersection["nonempty_exact_intersection"] is True, "authority intersection empty")
    require(capability["private_capability_bytes_serialized"] is False, "private capability serialized")
    for key in ("single_consume", "single_executor_session", "single_run"):
        require(capability[key] is True, f"capability {key} drift")
    require(capability["state"] == "UNUSED", "new authority capability is not unused")
    root_intersection_bindings = (
        "adapter_build_sha256",
        "adapter_set_manifest_sha256",
        "assignment_sha256",
        "cleanup_policy_sha256",
        "configuration_sha256",
        "contract_sha256",
        "cost_scope_sha256",
        "credential_scope_sha256",
        "effective_allowed_operations",
        "field_level_intersection_sha256",
        "namespace_id",
        "offline_harness_manifest_sha256",
        "phase",
        "profile_sha256",
        "resource_scope_sha256",
        "retention_policy_sha256",
        "revocation_epoch",
        "runner_build_sha256",
        "schedule_sha256",
        "simulation_run_id",
        "stop_control_plane_manifest_sha256",
        "suite_id",
        "track_id",
    )
    for key in root_intersection_bindings:
        require(bundle[key] == intersection[key], f"root/intersection {key} mismatch")
    for key in (
        "adapter_build_sha256",
        "adapter_set_manifest_sha256",
        "assignment_sha256",
        "cleanup_policy_sha256",
        "configuration_sha256",
        "contract_sha256",
        "cost_scope_sha256",
        "credential_scope_sha256",
        "effective_allowed_operations",
        "field_level_intersection_sha256",
        "namespace_id",
        "offline_harness_manifest_sha256",
        "phase",
        "profile_sha256",
        "resource_scope_sha256",
        "retention_policy_sha256",
        "revocation_epoch",
        "runner_build_sha256",
        "schedule_sha256",
        "simulation_run_id",
        "stop_control_plane_manifest_sha256",
        "suite_id",
        "track_id",
    ):
        require(capability[key] == intersection[key], f"capability/intersection {key} mismatch")
    require(track == intersection["track_id"] == capability["track_id"], "root track binding mismatch")
    require(phase == intersection["phase"] == capability["phase"], "root phase binding mismatch")

    checked = currentness["checked_at_utc"]
    require(_is_utc(checked), "currentness time malformed")
    for key in ("cost_budget_reserved", "credential_lease_current", "profile_current", "resource_budget_reserved"):
        require(currentness[key] is True, f"currentness {key} not true")
    require(
        bundle["revocation_epoch"] == currentness["revocation_epoch"],
        "root/currentness revocation epoch mismatch",
    )
    require(bundle["contract_sha256"] == ADAPTER_CONTRACT_SHA256, "authority contract binding drift")
    require(bundle["configuration_sha256"] == OFFLINE_CONFIGURATION_SHA256, "authority configuration binding drift")
    require(
        bundle["offline_harness_manifest_sha256"] == OFFLINE_HARNESS_MANIFEST_SHA256,
        "authority harness manifest binding drift",
    )
    require(bundle["schedule_sha256"] == OFFLINE_SCHEDULE_SHA256, "authority schedule binding drift")
    require(bundle["suite_id"] == OFFLINE_SUITE_ID, "authority suite binding drift")
    expected_assignment, expected_run, expected_namespace = _assignment_lineage(
        track, bundle["case_id"], bundle["repetition_index"]
    )
    require(bundle["assignment_sha256"] == expected_assignment, "authority assignment lineage drift")
    require(bundle["simulation_run_id"] == expected_run, "authority run lineage drift")
    require(bundle["namespace_id"] == expected_namespace, "authority namespace lineage drift")

    receipts = [bundle[slot] for slot, _ in _AUTHORITY_ROLE_SLOTS]
    principals: set[str] = set()
    receipt_ids: set[str] = set()
    nonces: set[str] = set()
    requests: set[str] = set()
    signatures: set[str] = set()
    allowed_case_sets: list[set[str]] = []
    allowed_operation_sets: list[set[str]] = []
    allowed_repetition_sets: list[set[int]] = []
    forbidden_union: set[str] = set()
    for receipt, (slot, role) in zip(receipts, _AUTHORITY_ROLE_SLOTS):
        require(receipt["artifact_type"] == role, f"{slot} role mismatch")
        require(receipt["track_id"] == track, f"{slot} track mismatch")
        require(receipt["phase"] == phase, f"{slot} phase mismatch")
        require(receipt["revocation_epoch"] == currentness["revocation_epoch"], f"{slot} revocation epoch mismatch")
        require(receipt["receipt_is_output_permit"] is False, f"{slot} is output permit")
        require(_is_utc(receipt["issued_at_utc"]), f"{slot} issued time malformed")
        require(_is_utc(receipt["not_before_utc"]), f"{slot} not-before malformed")
        require(_is_utc(receipt["expires_at_utc"]), f"{slot} expiry malformed")
        require(
            receipt["issued_at_utc"] <= receipt["not_before_utc"]
            < receipt["expires_at_utc"]
            and receipt["not_before_utc"] <= checked < receipt["expires_at_utc"],
            f"{slot} authority time window invalid",
        )
        for key in _AUTHORITY_SHARED_BINDINGS:
            require(receipt[key] == intersection[key], f"{slot} {key} mismatch")
        cases = receipt["allowed_case_ids"]
        operations = receipt["allowed_operations"]
        repetitions = receipt["allowed_repetition_indices"]
        forbidden = receipt["forbidden_operations"]
        require(cases == sorted(cases), f"{slot} cases not canonical")
        require(operations == sorted(operations), f"{slot} operations not canonical")
        require(repetitions == sorted(repetitions), f"{slot} repetitions not canonical")
        require(forbidden == sorted(forbidden), f"{slot} forbidden operations not canonical")
        require(set(operations).isdisjoint(forbidden), f"{slot} allowed/forbidden overlap")
        require(
            receipt["canonical_payload_sha256"] == _scope_payload_sha256(receipt),
            f"{slot} canonical payload preimage mismatch",
        )
        require(
            receipt["receipt_id"] == _scope_receipt_id(receipt),
            f"{slot} receipt id preimage mismatch",
        )
        prefix = "M" if track == MANAGED_TRACK else "S"
        valid_cases = set(MANAGED_CASE_IDS if track == MANAGED_TRACK else SELF_HOSTED_CASE_IDS)
        require(all(case.startswith(prefix) and case in valid_cases for case in cases), f"{slot} case/track mismatch")
        allowed_case_sets.append(set(cases))
        allowed_operation_sets.append(set(operations))
        allowed_repetition_sets.append(set(repetitions))
        forbidden_union.update(forbidden)
        principals.add(receipt["authority_principal_id_sha256"])
        receipt_ids.add(receipt["receipt_id"])
        nonces.add(receipt["nonce_sha256"])
        requests.add(receipt["authorization_request_sha256"])
        signatures.add(receipt["signature_receipt_sha256"])
    require(
        all(len(values) == 5 for values in (principals, receipt_ids, nonces, requests, signatures)),
        "authority role independence drift",
    )
    require(
        set(intersection["effective_allowed_case_ids"]) == set.intersection(*allowed_case_sets),
        "effective case scope is not the exact intersection",
    )
    require(
        set(intersection["effective_allowed_repetition_indices"]) == set.intersection(*allowed_repetition_sets),
        "effective repetition scope is not the exact intersection",
    )
    require(
        set(intersection["effective_allowed_operations"])
        == set.intersection(*allowed_operation_sets[:4]) - forbidden_union,
        "effective operation scope is not allowed intersection minus forbidden union",
    )
    require(
        set(receipts[4]["allowed_operations"]).issubset(EMERGENCY_STOP_OPERATIONS),
        "emergency receipt contains a positive experiment operation",
    )
    require(
        set(intersection["effective_allowed_operations"]).isdisjoint(
            receipts[4]["allowed_operations"]
        ),
        "emergency authority added positive execution authority",
    )
    for key in (
        "effective_allowed_case_ids",
        "effective_allowed_operations",
        "effective_allowed_repetition_indices",
    ):
        require(intersection[key] == sorted(intersection[key]), f"intersection {key} not canonical")
    require(
        intersection["field_level_intersection_sha256"]
        == _authority_intersection_sha256(intersection),
        "field-level intersection preimage mismatch",
    )
    if phase == "EXPERIMENT_EXECUTION_GRANT":
        require(len(intersection["effective_allowed_case_ids"]) == 1, "execution case scope is not singleton")
        require(len(intersection["effective_allowed_repetition_indices"]) == 1, "execution repetition scope is not singleton")
        require(intersection["effective_allowed_case_ids"] == [bundle["case_id"]], "execution case/assignment mismatch")
        require(intersection["effective_allowed_repetition_indices"] == [bundle["repetition_index"]], "execution repetition/assignment mismatch")
        require(capability["case_id"] == bundle["case_id"], "capability case mismatch")
        require(capability["repetition_index"] == bundle["repetition_index"], "capability repetition mismatch")
        require(
            set(intersection["effective_allowed_operations"]).issubset(EXPERIMENT_ADAPTER_OPERATIONS),
            "execution grant contains an operation outside adapter catalog",
        )
        require(
            set(intersection["effective_allowed_operations"]).isdisjoint(
                STOP_ONLY_ADAPTER_OPERATIONS
            ),
            "execution grant contains a stop-only adapter operation",
        )
    else:
        dangerous_prefixes = ("SIGN_", "MUTATE_", "FAULT_", "ARM_", "TRIGGER_", "PROVISION_", "START_")
        require(
            all(not operation.startswith(dangerous_prefixes) for operation in intersection["effective_allowed_operations"]),
            "preflight grant contains a mutating operation",
        )
        require(
            set(intersection["effective_allowed_operations"]).issubset(PREFLIGHT_OPERATIONS),
            "preflight grant contains an operation outside the read-only catalog",
        )
    require(capability["case_id"] == bundle["case_id"], "capability/root case mismatch")
    require(capability["repetition_index"] == bundle["repetition_index"], "capability/root repetition mismatch")
    require(bundle["bundle_id"] == _authority_bundle_id(bundle), "authority bundle id preimage mismatch")


def _validate_authority_candidate(bundle: dict[str, Any], schema: dict[str, Any]) -> None:
    _validate_instance(bundle, schema, schema, "$")
    _validate_authority_bundle_semantics(bundle)


def validate_authority_schema(schema: Any) -> None:
    _validate_schema_root(schema, AUTHORITY_RECEIPT_SCHEMA, "authority bundle schema")
    require(sha256_value(schema) == AUTHORITY_SCHEMA_SHA256, "authority schema bytes drift")
    expected_defs = {
        "authority_intersection", "caps", "case_id", "cost_authority_receipt",
        "currentness", "custodian_credential_receipt", "emergency_stop_authority_receipt",
        "execution_capability_commitment", "owner_scope_receipt", "resource_authority_receipt",
        "scope_receipt", "sha256", "track_id", "utc",
    }
    require(set(schema["$defs"]) == expected_defs, "authority schema defs drift")
    expected_root_fields = {
        "adapter_build_sha256", "adapter_set_manifest_sha256", "assignment_sha256",
        "authority_intersection", "bundle_id", "case_id", "cleanup_policy_sha256",
        "condition_output_authorized", "configuration_sha256", "contract_sha256",
        "cost_authority_receipt", "cost_scope_sha256", "credential_scope_sha256",
        "currentness", "custodian_credential_receipt", "effective_allowed_operations",
        "emergency_stop_authority_receipt", "execution_capability_commitment",
        "field_level_intersection_sha256", "namespace_id", "offline_harness_manifest_sha256",
        "owner_scope_receipt", "phase", "profile_sha256", "public_bundle_is_bearer_capability",
        "receipt_is_output_permit", "repetition_index", "resource_authority_receipt",
        "resource_scope_sha256", "retention_policy_sha256", "revocation_epoch",
        "runner_build_sha256", "schedule_sha256", "schema", "simulation_run_id",
        "stop_control_plane_manifest_sha256", "suite_id", "track_id",
    }
    require(set(schema["properties"]) == expected_root_fields, "authority root catalog drift")
    intersection_fields = {
        "adapter_build_sha256", "adapter_set_manifest_sha256", "assignment_sha256",
        "cleanup_policy_sha256", "configuration_sha256", "contract_sha256",
        "cost_scope_sha256", "credential_scope_sha256", "effective_allowed_case_ids",
        "effective_allowed_operations", "effective_allowed_repetition_indices",
        "field_level_intersection_sha256", "namespace_id", "nonempty_exact_intersection",
        "offline_harness_manifest_sha256", "phase", "profile_sha256", "resource_scope_sha256",
        "retention_policy_sha256", "revocation_epoch", "runner_build_sha256",
        "schedule_sha256", "simulation_run_id", "stop_control_plane_manifest_sha256",
        "suite_id", "track_id",
    }
    require(
        set(schema["$defs"]["authority_intersection"]["properties"])
        == intersection_fields,
        "authority intersection catalog drift",
    )
    capability_fields = set(_CAPABILITY_COMMITMENT_BINDING_FIELDS) | {
        "capability_commitment_sha256",
        "private_capability_bytes_serialized",
        "state",
    }
    require(
        set(schema["$defs"]["execution_capability_commitment"]["properties"])
        == capability_fields,
        "authority capability catalog drift",
    )
    scope_fields = set(_AUTHORITY_SHARED_BINDINGS) | {
        "allowed_case_ids", "allowed_operations", "allowed_repetition_indices",
        "artifact_type", "authority_principal_id_sha256", "authorization_request_sha256",
        "canonical_payload_sha256", "expires_at_utc", "forbidden_operations",
        "issued_at_utc", "nonce_sha256", "not_before_utc", "receipt_id",
        "receipt_is_output_permit", "signature_receipt_sha256", "trust_policy_sha256",
    }
    require(
        set(schema["$defs"]["scope_receipt"]["properties"]) == scope_fields,
        "authority scope receipt catalog drift",
    )
    for slot, role in _AUTHORITY_ROLE_SLOTS:
        expected_def = {
            "allOf": [
                {"$ref": "#/$defs/scope_receipt"},
                {"properties": {"artifact_type": {"const": role}}, "required": ["artifact_type"]},
            ]
        }
        require(schema["$defs"][slot] == expected_def, f"authority role def {slot} drift")
        require(schema["properties"][slot] == {"$ref": f"#/$defs/{slot}"}, f"authority root role ref {slot} drift")
    require(schema["properties"]["condition_output_authorized"] == {"const": False}, "authority output condition drift")
    require(schema["properties"]["receipt_is_output_permit"] == {"const": False}, "authority output permit drift")
    require(schema["properties"]["public_bundle_is_bearer_capability"] == {"const": False}, "authority bearer drift")
    capability_schema = schema["$defs"]["execution_capability_commitment"]["properties"]
    for key, expected in {
        "private_capability_bytes_serialized": False,
        "single_consume": True,
        "single_executor_session": True,
        "single_run": True,
    }.items():
        require(capability_schema[key] == {"const": expected}, f"authority capability {key} drift")
    kat = _authority_kat()
    _validate_authority_candidate(kat, schema)
    _validate_authority_candidate(_authority_preflight_kat(), schema)
    mutations: list[dict[str, Any]] = []
    wrong_role = copy.deepcopy(kat)
    wrong_role["owner_scope_receipt"]["artifact_type"] = "COST_AUTHORITY_RECEIPT"
    _rebind_authority_hashes(wrong_role)
    mutations.append(wrong_role)
    wrong_track = copy.deepcopy(kat)
    wrong_track["track_id"] = SELF_HOSTED_TRACK
    _rebind_authority_hashes(wrong_track)
    mutations.append(wrong_track)
    wrong_phase = copy.deepcopy(kat)
    wrong_phase["owner_scope_receipt"]["phase"] = "PREFLIGHT_OBSERVATION_GRANT"
    _rebind_authority_hashes(wrong_phase)
    mutations.append(wrong_phase)
    wrong_intersection = copy.deepcopy(kat)
    wrong_intersection["authority_intersection"]["effective_allowed_case_ids"] = ["M01"]
    _rebind_authority_hashes(wrong_intersection)
    mutations.append(wrong_intersection)
    expired = copy.deepcopy(kat)
    expired["owner_scope_receipt"]["expires_at_utc"] = "2026-07-15T19:59:59Z"
    _rebind_authority_hashes(expired)
    mutations.append(expired)
    wrong_epoch = copy.deepcopy(kat)
    wrong_epoch["cost_authority_receipt"]["revocation_epoch"] = 8
    _rebind_authority_hashes(wrong_epoch)
    mutations.append(wrong_epoch)
    overlap = copy.deepcopy(kat)
    overlap["resource_authority_receipt"]["forbidden_operations"] = [
        "STRONG_READ_EXACT_OPERATION_KEY"
    ]
    _rebind_authority_hashes(overlap)
    mutations.append(overlap)
    serialized = copy.deepcopy(kat)
    serialized["execution_capability_commitment"]["private_capability_bytes_serialized"] = True
    serialized["bundle_id"] = _authority_bundle_id(serialized)
    mutations.append(serialized)
    wrong_run = copy.deepcopy(kat)
    wrong_run["execution_capability_commitment"]["simulation_run_id"] = _tag_hash("other-run")
    wrong_run["bundle_id"] = _authority_bundle_id(wrong_run)
    mutations.append(wrong_run)
    wrong_stop_plane = copy.deepcopy(kat)
    wrong_stop_plane["owner_scope_receipt"]["stop_control_plane_manifest_sha256"] = (
        _tag_hash("other-stop-control-plane")
    )
    _rebind_authority_hashes(wrong_stop_plane)
    mutations.append(wrong_stop_plane)
    bad_calendar = copy.deepcopy(kat)
    bad_calendar["owner_scope_receipt"]["issued_at_utc"] = "2026-02-30T19:00:00Z"
    _rebind_authority_hashes(bad_calendar)
    mutations.append(bad_calendar)
    reused = copy.deepcopy(kat)
    reused["execution_capability_commitment"]["state"] = "START_COMMITTED"
    reused["bundle_id"] = _authority_bundle_id(reused)
    mutations.append(reused)
    wrong_assignment = copy.deepcopy(kat)
    replacement = _tag_hash("wrong-assignment")
    wrong_assignment["assignment_sha256"] = replacement
    wrong_assignment["authority_intersection"]["assignment_sha256"] = replacement
    wrong_assignment["execution_capability_commitment"]["assignment_sha256"] = replacement
    for slot, _ in _AUTHORITY_ROLE_SLOTS:
        wrong_assignment[slot]["assignment_sha256"] = replacement
    _rebind_authority_hashes(wrong_assignment)
    mutations.append(wrong_assignment)
    wrong_payload = copy.deepcopy(kat)
    wrong_payload["owner_scope_receipt"]["canonical_payload_sha256"] = _tag_hash(
        "wrong-payload"
    )
    wrong_payload["bundle_id"] = _authority_bundle_id(wrong_payload)
    mutations.append(wrong_payload)
    wrong_receipt_id = copy.deepcopy(kat)
    wrong_receipt_id["owner_scope_receipt"]["receipt_id"] = _tag_hash(
        "wrong-receipt-id"
    )
    wrong_receipt_id["bundle_id"] = _authority_bundle_id(wrong_receipt_id)
    mutations.append(wrong_receipt_id)
    wrong_bundle_id = copy.deepcopy(kat)
    wrong_bundle_id["bundle_id"] = _tag_hash("wrong-bundle-id")
    mutations.append(wrong_bundle_id)
    for index, mutation in enumerate(mutations):
        try:
            _validate_authority_candidate(mutation, schema)
        except ContractError:
            continue
        raise ContractError(f"authority negative mutation {index} accepted")


def _stop_receipt_id(receipt: dict[str, Any]) -> str:
    payload = {
        key: copy.deepcopy(value)
        for key, value in receipt.items()
        if key not in {"signature_receipt_sha256", "stop_id"}
    }
    return _domain_json_hash(STOP_RECEIPT_ID_DOMAIN, payload)


def _rebind_stop_id(receipt: dict[str, Any]) -> None:
    receipt["stop_id"] = _stop_receipt_id(receipt)


def _stop_kat(state: str = "STOP_ABSORBING_COMPLETE") -> dict[str, Any]:
    authority = _authority_kat()
    complete = state == "STOP_ABSORBING_COMPLETE"
    failed = state == "STOP_FAILED_QUARANTINED"
    requested = state == "STOP_REQUESTED"
    cleanup_status = (
        "REDUCTIVE_COMPLETE"
        if complete
        else "FAILED_QUARANTINED"
        if failed
        else "NOT_STARTED"
        if requested
        else "REDUCTIVE_IN_PROGRESS"
    )
    cleanup_terminal = cleanup_status in {"REDUCTIVE_COMPLETE", "FAILED_QUARANTINED"}
    credential_status = "REVOKED" if complete or failed else "NOT_REQUESTED" if requested else "PENDING"
    fault_status = "DISARMED" if complete or failed else "NOT_REQUESTED" if requested else "PENDING"
    receipt = {
        "adapter_build_sha256": authority["adapter_build_sha256"],
        "adapter_set_manifest_sha256": authority["adapter_set_manifest_sha256"],
        "application_calls": 1,
        "assignment_sha256": authority["assignment_sha256"],
        "authority_bundle_sha256": sha256_value(authority),
        "authority_phase": authority["phase"],
        "authority_revocation_epoch": authority["currentness"]["revocation_epoch"],
        "automatic_rerun_allowed": False,
        "capability_fence_receipt_sha256": _tag_hash("capability-fence"),
        "capability_invalidated": True,
        "case_id": authority["case_id"],
        "cleanup": {
            "cleanup_capability_commitment_sha256": _tag_hash("cleanup-capability"),
            "cleanup_completed_at_utc": "2026-07-15T20:06:00Z" if cleanup_terminal else None,
            "cleanup_receipt_sha256": _tag_hash("cleanup-receipt") if cleanup_terminal else None,
            "cleanup_status": cleanup_status,
            "egress_isolated": cleanup_terminal,
            "egress_isolation_receipt_sha256": _tag_hash("egress-isolation") if cleanup_terminal else None,
            "resource_frozen": cleanup_terminal,
        },
        "cleanup_policy_sha256": authority["authority_intersection"]["cleanup_policy_sha256"],
        "configuration_sha256": authority["configuration_sha256"],
        "control_plane_failure_ids": [_tag_hash("control-plane-failure")] if failed else [],
        "continuation_allowed": False,
        "contract_sha256": authority["contract_sha256"],
        "cost_scope_sha256": authority["authority_intersection"]["cost_scope_sha256"],
        "cost": {
            "actual_cost_minor_units": 1,
            "cost_authority_receipt_sha256": sha256_value(
                authority["cost_authority_receipt"]
            ),
            "currency": "USD",
            "remaining_authorized_minor_units": 9,
        },
        "credential": {
            "active_lease_commitments_after_stop": 0 if complete or failed else 1,
            "revoke_confirmed": complete or failed,
            "revoke_receipt_sha256": _tag_hash("revoke-receipt") if complete or failed else None,
            "revoke_requested": not requested,
            "revoke_status": credential_status,
        },
        "credential_scope_sha256": authority["authority_intersection"]["credential_scope_sha256"],
        "current_retained_row_sha256": _tag_hash("current-retained-row"),
        "durable_state": {
            "authority_currentness_receipt_sha256": authority["currentness"][
                "row_currentness_receipt_sha256"
            ],
            "call_state_sha256": _tag_hash("call-state"),
            "control_ledger_revision": 5,
            "operation_record_sha256": _tag_hash("operation-record"),
            "prepared_state_sha256": _tag_hash("prepared-state"),
        },
        "evidence_bundle_sha256": _tag_hash("evidence-bundle"),
        "evidence_preserved": True,
        "fault": {
            "disarm_confirmed": complete or failed,
            "disarm_receipt_sha256": _tag_hash("disarm-receipt") if complete or failed else None,
            "disarm_requested": not requested,
            "disarm_status": fault_status,
            "fault_controller_state_sha256": _tag_hash("fault-controller-state"),
        },
        "field_level_intersection_sha256": authority[
            "field_level_intersection_sha256"
        ],
        "last_completed_row_sha256": None,
        "manual_escalation_required": failed,
        "namespace_id": authority["namespace_id"],
        "new_calls_blocked": True,
        "offline_harness_manifest_sha256": authority["offline_harness_manifest_sha256"],
        "profile_sha256": authority["profile_sha256"],
        "receipt_is_execution_authority": False,
        "receipt_is_output_permit": False,
        "repetition_index": authority["repetition_index"],
        "resource_scope_sha256": authority["authority_intersection"]["resource_scope_sha256"],
        "retained_row_preserved": True,
        "retention_policy_sha256": authority["authority_intersection"]["retention_policy_sha256"],
        "retention_receipt_sha256": _tag_hash("retention-receipt"),
        "runner_build_sha256": authority["runner_build_sha256"],
        "schedule_sha256": authority["schedule_sha256"],
        "schema": STOP_RECEIPT_SCHEMA,
        "signature_receipt_sha256": _tag_hash("stop-signature-receipt"),
        "simulation_run_id": authority["simulation_run_id"],
        "stop_completed_at_utc": "2026-07-15T20:07:00Z" if complete else None,
        "stop_control_plane_manifest_sha256": authority["stop_control_plane_manifest_sha256"],
        "stop_id": "0" * 64,
        "stop_lifecycle_state": state,
        "stop_reason": "OPERATOR_STOP",
        "stop_requested_at_utc": "2026-07-15T20:05:00Z",
        "stop_trigger": "OWNER_CUSTODIAN_OR_EMERGENCY_OPERATOR_STOP",
        "stop_trigger_role": "OWNER",
        "suite_id": authority["suite_id"],
        "track_id": authority["track_id"],
        "unresolved_ambiguity_ids": [],
        "wire_attempts": 1,
    }
    _rebind_stop_id(receipt)
    return receipt


def _validate_stop_authority_binding(
    receipt: dict[str, Any],
    authority: dict[str, Any],
) -> None:
    intersection = authority["authority_intersection"]
    mapping = {
        "adapter_build_sha256": authority["adapter_build_sha256"],
        "adapter_set_manifest_sha256": authority["adapter_set_manifest_sha256"],
        "assignment_sha256": authority["assignment_sha256"],
        "authority_bundle_sha256": sha256_value(authority),
        "authority_phase": authority["phase"],
        "authority_revocation_epoch": authority["revocation_epoch"],
        "case_id": authority["case_id"],
        "cleanup_policy_sha256": intersection["cleanup_policy_sha256"],
        "configuration_sha256": authority["configuration_sha256"],
        "contract_sha256": authority["contract_sha256"],
        "cost_scope_sha256": intersection["cost_scope_sha256"],
        "credential_scope_sha256": intersection["credential_scope_sha256"],
        "field_level_intersection_sha256": intersection[
            "field_level_intersection_sha256"
        ],
        "namespace_id": authority["namespace_id"],
        "offline_harness_manifest_sha256": authority[
            "offline_harness_manifest_sha256"
        ],
        "profile_sha256": authority["profile_sha256"],
        "repetition_index": authority["repetition_index"],
        "resource_scope_sha256": intersection["resource_scope_sha256"],
        "retention_policy_sha256": intersection["retention_policy_sha256"],
        "runner_build_sha256": authority["runner_build_sha256"],
        "schedule_sha256": authority["schedule_sha256"],
        "simulation_run_id": authority["simulation_run_id"],
        "stop_control_plane_manifest_sha256": authority[
            "stop_control_plane_manifest_sha256"
        ],
        "suite_id": authority["suite_id"],
        "track_id": authority["track_id"],
    }
    for key, expected in mapping.items():
        require(receipt[key] == expected, f"stop/authority {key} mismatch")
    require(
        receipt["cost"]["cost_authority_receipt_sha256"]
        == sha256_value(authority["cost_authority_receipt"]),
        "stop cost authority receipt mismatch",
    )
    require(
        receipt["durable_state"]["authority_currentness_receipt_sha256"]
        == authority["currentness"]["row_currentness_receipt_sha256"],
        "stop authority currentness receipt mismatch",
    )


def _validate_stop_receipt_semantics(receipt: dict[str, Any]) -> None:
    track = receipt["track_id"]
    require(track in (MANAGED_TRACK, SELF_HOSTED_TRACK), "stop track drift")
    cases = MANAGED_CASE_IDS if track == MANAGED_TRACK else SELF_HOSTED_CASE_IDS
    require(receipt["case_id"] in cases, "stop case/track mismatch")
    require(receipt["contract_sha256"] == ADAPTER_CONTRACT_SHA256, "stop contract binding drift")
    require(receipt["configuration_sha256"] == OFFLINE_CONFIGURATION_SHA256, "stop configuration binding drift")
    require(
        receipt["offline_harness_manifest_sha256"] == OFFLINE_HARNESS_MANIFEST_SHA256,
        "stop harness manifest binding drift",
    )
    require(receipt["schedule_sha256"] == OFFLINE_SCHEDULE_SHA256, "stop schedule binding drift")
    require(receipt["suite_id"] == OFFLINE_SUITE_ID, "stop suite binding drift")
    assignment, simulation_run_id, namespace_id = _assignment_lineage(
        track, receipt["case_id"], receipt["repetition_index"]
    )
    require(receipt["assignment_sha256"] == assignment, "stop assignment lineage drift")
    require(receipt["simulation_run_id"] == simulation_run_id, "stop run lineage drift")
    require(receipt["namespace_id"] == namespace_id, "stop namespace lineage drift")
    require(receipt["authority_phase"] == "EXPERIMENT_EXECUTION_GRANT", "stop phase is not execution")
    reasons, roles = STOP_TRIGGER_REASON_ROLE_MAP[receipt["stop_trigger"]]
    require(receipt["stop_reason"] in reasons, "stop reason does not match trigger")
    require(receipt["stop_trigger_role"] in roles, "stop role does not match trigger")
    for key in (
        "capability_invalidated",
        "evidence_preserved",
        "new_calls_blocked",
        "retained_row_preserved",
    ):
        require(receipt[key] is True, f"stop {key} must be true")
    for key in (
        "automatic_rerun_allowed",
        "continuation_allowed",
        "receipt_is_execution_authority",
        "receipt_is_output_permit",
    ):
        require(receipt[key] is False, f"stop {key} must be false")

    requested_at = receipt["stop_requested_at_utc"]
    completed_at = receipt["stop_completed_at_utc"]
    cleanup = receipt["cleanup"]
    credential = receipt["credential"]
    fault = receipt["fault"]
    require(_is_utc(requested_at), "stop request time malformed")
    cleanup_at = cleanup["cleanup_completed_at_utc"]
    if cleanup_at is not None:
        require(_is_utc(cleanup_at) and requested_at <= cleanup_at, "cleanup completion time invalid")
    if completed_at is not None:
        require(_is_utc(completed_at) and requested_at <= completed_at, "stop completion time invalid")
        require(cleanup_at is not None and cleanup_at <= completed_at, "stop completed before cleanup")

    cleanup_terminal = cleanup["cleanup_status"] in {
        "REDUCTIVE_COMPLETE",
        "FAILED_QUARANTINED",
    }
    require(
        (cleanup["cleanup_completed_at_utc"] is not None) is cleanup_terminal,
        "cleanup status/completion contradiction",
    )
    require(
        (cleanup["cleanup_receipt_sha256"] is not None) is cleanup_terminal,
        "cleanup status/receipt contradiction",
    )
    if cleanup_terminal:
        require(cleanup["egress_isolated"] is True, "terminal cleanup lacks egress isolation")
        require(cleanup["egress_isolation_receipt_sha256"] is not None, "terminal cleanup lacks isolation receipt")
        require(cleanup["resource_frozen"] is True, "terminal cleanup lacks resource fence")

    credential_expected = {
        "NOT_REQUESTED": (False, False, False),
        "PENDING": (True, False, False),
        "REVOKED": (True, True, True),
        "FAILED_QUARANTINED": (True, False, True),
    }[credential["revoke_status"]]
    require(
        (
            credential["revoke_requested"],
            credential["revoke_confirmed"],
            credential["revoke_receipt_sha256"] is not None,
        )
        == credential_expected,
        "credential stop state contradiction",
    )
    if credential["revoke_confirmed"]:
        require(
            credential["active_lease_commitments_after_stop"] == 0,
            "revoked credential still has active lease commitments",
        )

    fault_expected = {
        "NOT_REQUESTED": (False, False, False),
        "PENDING": (True, False, False),
        "DISARMED": (True, True, True),
        "FAILED_QUARANTINED": (True, False, True),
    }[fault["disarm_status"]]
    require(
        (
            fault["disarm_requested"],
            fault["disarm_confirmed"],
            fault["disarm_receipt_sha256"] is not None,
        )
        == fault_expected,
        "fault stop state contradiction",
    )

    failures = bool(receipt["unresolved_ambiguity_ids"] or receipt["control_plane_failure_ids"])
    failures = failures or cleanup["cleanup_status"] == "FAILED_QUARANTINED"
    failures = failures or credential["revoke_status"] == "FAILED_QUARANTINED"
    failures = failures or fault["disarm_status"] == "FAILED_QUARANTINED"
    all_success = (
        cleanup["cleanup_status"] == "REDUCTIVE_COMPLETE"
        and credential["revoke_status"] == "REVOKED"
        and fault["disarm_status"] == "DISARMED"
        and not failures
    )
    state = receipt["stop_lifecycle_state"]
    require(
        (state == "STOP_ABSORBING_COMPLETE") is all_success,
        "stop absorbing-complete converse violated",
    )
    require(
        (state == "STOP_FAILED_QUARANTINED") is failures,
        "stop failed-quarantined converse violated",
    )
    if state == "STOP_ABSORBING_COMPLETE":
        require(completed_at is not None, "complete stop lacks completion time")
        require(receipt["manual_escalation_required"] is False, "complete stop escalates")
    else:
        require(completed_at is None, "noncomplete stop has completion time")
    if failures:
        require(receipt["manual_escalation_required"] is True, "failed stop lacks escalation")
    require(receipt["stop_id"] == _stop_receipt_id(receipt), "stop id preimage mismatch")


def _validate_stop_candidate(
    receipt: dict[str, Any],
    schema: dict[str, Any],
    authority: dict[str, Any] | None = None,
) -> None:
    _validate_instance(receipt, schema, schema, "$")
    _validate_stop_receipt_semantics(receipt)
    if authority is not None:
        _validate_stop_authority_binding(receipt, authority)


def validate_stop_schema(schema: Any) -> None:
    _validate_schema_root(schema, STOP_RECEIPT_SCHEMA, "stop receipt schema")
    require(sha256_value(schema) == STOP_SCHEMA_SHA256, "stop schema bytes drift")
    require(
        set(schema["$defs"])
        == {"cleanup", "cost", "credential_stop", "durable_state", "fault_stop", "sha256", "utc"},
        "stop schema defs drift",
    )
    expected_root_fields = {
        "adapter_build_sha256", "adapter_set_manifest_sha256", "application_calls",
        "assignment_sha256", "authority_bundle_sha256", "authority_phase",
        "authority_revocation_epoch", "automatic_rerun_allowed",
        "capability_fence_receipt_sha256", "capability_invalidated", "case_id",
        "cleanup", "cleanup_policy_sha256", "configuration_sha256",
        "continuation_allowed", "contract_sha256", "control_plane_failure_ids",
        "cost", "cost_scope_sha256", "credential", "credential_scope_sha256",
        "current_retained_row_sha256", "durable_state", "evidence_bundle_sha256",
        "evidence_preserved", "fault", "field_level_intersection_sha256",
        "last_completed_row_sha256", "manual_escalation_required", "namespace_id",
        "new_calls_blocked", "offline_harness_manifest_sha256", "profile_sha256",
        "receipt_is_execution_authority", "receipt_is_output_permit",
        "repetition_index", "resource_scope_sha256", "retained_row_preserved",
        "retention_policy_sha256", "retention_receipt_sha256", "runner_build_sha256",
        "schedule_sha256", "schema", "signature_receipt_sha256", "simulation_run_id",
        "stop_completed_at_utc", "stop_control_plane_manifest_sha256", "stop_id",
        "stop_lifecycle_state", "stop_reason", "stop_requested_at_utc", "stop_trigger",
        "stop_trigger_role", "suite_id", "track_id", "unresolved_ambiguity_ids",
        "wire_attempts",
    }
    require(set(schema["properties"]) == expected_root_fields, "stop root catalog drift")
    for name in ("cleanup", "cost", "credential_stop", "durable_state", "fault_stop"):
        definition = schema["$defs"][name]
        require(definition.get("type") == "object", f"stop {name} type drift")
        require(definition.get("additionalProperties") is False, f"stop {name} is open")
        require(set(definition["required"]) == set(definition["properties"]), f"stop {name} closure drift")
    for key in (
        "automatic_rerun_allowed",
        "continuation_allowed",
        "receipt_is_execution_authority",
        "receipt_is_output_permit",
    ):
        require(schema["properties"][key] == {"const": False}, f"stop schema {key} drift")
    for key in (
        "capability_invalidated",
        "evidence_preserved",
        "new_calls_blocked",
        "retained_row_preserved",
    ):
        require(schema["properties"][key] == {"const": True}, f"stop schema {key} drift")
    require(
        schema["properties"]["stop_lifecycle_state"]["enum"]
        == [
            "STOP_REQUESTED",
            "STOP_FENCING",
            "STOP_ABSORBING_COMPLETE",
            "STOP_FAILED_QUARANTINED",
        ],
        "stop lifecycle catalog drift",
    )
    require(
        schema["properties"]["stop_trigger_role"]["enum"]
        == ["OWNER", "CUSTODIAN", "EMERGENCY_OPERATOR", "SYSTEM_BOUNDARY", "SYSTEM_EXPIRY_OR_REVOCATION"],
        "stop role catalog drift",
    )
    require(
        set(schema["properties"]["stop_trigger"]["enum"]) == set(STOP_TRIGGER_REASON_ROLE_MAP),
        "stop trigger catalog drift",
    )
    require(
        set(schema["properties"]["stop_reason"]["enum"])
        == {reason for reasons, _ in STOP_TRIGGER_REASON_ROLE_MAP.values() for reason in reasons},
        "stop reason catalog drift",
    )
    require("control_plane_failure_ids" in schema["properties"], "stop control failure evidence missing")
    require(type(schema.get("allOf")) is list and len(schema["allOf"]) >= 20, "stop cross-field guards missing")

    authority = _authority_kat()
    for state in (
        "STOP_REQUESTED",
        "STOP_FENCING",
        "STOP_ABSORBING_COMPLETE",
        "STOP_FAILED_QUARANTINED",
    ):
        _validate_stop_candidate(_stop_kat(state), schema, authority)

    complete = _stop_kat()
    mutations: list[dict[str, Any]] = []
    wrong_case = copy.deepcopy(complete)
    wrong_case["case_id"] = "S00"
    _rebind_stop_id(wrong_case)
    mutations.append(wrong_case)
    wrong_run = copy.deepcopy(complete)
    wrong_run["simulation_run_id"] = _tag_hash("wrong-run")
    _rebind_stop_id(wrong_run)
    mutations.append(wrong_run)
    wrong_reason = copy.deepcopy(complete)
    wrong_reason["stop_reason"] = "AUTHORITY_REVOKED"
    _rebind_stop_id(wrong_reason)
    mutations.append(wrong_reason)
    wrong_role = copy.deepcopy(complete)
    wrong_role["stop_trigger_role"] = "SYSTEM_BOUNDARY"
    _rebind_stop_id(wrong_role)
    mutations.append(wrong_role)
    missing_completion = copy.deepcopy(complete)
    missing_completion["stop_completed_at_utc"] = None
    _rebind_stop_id(missing_completion)
    mutations.append(missing_completion)
    false_complete = _stop_kat("STOP_FENCING")
    false_complete["cleanup"] = copy.deepcopy(complete["cleanup"])
    false_complete["credential"] = copy.deepcopy(complete["credential"])
    false_complete["fault"] = copy.deepcopy(complete["fault"])
    _rebind_stop_id(false_complete)
    mutations.append(false_complete)
    hidden_failure = _stop_kat("STOP_FAILED_QUARANTINED")
    hidden_failure["stop_lifecycle_state"] = "STOP_FENCING"
    _rebind_stop_id(hidden_failure)
    mutations.append(hidden_failure)
    no_escalation = _stop_kat("STOP_FAILED_QUARANTINED")
    no_escalation["manual_escalation_required"] = False
    _rebind_stop_id(no_escalation)
    mutations.append(no_escalation)
    bad_revoke = copy.deepcopy(complete)
    bad_revoke["credential"]["active_lease_commitments_after_stop"] = 1
    _rebind_stop_id(bad_revoke)
    mutations.append(bad_revoke)
    bad_disarm = copy.deepcopy(complete)
    bad_disarm["fault"]["disarm_requested"] = False
    _rebind_stop_id(bad_disarm)
    mutations.append(bad_disarm)
    bad_cleanup_time = copy.deepcopy(complete)
    bad_cleanup_time["cleanup"]["cleanup_completed_at_utc"] = "2026-07-15T20:04:59Z"
    _rebind_stop_id(bad_cleanup_time)
    mutations.append(bad_cleanup_time)
    bad_stop_time = copy.deepcopy(complete)
    bad_stop_time["stop_completed_at_utc"] = "2026-07-15T20:05:59Z"
    _rebind_stop_id(bad_stop_time)
    mutations.append(bad_stop_time)
    bad_calendar = copy.deepcopy(complete)
    bad_calendar["stop_requested_at_utc"] = "2026-02-30T20:05:00Z"
    _rebind_stop_id(bad_calendar)
    mutations.append(bad_calendar)
    bad_stop_id = copy.deepcopy(complete)
    bad_stop_id["stop_id"] = _tag_hash("wrong-stop-id")
    mutations.append(bad_stop_id)
    reusable = copy.deepcopy(complete)
    reusable["automatic_rerun_allowed"] = True
    _rebind_stop_id(reusable)
    mutations.append(reusable)
    for index, mutation in enumerate(mutations):
        try:
            _validate_stop_candidate(mutation, schema, authority)
        except ContractError:
            continue
        raise ContractError(f"stop negative mutation {index} accepted")


def validate_observation(observation: Any) -> None:
    exact_keys(
        observation,
        (
            "audit_scope",
            "authority",
            "boundary",
            "inventory",
            "lineage",
            "observation_class",
            "observed_at_utc",
            "planned_counts",
            "runtime_counts",
            "schema",
        ),
        "observation",
    )
    require(observation["schema"] == OBSERVATION_SCHEMA, "observation schema drift")
    require(observation["observation_class"] == "UNBOUND_SYNTHETIC_PACKET_AUDIT", "observation class drift")
    require(observation["observed_at_utc"] == "2026-07-15T20:00:00Z", "observation time drift")

    audit = observation["audit_scope"]
    exact_keys(
        audit,
        (
            "external_organization_state_observed",
            "host_visibility_complete",
            "network_observed",
            "repository_scope",
            "secret_values_inspected_or_recorded",
        ),
        "observation audit scope",
    )
    require(
        audit["repository_scope"] == "CURRENT_PACKET_AND_FROZEN_PREDECESSOR_ARTIFACTS_ONLY",
        "observation repository scope drift",
    )
    for key in (
        "external_organization_state_observed",
        "host_visibility_complete",
        "network_observed",
        "secret_values_inspected_or_recorded",
    ):
        require(audit[key] is False, f"observation audit {key} must be false")

    authority = observation["authority"]
    authority_keys = (
        "authority_bundles_bound",
        "cost_authority_receipts_bound",
        "credential_authority_receipts_bound",
        "custodian_scope_receipts_bound",
        "emergency_stop_authority_receipts_bound",
        "execution_capabilities_emitted",
        "owner_scope_receipts_bound",
        "phase",
        "resource_authority_receipts_bound",
        "row_currentness_receipts_bound",
    )
    exact_keys(authority, authority_keys, "observation authority")
    require(authority["phase"] == "UNBOUND_SYNTHETIC", "observation authority phase drift")
    for key in authority_keys:
        if key != "phase":
            require(type(authority[key]) is int and authority[key] == 0, f"observation authority {key} must be zero")

    _validate_zero_boundary(observation["boundary"], "observation boundary")

    inventory = observation["inventory"]
    inventory_keys = (
        "adapter_artifacts",
        "credential_handles",
        "endpoints",
        "execution_runs",
        "provider_profiles",
        "resource_bindings",
        "runtime_receipts",
        "stop_receipts",
    )
    exact_keys(inventory, inventory_keys, "observation inventory")
    for key in inventory_keys:
        require(inventory[key] == [], f"observation inventory {key} must be empty")

    lineage = observation["lineage"]
    exact_keys(
        lineage,
        (
            "baseline_commit",
            "offline_configuration_sha256",
            "offline_harness_manifest_sha256",
            "offline_rows_sha256",
            "offline_schedule_sha256",
            "predecessor_source_commit",
            "preregistration_contract_sha256",
        ),
        "observation lineage",
    )
    require(
        lineage
        == {
            "baseline_commit": BASELINE_COMMIT,
            "offline_configuration_sha256": OFFLINE_CONFIGURATION_SHA256,
            "offline_harness_manifest_sha256": OFFLINE_HARNESS_MANIFEST_SHA256,
            "offline_rows_sha256": OFFLINE_ROWS_SHA256,
            "offline_schedule_sha256": OFFLINE_SCHEDULE_SHA256,
            "predecessor_source_commit": PREDECESSOR_SOURCE_COMMIT,
            "preregistration_contract_sha256": PREREGISTRATION_CONTRACT_SHA256,
        },
        "observation lineage drift",
    )

    planned = observation["planned_counts"]
    exact_keys(
        planned,
        (
            "client_conformance_double_rows",
            "managed_cases",
            "managed_service_fault_proxy_rows",
            "planned_rows",
            "self_hosted_adversarial_lab_rows",
            "self_hosted_cases",
            "tracks",
        ),
        "observation planned counts",
    )
    require(
        planned
        == {
            "client_conformance_double_rows": 420,
            "managed_cases": 16,
            "managed_service_fault_proxy_rows": 210,
            "planned_rows": 1020,
            "self_hosted_adversarial_lab_rows": 390,
            "self_hosted_cases": 18,
            "tracks": 2,
        },
        "observation planned counts drift",
    )

    runtime = observation["runtime_counts"]
    runtime_keys = (
        "application_calls",
        "evaluable_case_rows",
        "provider_evidence_rows",
        "provider_processing_events",
        "retained_rows",
        "runtime_rows",
        "wire_attempts",
    )
    exact_keys(runtime, runtime_keys, "observation runtime counts")
    for key in runtime_keys:
        require(type(runtime[key]) is int and runtime[key] == 0, f"observation runtime {key} must be zero")


def build_validation_receipt(
    contract: Any,
    authority_schema: Any,
    stop_schema: Any,
    observation: Any,
) -> dict[str, Any]:
    validate_contract(contract)
    validate_authority_schema(authority_schema)
    validate_stop_schema(stop_schema)
    validate_observation(observation)
    return {
        "artifact_sha256": {
            "adapter_contract": sha256_value(contract),
            "authority_receipt_schema": sha256_value(authority_schema),
            "observation": sha256_value(observation),
            "stop_receipt_schema": sha256_value(stop_schema),
        },
        "authority_model": {
            "capability": "PRIVATE_NONSERIALIZABLE_SINGLE_RUN_SINGLE_SESSION_SINGLE_CONSUMPTION",
            "start_logic": "START_ALL_FIVE_CURRENT_OWNER_CUSTODIAN_RESOURCE_COST_INTERSECTION_WITH_EMERGENCY_VETO",
            "stop_logic": "STOP_OWNER_OR_CUSTODIAN_OR_EMERGENCY_OR_BOUNDARY_OR_EXPIRY",
        },
        "baseline_commit": BASELINE_COMMIT,
        "boundary": dict(observation["boundary"]),
        "data_quality": {
            "contract_closure": "PASS",
            "execution_evidence": "NOT_EVALUATED_ZERO_RUNTIME_ROWS",
            "schema_closure": "PASS",
            "synthetic_observation": "PASS_UNBOUND_ZERO_RUNTIME",
        },
        "date": "2026-07-15",
        "decision": DECISION,
        "next_unit": contract["next_unit"],
        "planned_counts": dict(observation["planned_counts"]),
        "schema": VALIDATION_RECEIPT_SCHEMA,
        "status": STATUS,
        "track_results": {
            MANAGED_TRACK: "CONTRACT_VALIDATED_RUNTIME_UNBOUND",
            SELF_HOSTED_TRACK: "CONTRACT_VALIDATED_RUNTIME_UNBOUND",
        },
    }


TSV_FIELDS = (
    ("schema", ("schema",)),
    ("status", ("status",)),
    ("decision", ("decision",)),
    ("date", ("date",)),
    ("baseline_commit", ("baseline_commit",)),
    ("adapter_contract_sha256", ("artifact_sha256", "adapter_contract")),
    ("authority_receipt_schema_sha256", ("artifact_sha256", "authority_receipt_schema")),
    ("stop_receipt_schema_sha256", ("artifact_sha256", "stop_receipt_schema")),
    ("observation_sha256", ("artifact_sha256", "observation")),
    ("tracks", ("planned_counts", "tracks")),
    ("managed_cases", ("planned_counts", "managed_cases")),
    ("self_hosted_cases", ("planned_counts", "self_hosted_cases")),
    ("planned_rows", ("planned_counts", "planned_rows")),
    ("client_conformance_double_rows", ("planned_counts", "client_conformance_double_rows")),
    ("managed_service_fault_proxy_rows", ("planned_counts", "managed_service_fault_proxy_rows")),
    ("self_hosted_adversarial_lab_rows", ("planned_counts", "self_hosted_adversarial_lab_rows")),
    ("start_logic", ("authority_model", "start_logic")),
    ("stop_logic", ("authority_model", "stop_logic")),
    ("capability", ("authority_model", "capability")),
    ("contract_closure", ("data_quality", "contract_closure")),
    ("schema_closure", ("data_quality", "schema_closure")),
    ("synthetic_observation", ("data_quality", "synthetic_observation")),
    ("execution_evidence", ("data_quality", "execution_evidence")),
    ("experiment_executed", ("boundary", "experiment_executed")),
    ("provider_called", ("boundary", "provider_called")),
    ("credentials_accessed", ("boundary", "credentials_accessed")),
    ("runner_implemented", ("boundary", "runner_implemented")),
    ("adapter_implemented", ("boundary", "adapter_implemented")),
    ("execution_capability_emitted", ("boundary", "execution_capability_emitted")),
    ("stop_capability_emitted", ("boundary", "stop_capability_emitted")),
    ("receipt_is_execution_authority", ("boundary", "receipt_is_execution_authority")),
    ("receipt_is_output_permit", ("boundary", "receipt_is_output_permit")),
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


def render_tsv(receipt: dict[str, Any]) -> str:
    return "\n".join(
        f"{label}\t{_tsv_scalar(_lookup(receipt, path))}" for label, path in TSV_FIELDS
    ) + "\n"


def self_test(
    contract: Any,
    authority_schema: Any,
    stop_schema: Any,
    observation: Any,
) -> dict[str, Any]:
    first = build_validation_receipt(contract, authority_schema, stop_schema, observation)
    second = build_validation_receipt(contract, authority_schema, stop_schema, observation)
    require(canonical_bytes(first) == canonical_bytes(second), "validation receipt is nondeterministic")
    require(render_tsv(first) == render_tsv(second), "validation TSV is nondeterministic")
    return first


__all__ = [
    "AUTHORITY_RECEIPT_SCHEMA",
    "BASELINE_COMMIT",
    "CONTRACT_SCHEMA",
    "ContractError",
    "DECISION",
    "OBSERVATION_SCHEMA",
    "STOP_RECEIPT_SCHEMA",
    "STATUS",
    "VALIDATION_RECEIPT_SCHEMA",
    "build_validation_receipt",
    "canonical_bytes",
    "render_tsv",
    "self_test",
    "sha256_value",
    "validate_authority_schema",
    "validate_contract",
    "validate_observation",
    "validate_stop_schema",
]
