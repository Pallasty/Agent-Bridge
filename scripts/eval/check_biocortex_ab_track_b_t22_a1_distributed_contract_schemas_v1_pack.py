"""Synthetic offline KATs for the T22-A1 distributed contract schemas."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "docs/design/fixtures"
EXECUTION_SCHEMA_PATH = FIXTURES / "biocortex-ab-track-b-t22-a1-distributed-execution-contract-schema-v1.json"
EVENT_SCHEMA_PATH = FIXTURES / "biocortex-ab-track-b-t22-a1-distributed-event-schema-v1.json"
TERMINAL_SCHEMA_PATH = FIXTURES / "biocortex-ab-track-b-t22-a1-terminal-evidence-schema-v1.json"


def load_validator(path: Path) -> Draft202012Validator:
    schema = json.loads(path.read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def digest(label: str) -> str:
    return hashlib.sha256(f"T22_A1_SYNTHETIC_SCHEMA_KAT_ONLY:{label}".encode()).hexdigest()


def rejected(validator: Draft202012Validator, base: dict, mutate) -> None:  # noqa: ANN001
    candidate = copy.deepcopy(base)
    mutate(candidate)
    if not list(validator.iter_errors(candidate)):
        raise AssertionError("unsafe synthetic schema mutation admitted")


execution_validator = load_validator(EXECUTION_SCHEMA_PATH)
event_validator = load_validator(EVENT_SCHEMA_PATH)
terminal_validator = load_validator(TERMINAL_SCHEMA_PATH)

hashing_execution = {
    "hash_algorithm": "SHA-256",
    "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
    "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/distributed-execution-contract/v1",
    "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256",
    "self_hash_field": "content_sha256",
    "self_hash_field_excluded": True,
    "detached_owner_signature_covers_complete_canonical_packet": True,
    "cross_field_semantic_validation_required": True,
}

execution = {
    "schema": "agent_bridge.biocortex.track_b.t22_a1.distributed_execution_contract.v1",
    "packet_kind": "T22_A1_H_FINAL_UNSIGNED_EXECUTION_CONTRACT",
    "hashing_contract": hashing_execution,
    "run_id": "t22-a1-20260722T210000.000000z-123456789abc",
    "source_commit": "a" * 40,
    "issued_at": "2026-07-22T21:00:00Z",
    "expires_at": "2026-07-23T01:00:00Z",
    "authorization": {
        "owner_id": "pallasting",
        "owner_role": "PROJECT_OWNER",
        "signature_scheme": "OPENSSH_SSHSIG_ED25519",
        "signature_namespace": "agent-bridge-t22-a1-owner-v1",
        "verified_unexpired_owner_signature_required": True,
        "exact_source_commit_required": True,
        "clean_tracked_tree_required": True,
        "one_run_per_authorization_content_sha256": True,
        "maximum_runtime_seconds": 14400,
        "automatic_retry_allowed": False,
    },
    "admission_bindings": {
        "admission_contract_sha256": digest("admission-contract"),
        "owner_decision_proposal_sha256": digest("proposal"),
        "domain_attestation_schema_sha256": digest("attestation-schema"),
        "exact_three_domain_attestation_packet_set_sha256": digest("attestation-set"),
        "attestation_set_countersignature_content_sha256": digest("attestation-set-countersignature"),
        "owner_attestation_set_countersignature_signature_sha256": digest("attestation-set-owner-signature"),
        "owner_countersigned_attestation_set_receipt_sha256": digest("attestation-set-admission-receipt"),
        "admission_bundle_reverification_receipt_sha256": digest("attestation-set-bundle-reverification"),
        "domain_bindings": [
            {
                "domain_id": f"domain-{number}",
                "attestation_packet_sha256": digest(f"attestation:{number}"),
                "attestation_signature_sha256": digest(f"attestation-signature:{number}"),
                "domain_public_key_sha256": digest(f"domain-key:{number}"),
            }
            for number in (1, 2, 3)
        ],
        "all_domain_attestation_signatures_verified": True,
        "all_domain_attestations_current": True,
        "all_domain_distinctness_checks_passed": True,
        "owner_countersignature_over_exact_packet_set_verified": True,
    },
    "budget": {
        "mode": "THREE_OWNER_PHYSICAL_HOSTS_ZERO_SPEND",
        "provider": None,
        "region": None,
        "zone": None,
        "instance_type": None,
        "maximum_spend_usd_cents": 0,
    },
    "network": {
        "transport": "OWNER_MANAGED_PRIVATE_OVERLAY",
        "peer_endpoint_set_sha256": digest("endpoint-set"),
        "acl_policy_receipt_sha256": digest("acl"),
        "raw_endpoints_embedded": False,
        "overlay_credentials_embedded": False,
        "public_listeners_allowed": False,
        "host_global_firewall_or_route_mutation_allowed": False,
        "runner_provisions_or_joins_overlay": False,
    },
    "private_runtime": {
        "private_endpoint_manifest_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-private-endpoint-manifest-schema-v1.json",
        "private_endpoint_manifest_schema_sha256": "8741f130384d246077c281a8200a174f92c63fda565c9384ab7d6edc0f723953",
        "private_endpoint_manifest_content_sha256": digest("private-endpoint-manifest"),
        "runtime_credential_manifest_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-runtime-credential-manifest-schema-v1.json",
        "runtime_credential_manifest_schema_sha256": "b729e53c775af8350badd72660b8adb36e97ca717228e129411c2b5c4ebb3d8a",
        "runtime_credential_manifest_content_sha256": digest("runtime-credential-manifest"),
        "domain_agent_message_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-domain-agent-message-schema-v1.json",
        "domain_agent_message_schema_sha256": "92d8a9e59e62b56afec200caf0e25517c7bf3322bc24078024d4c52993e9e3ee",
        "coordinator_runtime_public_key_sha256": digest("coordinator-runtime-key"),
        "mutual_tls_required": True,
        "certificate_and_key_verification_required": True,
        "credentials_read_only_after_owner_signature": True,
        "domain_message_signatures_required": True,
        "agent_listeners_bind_exact_overlay_ip_only": True,
        "arbitrary_remote_shell_allowed": False,
        "raw_endpoint_or_credential_manifest_in_repository_or_receipts_allowed": False,
    },
    "topology": {
        "domains": [
            {"domain_id": "domain-1", "role": "COORDINATOR_VOTER", "etcd_member": "etcd-1", "openbao_member": "bao-1", "owned_process_count": 2},
            {"domain_id": "domain-2", "role": "PARTICIPANT_VOTER", "etcd_member": "etcd-2", "openbao_member": "bao-2", "owned_process_count": 2},
            {"domain_id": "domain-3", "role": "PARTICIPANT_VOTER", "etcd_member": "etcd-3", "openbao_member": "bao-3", "owned_process_count": 2},
        ],
        "etcd_voter_count": 3,
        "openbao_voter_count": 3,
        "coordinator_domain_id": "domain-1",
        "production_or_customer_data_allowed": False,
    },
    "fault": {
        "id": "ONE_DOMAIN_ALL_OWNED_CLUSTER_SERVICES_STOP_AND_RESTART",
        "target_domain_id": "domain-2",
        "target_selection": "OBSERVED_NON_COORDINATOR_VOTER_DOMAIN",
        "allowed_actions": ["OWNED_PROCESS_STOP", "OWNED_PROCESS_KILL_AFTER_TIMEOUT", "OWNED_PROCESS_RESTART"],
        "forbidden_actions": ["HOST_REBOOT", "HOST_POWER_OFF", "HOST_GLOBAL_IPTABLES_OR_TC", "BLOCK_DEVICE_MUTATION", "PROVIDER_INSTANCE_STOP"],
        "required_observation": "SURVIVING_TWO_DOMAINS_RETAIN_QUORUM_AND_VERIFY_PREFAULT_STATE_THEN_STOPPED_DOMAIN_REJOINS",
    },
    "evidence_contract": {
        "distributed_event_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-distributed-event-schema-v1.json",
        "distributed_event_schema_sha256": digest("event-schema"),
        "terminal_evidence_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-terminal-evidence-schema-v1.json",
        "terminal_evidence_schema_sha256": digest("terminal-schema"),
        "coordinator_hash_chain_required": True,
        "source_domain_detached_signatures_required": True,
        "per_domain_cleanup_receipts_required": True,
        "exact_secret_value_scan_required": True,
        "raw_credentials_endpoints_or_bootstrap_secrets_allowed": False,
    },
    "claims": {
        "maximum_success_claim": "THREE_DISTINCT_PHYSICAL_HOST_PLACEMENT_AND_ONE_HOST_SCOPED_OWNED_SERVICE_SET_LOSS_RECOVERY_NONPRODUCTION",
        "host_power_loss_proved": False,
        "site_power_network_independence_proved": False,
        "storage_device_durability_proved": False,
        "provider_durability_proved": False,
        "external_anti_rollback_proved": False,
        "production_admissible": False,
        "t22_a1_r_authorized": False,
    },
    "content_sha256": digest("execution-contract"),
}
execution_validator.validate(execution)

execution_mutations = (
    lambda x: x.update(packet_kind="EXECUTE_NOW"),
    lambda x: x["hashing_contract"].update(self_hash_field_excluded=False),
    lambda x: x["authorization"].update(verified_unexpired_owner_signature_required=False),
    lambda x: x["authorization"].update(one_run_per_authorization_content_sha256=False),
    lambda x: x["authorization"].update(maximum_runtime_seconds=14401),
    lambda x: x["authorization"].update(automatic_retry_allowed=True),
    lambda x: x["admission_bindings"]["domain_bindings"].pop(),
    lambda x: x["admission_bindings"]["domain_bindings"][1].update(domain_id="domain-1"),
    lambda x: x["admission_bindings"].update(all_domain_attestations_current=False),
    lambda x: x["admission_bindings"].update(owner_countersignature_over_exact_packet_set_verified=False),
    lambda x: x["admission_bindings"].pop("attestation_set_countersignature_content_sha256"),
    lambda x: x["admission_bindings"].pop("owner_attestation_set_countersignature_signature_sha256"),
    lambda x: x["admission_bindings"].pop("owner_countersigned_attestation_set_receipt_sha256"),
    lambda x: x["admission_bindings"].pop("admission_bundle_reverification_receipt_sha256"),
    lambda x: x["budget"].update(maximum_spend_usd_cents=1),
    lambda x: x["network"].update(raw_endpoints_embedded=True),
    lambda x: x["network"].update(overlay_credentials_embedded=True),
    lambda x: x["network"].update(public_listeners_allowed=True),
    lambda x: x["network"].update(runner_provisions_or_joins_overlay=True),
    lambda x: x["private_runtime"].update(private_endpoint_manifest_schema_sha256=digest("wrong-schema")),
    lambda x: x["private_runtime"].update(runtime_credential_manifest_schema_sha256=digest("wrong-schema")),
    lambda x: x["private_runtime"].update(domain_agent_message_schema_sha256=digest("wrong-schema")),
    lambda x: x["private_runtime"].update(mutual_tls_required=False),
    lambda x: x["private_runtime"].update(certificate_and_key_verification_required=False),
    lambda x: x["private_runtime"].update(credentials_read_only_after_owner_signature=False),
    lambda x: x["private_runtime"].update(domain_message_signatures_required=False),
    lambda x: x["private_runtime"].update(agent_listeners_bind_exact_overlay_ip_only=False),
    lambda x: x["private_runtime"].update(arbitrary_remote_shell_allowed=True),
    lambda x: x["private_runtime"].update(raw_endpoint_or_credential_manifest_in_repository_or_receipts_allowed=True),
    lambda x: x["topology"].update(etcd_voter_count=2),
    lambda x: x["topology"]["domains"][1].update(role="COORDINATOR_VOTER"),
    lambda x: x["fault"].update(target_domain_id="domain-1"),
    lambda x: x["fault"]["allowed_actions"].append("HOST_REBOOT"),
    lambda x: x["evidence_contract"].update(raw_credentials_endpoints_or_bootstrap_secrets_allowed=True),
    lambda x: x["claims"].update(host_power_loss_proved=True),
    lambda x: x["claims"].update(external_anti_rollback_proved=True),
    lambda x: x["claims"].update(production_admissible=True),
    lambda x: x.update(unexpected="field"),
)
for mutation in execution_mutations:
    rejected(execution_validator, execution, mutation)

cloud_execution = copy.deepcopy(execution)
cloud_execution["budget"] = {
    "mode": "EXACT_OWNER_AUTHORIZED_CLOUD_VM",
    "provider": "synthetic-provider",
    "region": "synthetic-region",
    "zone": "synthetic-zone",
    "instance_type": "synthetic-type",
    "maximum_spend_usd_cents": 100,
}
execution_validator.validate(cloud_execution)
rejected(execution_validator, cloud_execution, lambda x: x["budget"].update(zone=""))
rejected(execution_validator, cloud_execution, lambda x: x["budget"].update(maximum_spend_usd_cents=0))
rejected(execution_validator, cloud_execution, lambda x: x["budget"].update(maximum_spend_usd_cents=100.5))

event = {
    "schema": "agent_bridge.biocortex.track_b.t22_a1.distributed_event.v1",
    "run_id": execution["run_id"],
    "source_commit": execution["source_commit"],
    "execution_contract_sha256": execution["content_sha256"],
    "sequence": 0,
    "previous_event_sha256": "0" * 64,
    "observed_at": "2026-07-22T21:00:01Z",
    "source_domain_id": "domain-1",
    "event_type": "EXECUTION_PREFLIGHT_ACCEPTED",
    "observation_sha256": digest("observation"),
    "source_domain_evidence": {
        "attestation_packet_sha256": digest("attestation:1"),
        "domain_event_payload_sha256": digest("domain-event"),
        "detached_signature_sha256": digest("domain-event-signature"),
        "domain_public_key_sha256": digest("domain-key:1"),
        "signature_scheme": "OPENSSH_SSHSIG_ED25519",
        "signature_namespace": "agent-bridge-t22-a1-domain-event-v1",
        "signature_verified": True,
    },
    "contains_raw_endpoint": False,
    "contains_secret_material": False,
    "event_sha256": digest("event"),
}
event_validator.validate(event)
second_event = copy.deepcopy(event)
second_event.update(sequence=1, previous_event_sha256=event["event_sha256"], event_type="DOMAIN_PROCESS_STARTED")
event_validator.validate(second_event)

event_mutations = (
    lambda x: x.update(sequence=-1),
    lambda x: x.update(previous_event_sha256=digest("not-genesis")),
    lambda x: x.update(source_domain_id="domain-4"),
    lambda x: x.update(event_type="HOST_POWER_OFF"),
    lambda x: x["source_domain_evidence"].update(signature_verified=False),
    lambda x: x["source_domain_evidence"].update(signature_namespace="wrong"),
    lambda x: x.update(contains_raw_endpoint=True),
    lambda x: x.update(contains_secret_material=True),
    lambda x: x.update(observed_at="not-a-time"),
    lambda x: x.update(unexpected="field"),
)
for mutation_index, mutation in enumerate(event_mutations):
    try:
        rejected(event_validator, event, mutation)
    except AssertionError as error:
        raise AssertionError(f"unsafe event mutation admitted at index {mutation_index}") from error
rejected(event_validator, second_event, lambda x: x.update(previous_event_sha256="0" * 64))

domain_rows = [
    {
        "domain_id": f"domain-{number}",
        "attestation_packet_sha256": digest(f"attestation:{number}"),
        "attestation_signature_verified": True,
        "signed_event_chain_head_sha256": digest(f"domain-chain:{number}"),
        "domain_event_count": 5,
        "domain_event_signatures_verified": True,
        "preflight_receipt_sha256": digest(f"preflight:{number}"),
        "process_receipt_sha256": digest(f"process:{number}"),
        "cleanup_receipt_sha256": digest(f"cleanup:{number}"),
        "owned_process_log_set_sha256": digest(f"logs:{number}"),
        "owned_process_logs_hashed": True,
        "cleanup_receipt_verified": True,
        "all_owned_processes_stopped": True,
        "all_owned_ports_released": True,
        "secret_value_scan_passed": True,
    }
    for number in (1, 2, 3)
]

terminal = {
    "schema": "agent_bridge.biocortex.track_b.t22_a1.terminal_evidence.v1",
    "packet_kind": "T22_A1_H_TERMINAL_EVIDENCE",
    "hashing_contract": {
        "hash_algorithm": "SHA-256",
        "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
        "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/terminal-evidence/v1",
        "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256",
        "self_hash_field": "content_sha256",
        "self_hash_field_excluded": True,
        "cross_field_semantic_validation_required": True,
    },
    "status": "PASS_T22_A1_THREE_HOST_OWNED_SERVICE_SET_LOSS_RECOVERY",
    "failure_code": None,
    "run_id": execution["run_id"],
    "source_commit": execution["source_commit"],
    "bindings": {
        "execution_contract_sha256": execution["content_sha256"],
        "owner_authorization_content_sha256": digest("owner-authorization"),
        "admission_contract_sha256": digest("admission-contract"),
        "owner_decision_proposal_sha256": digest("proposal"),
        "exact_three_domain_attestation_packet_set_sha256": digest("attestation-set"),
        "peer_endpoint_set_sha256": digest("endpoint-set"),
        "acl_policy_receipt_sha256": digest("acl"),
    },
    "timing": {
        "started_at": "2026-07-22T21:00:00Z",
        "completed_at": "2026-07-22T21:30:00Z",
        "runtime_seconds": 1800,
        "signed_maximum_runtime_seconds": 14400,
        "runtime_within_signed_limit": True,
        "maximum_observed_clock_skew_seconds": 2,
        "clock_skew_within_bound": True,
    },
    "domains": domain_rows,
    "cluster_evidence": {
        "etcd_distinct_voter_domain_count": 3,
        "openbao_distinct_voter_domain_count": 3,
        "linearizable_authorize_consume_observed": True,
        "replay_consume_rejected": True,
        "prefault_transit_signature_created": True,
        "fault_target_domain_id": "domain-2",
        "fault_target_was_non_coordinator": True,
        "target_owned_service_set_stopped": True,
        "surviving_two_domain_etcd_quorum_observed": True,
        "surviving_two_domain_openbao_available": True,
        "postfault_transit_signature_verified": True,
        "target_owned_service_set_restarted": True,
        "target_domain_rejoined": True,
    },
    "event_chain": {
        "event_count": 15,
        "event_chain_head_sha256": digest("coordinator-chain"),
        "canonical_coordinator_hash_chain_verified": True,
        "all_source_domain_signatures_verified": True,
        "terminal_event_present": True,
    },
    "cleanup": {
        "all_owned_processes_stopped": True,
        "all_owned_ports_released": True,
        "all_domain_cleanup_receipts_verified": True,
        "secret_value_scan_passed": True,
        "host_global_network_mutated": False,
        "ambient_or_external_credentials_accessed": False,
        "public_listeners_created": False,
        "spend_usd_cents": 0,
        "signed_maximum_spend_usd_cents": 0,
        "spend_within_signed_limit": True,
    },
    "claims": {
        "maximum_claim": "THREE_DISTINCT_PHYSICAL_HOST_PLACEMENT_AND_ONE_HOST_SCOPED_OWNED_SERVICE_SET_LOSS_RECOVERY_NONPRODUCTION",
        "admissible_claim_earned": True,
        "host_power_loss_proved": False,
        "site_power_network_independence_proved": False,
        "storage_device_durability_proved": False,
        "provider_durability_proved": False,
        "external_anti_rollback_proved": False,
        "production_admissible": False,
    },
    "completed_at": "2026-07-22T21:30:00Z",
    "content_sha256": digest("terminal"),
}
terminal_validator.validate(terminal)

terminal_mutations = (
    lambda x: x.update(failure_code="E_FALSE_PASS"),
    lambda x: x["timing"].update(runtime_seconds=14401),
    lambda x: x["timing"].update(runtime_seconds=1.5),
    lambda x: x["timing"].update(clock_skew_within_bound=False),
    lambda x: x["domains"].pop(),
    lambda x: x["domains"][1].update(domain_id="domain-1"),
    lambda x: x["domains"][0].update(attestation_signature_verified=False),
    lambda x: x["domains"][0].update(domain_event_signatures_verified=False),
    lambda x: x["domains"][0].update(owned_process_logs_hashed=False),
    lambda x: x["domains"][0].update(cleanup_receipt_verified=False),
    lambda x: x["domains"][0].update(all_owned_processes_stopped=False),
    lambda x: x["domains"][0].update(all_owned_ports_released=False),
    lambda x: x["domains"][0].update(secret_value_scan_passed=False),
    lambda x: x["cluster_evidence"].update(etcd_distinct_voter_domain_count=2),
    lambda x: x["cluster_evidence"].update(linearizable_authorize_consume_observed=False),
    lambda x: x["cluster_evidence"].update(replay_consume_rejected=False),
    lambda x: x["cluster_evidence"].update(fault_target_domain_id="domain-1"),
    lambda x: x["cluster_evidence"].update(surviving_two_domain_etcd_quorum_observed=False),
    lambda x: x["cluster_evidence"].update(postfault_transit_signature_verified=False),
    lambda x: x["cluster_evidence"].update(target_domain_rejoined=False),
    lambda x: x["event_chain"].update(event_count=14),
    lambda x: x["event_chain"].update(all_source_domain_signatures_verified=False),
    lambda x: x["cleanup"].update(secret_value_scan_passed=False),
    lambda x: x["cleanup"].update(host_global_network_mutated=True),
    lambda x: x["cleanup"].update(ambient_or_external_credentials_accessed=True),
    lambda x: x["cleanup"].update(public_listeners_created=True),
    lambda x: x["cleanup"].update(spend_usd_cents=0.5),
    lambda x: x["cleanup"].update(spend_within_signed_limit=False),
    lambda x: x["claims"].update(admissible_claim_earned=False),
    lambda x: x["claims"].update(host_power_loss_proved=True),
    lambda x: x["claims"].update(external_anti_rollback_proved=True),
    lambda x: x["claims"].update(production_admissible=True),
    lambda x: x.update(unexpected="field"),
)
for mutation in terminal_mutations:
    rejected(terminal_validator, terminal, mutation)

failed_terminal = copy.deepcopy(terminal)
failed_terminal.update(status="FAIL_T22_A1_DISTRIBUTED_EXECUTION", failure_code="E_SYNTHETIC_FAILURE")
failed_terminal["claims"]["admissible_claim_earned"] = False
failed_terminal["cluster_evidence"]["target_domain_rejoined"] = False
terminal_validator.validate(failed_terminal)
rejected(terminal_validator, failed_terminal, lambda x: x.update(failure_code=None))
rejected(terminal_validator, failed_terminal, lambda x: x["claims"].update(admissible_claim_earned=True))

negative_count = len(execution_mutations) + 3 + len(event_mutations) + 1 + len(terminal_mutations) + 2
print("t22_a1_distributed_contract_schemas_check\tpass")
print(f"directed_negative_test_count\t{negative_count}")
print("real_contract_instances_created\t0")
print("real_terminal_evidence_items_created\t0")
print("real_host_identifiers_read\tfalse")
print("network_accessed\tfalse")
print("credentials_accessed\tfalse")
print("external_hosts_contacted\t0")
print("services_started\t0")
print("faults_injected\t0")
