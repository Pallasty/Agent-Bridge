"""Offline, credential-blind admission preflight for Track B T22-A1.

This module validates only committed contracts and local non-secret host
identity digests. It does not discover endpoints, inspect credential stores,
connect to another host, start a service, publish a checkpoint, or authorize
execution.
"""
from __future__ import annotations

import hashlib
import json
import platform
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-domain-attestation-schema-v1.json"
CONTRACT_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-three-domain-admission-contract-v1.json"
PROPOSAL_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-owner-decision-proposal-v1.json"
EXECUTION_SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-distributed-execution-contract-schema-v1.json"
EVENT_SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-distributed-event-schema-v1.json"
TERMINAL_SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-terminal-evidence-schema-v1.json"
COLLECTION_CHALLENGE_SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-domain-collection-challenge-schema-v1.json"
CONTRACT_DOMAIN = b"AB_TRACK_B_T22_A1_THREE_DOMAIN_ADMISSION_CONTRACT_V1\0"
PROPOSAL_DOMAIN = b"AB_TRACK_B_T22_A1_OWNER_DECISION_PROPOSAL_V1\0"
EXPECTED_SCHEMA_SHA256 = "1b261a7ac328de62cbcb51eac9189787e3e5144688ec967311c7341f630b8a2b"
EXPECTED_EXECUTION_SCHEMA_SHA256 = "2974616587d4462b718fb5dae0a621c0d16ff4f844830b8b37c8bafd9a27429b"
EXPECTED_EVENT_SCHEMA_SHA256 = "4aaad4ea4006cfbae80fc784837146f3de48bcf9655fd1fe30a237f0d34f6cf5"
EXPECTED_TERMINAL_SCHEMA_SHA256 = "f3e6b833b04150376d09f3926dc75601acced248ebd9f9e08d70a86cc51e2a1a"
EXPECTED_COLLECTION_CHALLENGE_SCHEMA_SHA256 = "26d078bb9716cdb443808755ef87c0962f5e4284f94be6f1d168c370a911676d"
STATUS = "BLOCKED_REMOTE_ATTESTATIONS_THIRD_DOMAIN_MODE_ENDPOINT_SET_AND_EXACT_OWNER_DECISION_REQUIRED"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def domain_digest(domain: bytes, value: dict, self_field: str) -> str:
    unsigned = dict(value)
    unsigned.pop(self_field, None)
    return hashlib.sha256(domain + canonical(unsigned)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_attestation_schema(value: dict) -> None:
    assert value["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert value["$id"] == "agent_bridge.biocortex.track_b.t22_a1.domain_attestation.v1"
    assert value["type"] == "object" and value["additionalProperties"] is False
    assert set(value["required"]) == {
        "schema", "packet_kind", "hashing_contract", "domain_id", "attested_at", "expires_at",
        "source_commit", "host_identity", "operator_binding", "network_binding",
        "workload_readiness", "claims", "attestation_sha256",
    }
    properties = value["properties"]
    assert properties["schema"]["const"] == "agent_bridge.biocortex.track_b.t22_a1.domain_attestation.v1"
    assert properties["packet_kind"]["const"] == "T22_A1_HOST_DOMAIN_ATTESTATION"
    assert properties["domain_id"]["pattern"] == "^domain-[123]$"
    defs = value["$defs"]
    assert defs["sha256"]["pattern"] == "^(?!0{64}$)[0-9a-f]{64}$"
    assert defs["hashing_contract"]["properties"] == {
        "hash_algorithm": {"const": "SHA-256"},
        "canonicalization": {"const": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT"},
        "digest_domain": {"const": "agent-bridge/biocortex/track-b/t22-a1/domain-attestation/v1"},
        "hash_scope": {"const": "ENTIRE_PACKET_EXCEPT_ATTESTATION_SHA256"},
        "self_hash_field": {"const": "attestation_sha256"},
        "self_hash_field_excluded": {"const": True},
        "detached_signature_covers_complete_canonical_packet": {"const": True},
        "cross_field_semantic_validation_required": {"const": True},
        "candidate_reported_matches_authoritative": {"const": False},
    }
    host = defs["host_identity"]
    assert host["additionalProperties"] is False
    assert host["properties"]["physical_host_asserted"]["const"] is True
    assert set(host["properties"]["provider_kind"]["enum"]) == {"OWNER_PHYSICAL", "CLOUD_VM"}
    operator = defs["operator_binding"]["properties"]
    assert operator["signature_namespace"]["const"] == "agent-bridge-t22-a1-domain-v1"
    assert operator["private_key_exported"]["const"] is False
    network = defs["network_binding"]["properties"]
    assert network["transport"]["const"] == "OWNER_MANAGED_PRIVATE_OVERLAY"
    assert network["public_listener_allowed"]["const"] is False
    assert network["credential_material_embedded"]["const"] is False
    workload = defs["workload_readiness"]["properties"]
    assert workload["tracked_tree_clean"]["const"] is True
    assert workload["ambient_credentials_required"]["const"] is False
    claims = defs["claims"]["properties"]
    assert claims == {
        "candidate_for_distinct_physical_host": {"const": True},
        "site_or_power_independence_proved": {"const": False},
        "production_admissible": {"const": False},
        "attestation_is_execution_authority": {"const": False},
    }


def validate_contract(value: dict) -> None:
    assert set(value) == {
        "schema", "state", "track_id", "stage", "predecessor", "domain_admission",
        "network", "workload", "fault", "evidence", "future_execution_evidence_contracts", "external_checkpoint",
        "claim_ceiling", "contract_sha256",
    }
    assert value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.three_domain_admission_contract.v1"
    assert value["state"] == "NON_EXECUTING_FAIL_CLOSED_ADMISSION_ONLY"
    assert value["track_id"] == "SELF_HOSTED_ETCD_OPENBAO_THREE_DOMAIN"
    assert value["stage"] == "T22_A1_H"
    assert value["predecessor"] == {
        "stage": "T22_A0",
        "terminal_receipt_content_sha256": "3d73929854090364a399755fcc417d83f32cd552b4207a449661277413ec31ca",
        "result": "PASS_T22_A0_REAL_PROCESS_FAULT_EVIDENCE",
        "claim_ceiling": "SINGLE_PHYSICAL_HOST_PROCESS_EVIDENCE_ONLY",
    }
    assert value["domain_admission"] == {
        "required_domain_count": 3,
        "required_current_attestation_count": 3,
        "required_distinct_machine_identity_count": 3,
        "required_distinct_hardware_identity_count": 3,
        "required_distinct_domain_signing_key_count": 3,
        "required_distinct_hostname_count": 3,
        "known_alias_equivalence_classes": [["aio2", "pallasting-ThinkBook-14-G5-IRH", "tb14"]],
        "attestation_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-domain-attestation-schema-v1.json",
        "attestation_schema_sha256": EXPECTED_SCHEMA_SHA256,
        "attestation_maximum_age_seconds": 14400,
        "candidate_self_reports_are_authoritative": False,
        "owner_countersignature_over_exact_three_packet_set_required": True,
    }
    assert value["network"] == {
        "transport": "OWNER_MANAGED_PRIVATE_OVERLAY",
        "public_listeners_allowed": False,
        "host_global_firewall_or_route_mutation_allowed": False,
        "ambient_overlay_credentials_access_allowed": False,
        "exact_peer_endpoint_set_owner_bound_required": True,
        "exact_acl_receipt_owner_bound_required": True,
        "runner_provisions_or_joins_overlay": False,
    }
    assert value["workload"] == {
        "etcd_voter_per_domain": 1,
        "openbao_voter_per_domain": 1,
        "coordinator_domain_count": 1,
        "one_linearizable_authorize_consume_required": True,
        "replay_consume_rejection_required": True,
        "pre_fault_transit_signature_required": True,
        "post_fault_signature_verification_required": True,
    }
    assert value["fault"] == {
        "id": "ONE_DOMAIN_ALL_OWNED_CLUSTER_SERVICES_STOP_AND_RESTART",
        "target_selection": "OBSERVED_NON_COORDINATOR_VOTER_DOMAIN",
        "allowed_actions": ["OWNED_PROCESS_STOP", "OWNED_PROCESS_KILL_AFTER_TIMEOUT", "OWNED_PROCESS_RESTART"],
        "forbidden_actions": ["HOST_REBOOT", "HOST_POWER_OFF", "HOST_GLOBAL_IPTABLES_OR_TC", "BLOCK_DEVICE_MUTATION", "PROVIDER_INSTANCE_STOP"],
        "required_observation": "SURVIVING_TWO_DOMAINS_RETAIN_QUORUM_AND_VERIFY_PREFAULT_STATE_THEN_STOPPED_DOMAIN_REJOINS",
    }
    assert value["evidence"] == {
        "domain_attestations_independently_signed": True,
        "owner_exact_packet_set_binding_required": True,
        "coordinator_hash_chained_event_log_required": True,
        "per_domain_owned_process_logs_hashed": True,
        "per_domain_cleanup_receipts_required": True,
        "exact_secret_value_scan_required": True,
        "raw_credentials_endpoints_or_bootstrap_secrets_in_repository_or_receipts_allowed": False,
        "clock_skew_observed_and_bounded_required": True,
        "maximum_attestation_time_spread_seconds": 300,
    }
    assert value["future_execution_evidence_contracts"] == {
        "domain_collection_challenge_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-domain-collection-challenge-schema-v1.json",
        "domain_collection_challenge_schema_sha256": EXPECTED_COLLECTION_CHALLENGE_SCHEMA_SHA256,
        "distributed_execution_contract_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-distributed-execution-contract-schema-v1.json",
        "distributed_execution_contract_schema_sha256": EXPECTED_EXECUTION_SCHEMA_SHA256,
        "distributed_event_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-distributed-event-schema-v1.json",
        "distributed_event_schema_sha256": EXPECTED_EVENT_SCHEMA_SHA256,
        "terminal_evidence_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-terminal-evidence-schema-v1.json",
        "terminal_evidence_schema_sha256": EXPECTED_TERMINAL_SCHEMA_SHA256,
        "actual_execution_contract_instance_present": False,
        "actual_terminal_evidence_present": False,
    }
    assert value["external_checkpoint"] == {
        "substage": "T22_A1_R",
        "independent_of_a1_h_admission": True,
        "candidate": "SIGSTORE_REKOR_HASHEDREKORD",
        "public_irreversible_output": True,
        "currently_authorized": False,
        "claim_if_later_authorized": "PUBLIC_TRANSPARENCY_LOG_INCLUSION_AND_FORK_VISIBILITY_ONLY",
        "monotonic_compare_and_swap_claim": False,
        "rollback_prevention_claim": False,
        "s20_external_checkpoint_satisfied": False,
    }
    assert value["claim_ceiling"] == {
        "admissible_after_pass": "THREE_DISTINCT_PHYSICAL_HOST_PLACEMENT_AND_ONE_HOST_SCOPED_OWNED_SERVICE_SET_LOSS_RECOVERY_NONPRODUCTION",
        "host_power_loss_proved": False,
        "site_power_network_independence_proved": False,
        "storage_device_durability_proved": False,
        "provider_durability_proved": False,
        "external_anti_rollback_proved": False,
        "production_admissible": False,
    }
    assert sha256_file(SCHEMA_PATH) == EXPECTED_SCHEMA_SHA256
    assert sha256_file(EXECUTION_SCHEMA_PATH) == EXPECTED_EXECUTION_SCHEMA_SHA256
    assert sha256_file(EVENT_SCHEMA_PATH) == EXPECTED_EVENT_SCHEMA_SHA256
    assert sha256_file(TERMINAL_SCHEMA_PATH) == EXPECTED_TERMINAL_SCHEMA_SHA256
    assert sha256_file(COLLECTION_CHALLENGE_SCHEMA_PATH) == EXPECTED_COLLECTION_CHALLENGE_SCHEMA_SHA256
    assert value["contract_sha256"] == domain_digest(CONTRACT_DOMAIN, value, "contract_sha256")


def validate_proposal(value: dict, contract: dict) -> None:
    assert set(value) == {
        "schema", "state", "track_id", "decision_requested_after_inputs_complete",
        "current_observation", "required_owner_inputs", "scope_before_exact_owner_signature",
        "admission_contract", "signing", "claims", "proposal_sha256",
    }
    assert value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.owner_decision_proposal.v1"
    assert value["state"] == "BLOCKED_AWAITING_EXACT_DOMAIN_INPUTS_AND_OWNER_DECISION"
    assert value["track_id"] == "SELF_HOSTED_ETCD_OPENBAO_THREE_DOMAIN"
    assert value["decision_requested_after_inputs_complete"] == "AUTHORIZE_T22_A1_H_THREE_HOST_NONPRODUCTION_CANARY_ONLY"
    assert value["current_observation"] == {
        "observed_at": "2026-07-22",
        "coordinator_hostname": "tb14",
        "coordinator_identity_binding": "PRIVATE_FRESH_DOMAIN_ATTESTATION_REQUIRED_NOT_REPOSITORY_EMBEDDED",
        "aio2_tb14_alias_policy": "COLLAPSE_TO_ONE_DOMAIN_UNTIL_DISTINCTNESS_IS_PROVED",
        "alias_equivalence_is_physical_proof": False,
        "current_validated_domain_count": 1,
        "known_distinct_physical_host_candidate_upper_bound": 2,
        "mac_candidate": {
            "hostname": "maxiaodeMac-Pro.local",
            "historical_evidence_date": "2026-06-22",
            "historical_evidence_path": "docs/reports/goal-c-u/2026-06-22-mac-standing-continuity-dashboard.md",
            "current_attestation_present": False,
        },
        "third_domain": "MISSING",
    }
    assert value["required_owner_inputs"] == {
        "third_domain_mode": "UNSELECTED_OWNER_PHYSICAL_OR_CLOUD_VM",
        "t22_a1_owner_public_key_sha256": None,
        "cloud_provider_region_zone_instance_type_if_selected": None,
        "spend_limit_usd_if_cloud_selected": None,
        "exact_three_domain_attestation_packet_sha256_set": None,
        "exact_three_domain_collection_challenge_sha256_set": None,
        "exact_private_overlay_peer_endpoint_set_sha256": None,
        "exact_private_overlay_acl_receipt_sha256": None,
        "fault_target_domain": None,
        "exact_distributed_execution_contract_content_sha256": None,
        "t22_a1_r_public_rekor_submission": "SEPARATE_DECISION_REQUIRED",
    }
    assert value["scope_before_exact_owner_signature"] == {
        "stable_host_identity_read": False,
        "credential_access": False,
        "external_host_connection": False,
        "provider_or_cloud_api_access": False,
        "network_overlay_configuration_change": False,
        "public_transparency_log_output": False,
        "spend_authorized_usd": 0,
        "service_processes_started": 0,
        "faults_injected": 0,
        "production_or_customer_data": False,
        "host_global_network_mutation": False,
    }
    assert value["admission_contract"] == {
        "path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-three-domain-admission-contract-v1.json",
        "schema": contract["schema"],
        "contract_sha256": contract["contract_sha256"],
    }
    assert value["signing"] == {
        "owner_id": "pallasting",
        "owner_role": "PROJECT_OWNER",
        "signature_scheme": "OPENSSH_SSHSIG_ED25519",
        "signature_namespace": "agent-bridge-t22-a1-owner-v1",
        "owner_public_key_sha256": None,
        "exact_payload_generated": False,
        "owner_signature_verified": False,
    }
    assert value["claims"] == {
        "three_distinct_physical_hosts_validated": False,
        "three_failure_domain_execution_authorized": False,
        "external_anti_rollback_evidence": False,
        "cloud_or_provider_authorized": False,
        "nonzero_spend_authorized": False,
        "production_admissible": False,
    }
    assert value["proposal_sha256"] == domain_digest(PROPOSAL_DOMAIN, value, "proposal_sha256")


def load_and_validate() -> tuple[dict, dict, dict]:
    schema = json.loads(SCHEMA_PATH.read_text())
    contract = json.loads(CONTRACT_PATH.read_text())
    proposal = json.loads(PROPOSAL_PATH.read_text())
    validate_attestation_schema(schema)
    validate_contract(contract)
    validate_proposal(proposal, contract)
    return schema, contract, proposal


def inspect() -> dict:
    _, contract, proposal = load_and_validate()
    local_coordinator_observed = socket.gethostname() == proposal["current_observation"]["coordinator_hostname"]
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.three_domain_preflight_receipt.v0",
        "status": STATUS,
        "host": socket.gethostname(),
        "platform": platform.system(),
        "local_coordinator_observed": local_coordinator_observed,
        "stable_host_identity_read": False,
        "required_domain_count": contract["domain_admission"]["required_domain_count"],
        "current_validated_domain_count": proposal["current_observation"]["current_validated_domain_count"],
        "missing_current_domain_attestation_count": 2,
        "known_distinct_physical_host_candidate_upper_bound": proposal["current_observation"]["known_distinct_physical_host_candidate_upper_bound"],
        "aio2_and_tb14_counted_as_one_domain": True,
        "alias_equivalence_is_physical_proof": False,
        "third_domain_mode_selected": False,
        "exact_endpoint_set_present": False,
        "exact_acl_receipt_present": False,
        "owner_signature_verified": False,
        "credentials_accessed": False,
        "external_hosts_contacted": 0,
        "provider_apis_accessed": 0,
        "network_accessed": False,
        "spend_authorized_usd": 0,
        "spend_usd": 0,
        "services_started": 0,
        "faults_injected": 0,
        "public_transparency_entries_created": 0,
        "external_checkpoint_authorized": False,
        "three_failure_domain_evidence": False,
        "external_anti_rollback_evidence": False,
        "production_admissible": False,
        "attestation_schema_sha256": EXPECTED_SCHEMA_SHA256,
        "collection_challenge_schema_sha256": EXPECTED_COLLECTION_CHALLENGE_SCHEMA_SHA256,
        "owner_trust_anchor_present": False,
        "distributed_execution_contract_schema_sha256": EXPECTED_EXECUTION_SCHEMA_SHA256,
        "distributed_event_schema_sha256": EXPECTED_EVENT_SCHEMA_SHA256,
        "terminal_evidence_schema_sha256": EXPECTED_TERMINAL_SCHEMA_SHA256,
        "actual_execution_contract_instance_present": False,
        "actual_terminal_evidence_present": False,
        "contract_sha256": contract["contract_sha256"],
        "proposal_sha256": proposal["proposal_sha256"],
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True, separators=(",", ":")))
