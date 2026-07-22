"""Directed fail-closed checks for the T22-A1 admission preflight."""
from __future__ import annotations

import copy
import importlib.util
import json
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_three_domain_preflight_v1.py"
spec = importlib.util.spec_from_file_location("t22a1preflight", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

schema, contract, proposal = module.load_and_validate()


def rejected_contract(mutate) -> None:  # noqa: ANN001
    candidate = copy.deepcopy(contract)
    mutate(candidate)
    candidate["contract_sha256"] = module.domain_digest(module.CONTRACT_DOMAIN, candidate, "contract_sha256")
    try:
        module.validate_contract(candidate)
    except (AssertionError, KeyError, TypeError):
        return
    raise AssertionError("unsafe contract mutation admitted after self-digest recomputation")


def rejected_proposal(mutate) -> None:  # noqa: ANN001
    candidate = copy.deepcopy(proposal)
    mutate(candidate)
    candidate["proposal_sha256"] = module.domain_digest(module.PROPOSAL_DOMAIN, candidate, "proposal_sha256")
    try:
        module.validate_proposal(candidate, contract)
    except (AssertionError, KeyError, TypeError):
        return
    raise AssertionError("unsafe proposal mutation admitted after self-digest recomputation")


contract_mutations = (
    lambda x: x.update(state="EXECUTION_AUTHORIZED"),
    lambda x: x["domain_admission"].update(required_domain_count=2),
    lambda x: x["domain_admission"].update(required_current_attestation_count=2),
    lambda x: x["domain_admission"].update(required_distinct_hardware_identity_count=2),
    lambda x: x["domain_admission"].update(required_distinct_domain_signing_key_count=1),
    lambda x: x["domain_admission"].update(known_alias_equivalence_classes=[]),
    lambda x: x["domain_admission"].update(candidate_self_reports_are_authoritative=True),
    lambda x: x["network"].update(public_listeners_allowed=True),
    lambda x: x["network"].update(ambient_overlay_credentials_access_allowed=True),
    lambda x: x["network"].update(runner_provisions_or_joins_overlay=True),
    lambda x: x["fault"]["allowed_actions"].append("HOST_REBOOT"),
    lambda x: x["fault"]["forbidden_actions"].remove("PROVIDER_INSTANCE_STOP"),
    lambda x: x["evidence"].update(raw_credentials_endpoints_or_bootstrap_secrets_in_repository_or_receipts_allowed=True),
    lambda x: x["future_execution_evidence_contracts"].update(distributed_execution_contract_schema_sha256="1" * 64),
    lambda x: x["future_execution_evidence_contracts"].update(domain_collection_challenge_schema_sha256="1" * 64),
    lambda x: x["future_execution_evidence_contracts"].update(attestation_set_countersignature_schema_sha256="1" * 64),
    lambda x: x["future_execution_evidence_contracts"].update(private_endpoint_manifest_schema_sha256="1" * 64),
    lambda x: x["future_execution_evidence_contracts"].update(runtime_credential_manifest_schema_sha256="1" * 64),
    lambda x: x["future_execution_evidence_contracts"].update(domain_agent_message_schema_sha256="1" * 64),
    lambda x: x["future_execution_evidence_contracts"].update(runtime_preparation_challenge_schema_sha256="1" * 64),
    lambda x: x["future_execution_evidence_contracts"].update(distributed_event_schema_path="unsafe.json"),
    lambda x: x["future_execution_evidence_contracts"].update(domain_runtime_readiness_schema_sha256="1" * 64),
    lambda x: x["future_execution_evidence_contracts"].update(source_bound_cross_host_runner_present=True),
    lambda x: x["future_execution_evidence_contracts"].update(three_domain_runtime_readiness_contract_present=False),
    lambda x: x["future_execution_evidence_contracts"].update(three_domain_credential_placement_proof_present=True),
    lambda x: x["future_execution_evidence_contracts"].update(actual_execution_contract_instance_present=True),
    lambda x: x["future_execution_evidence_contracts"].update(actual_terminal_evidence_present=True),
    lambda x: x["external_checkpoint"].update(currently_authorized=True),
    lambda x: x["external_checkpoint"].update(monotonic_compare_and_swap_claim=True),
    lambda x: x["external_checkpoint"].update(s20_external_checkpoint_satisfied=True),
    lambda x: x["claim_ceiling"].update(host_power_loss_proved=True),
    lambda x: x["claim_ceiling"].update(external_anti_rollback_proved=True),
    lambda x: x["claim_ceiling"].update(production_admissible=True),
    lambda x: x.update(unexpected="field"),
)
for mutation in contract_mutations:
    rejected_contract(mutation)

proposal_mutations = (
    lambda x: x.update(state="AUTHORIZED"),
    lambda x: x["current_observation"].update(aio2_tb14_alias_policy="COUNT_AS_TWO"),
    lambda x: x["current_observation"].update(alias_equivalence_is_physical_proof=True),
    lambda x: x["current_observation"].update(current_validated_domain_count=3),
    lambda x: x["current_observation"]["mac_candidate"].update(current_attestation_present=True),
    lambda x: x["current_observation"].update(third_domain="PRESENT"),
    lambda x: x["required_owner_inputs"].update(third_domain_mode="CLOUD_VM"),
    lambda x: x["required_owner_inputs"].update(spend_limit_usd_if_cloud_selected=10),
    lambda x: x["scope_before_exact_owner_signature"].update(credential_access=True),
    lambda x: x["scope_before_exact_owner_signature"].update(external_host_connection=True),
    lambda x: x["scope_before_exact_owner_signature"].update(provider_or_cloud_api_access=True),
    lambda x: x["scope_before_exact_owner_signature"].update(public_transparency_log_output=True),
    lambda x: x["scope_before_exact_owner_signature"].update(spend_authorized_usd=1),
    lambda x: x["required_owner_inputs"].update(exact_distributed_execution_contract_content_sha256="1" * 64),
    lambda x: x["required_owner_inputs"].update(t22_a1_owner_public_key_sha256="1" * 64),
    lambda x: x["required_owner_inputs"].update(exact_private_endpoint_manifest_content_sha256="1" * 64),
    lambda x: x["required_owner_inputs"].update(exact_runtime_credential_manifest_content_sha256="1" * 64),
    lambda x: x["required_owner_inputs"].update(coordinator_runtime_public_key_sha256="1" * 64),
    lambda x: x["required_owner_inputs"].update(exact_runtime_preparation_challenge_content_sha256="1" * 64),
    lambda x: x["required_owner_inputs"].update(exact_attestation_set_countersignature_content_sha256="1" * 64),
    lambda x: x["required_owner_inputs"].update(exact_attestation_set_countersignature_signature_sha256="1" * 64),
    lambda x: x["required_owner_inputs"].update(exact_owner_countersigned_attestation_set_receipt_sha256="1" * 64),
    lambda x: x["required_owner_inputs"].update(exact_runtime_preparation_owner_signature_sha256="1" * 64),
    lambda x: x["required_owner_inputs"].update(exact_runtime_preparation_terminal_receipt_sha256="1" * 64),
    lambda x: x["required_owner_inputs"].update(credential_initial_placement_mode="CENTRAL_GENERATION_AND_OWNER_MEDIATED_PLACEMENT"),
    lambda x: x["required_owner_inputs"].update(exact_three_domain_runtime_readiness_packet_sha256_set=["1" * 64] * 3),
    lambda x: x["required_owner_inputs"].update(exact_three_domain_runtime_readiness_signature_sha256_set=["1" * 64] * 3),
    lambda x: x["required_owner_inputs"].update(exact_source_bound_runner_and_executor_sha256_set=["1" * 64] * 2),
    lambda x: x["required_owner_inputs"].update(exact_owner_execution_signature_sha256="1" * 64),
    lambda x: x["scope_before_exact_owner_signature"].update(private_manifest_instances_read=True),
    lambda x: x["scope_before_exact_owner_signature"].update(runtime_credential_files_read=True),
    lambda x: x["scope_before_exact_owner_signature"].update(ephemeral_runtime_material_generated=True),
    lambda x: x["scope_before_exact_owner_signature"].update(agent_listeners_started=1),
    lambda x: x["scope_before_exact_owner_signature"].update(stable_host_identity_read=True),
    lambda x: x["signing"].update(exact_payload_generated=True),
    lambda x: x["signing"].update(owner_public_key_sha256="1" * 64),
    lambda x: x["signing"].update(owner_signature_verified=True),
    lambda x: x["claims"].update(three_distinct_physical_hosts_validated=True),
    lambda x: x["claims"].update(three_failure_domain_execution_authorized=True),
    lambda x: x["claims"].update(external_anti_rollback_evidence=True),
    lambda x: x["claims"].update(cloud_or_provider_authorized=True),
    lambda x: x["claims"].update(nonzero_spend_authorized=True),
    lambda x: x["claims"].update(production_admissible=True),
)
for mutation in proposal_mutations:
    rejected_proposal(mutation)

schema_mutations = (
    lambda x: x.update(additionalProperties=True),
    lambda x: x["$defs"]["hashing_contract"]["properties"]["candidate_reported_matches_authoritative"].update(const=True),
    lambda x: x["$defs"]["hashing_contract"]["properties"]["self_hash_field_excluded"].update(const=False),
    lambda x: x["$defs"]["operator_binding"]["properties"]["private_key_exported"].update(const=True),
    lambda x: x["$defs"]["network_binding"]["properties"]["public_listener_allowed"].update(const=True),
)
for mutation in schema_mutations:
    unsafe_schema = copy.deepcopy(schema)
    mutation(unsafe_schema)
    try:
        module.validate_attestation_schema(unsafe_schema)
    except AssertionError:
        continue
    raise AssertionError("unsafe attestation schema mutation admitted")

original_socket = socket.socket
socket.socket = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network socket constructed"))
try:
    receipt = module.inspect()
finally:
    socket.socket = original_socket

assert receipt["status"] == module.STATUS
assert receipt["local_coordinator_observed"] is True
assert receipt["stable_host_identity_read"] is False
assert receipt["required_domain_count"] == 3
assert receipt["current_validated_domain_count"] == 1
assert receipt["missing_current_domain_attestation_count"] == 2
assert receipt["known_distinct_physical_host_candidate_upper_bound"] == 2
assert receipt["aio2_and_tb14_counted_as_one_domain"] is True
assert receipt["alias_equivalence_is_physical_proof"] is False
assert receipt["credentials_accessed"] is False
assert receipt["external_hosts_contacted"] == receipt["provider_apis_accessed"] == 0
assert receipt["network_accessed"] is False
assert receipt["spend_usd"] == receipt["services_started"] == receipt["faults_injected"] == 0
assert receipt["public_transparency_entries_created"] == 0
assert receipt["three_failure_domain_evidence"] is False
assert receipt["external_anti_rollback_evidence"] is False
assert receipt["production_admissible"] is False

print("t22_a1_three_domain_preflight_check\tpass")
print(f"directed_negative_test_count\t{len(contract_mutations) + len(proposal_mutations) + len(schema_mutations)}")
print("network_accessed\tfalse")
print("credentials_accessed\tfalse")
print("external_hosts_contacted\t0")
print("services_started\t0")
print("public_transparency_entries_created\t0")
