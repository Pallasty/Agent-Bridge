"""Synthetic offline KATs for T22-A1 private runtime contracts."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_private_runtime_contracts_v1.py"
spec = importlib.util.spec_from_file_location("t22a1privateruntime", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

endpoint_schema, credential_schema, message_schema = module.load_schemas()
SOURCE_COMMIT = "a" * 40
RUN_ID = "t22-a1-20260722T230000.000000z-123456789abc"
NOW = datetime(2026, 7, 22, 23, 0, tzinfo=timezone.utc)
EXECUTION_EXPIRES = NOW + timedelta(hours=4)


def digest(label: str) -> str:
    return hashlib.sha256(f"T22_A1_SYNTHETIC_PRIVATE_RUNTIME_ONLY:{label}".encode()).hexdigest()


def rehash(value: dict, domain: bytes) -> None:
    value.pop("content_sha256", None)
    value["content_sha256"] = module.digest(domain, value)


endpoint = {
    "schema": "agent_bridge.biocortex.track_b.t22_a1.private_endpoint_manifest.v1",
    "packet_kind": "T22_A1_PRIVATE_ENDPOINT_MANIFEST",
    "hashing_contract": {
        "hash_algorithm": "SHA-256",
        "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
        "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/private-endpoint-manifest/v1",
        "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256",
        "self_hash_field": "content_sha256",
        "self_hash_field_excluded": True,
        "cross_field_semantic_validation_required": True,
    },
    "run_id": RUN_ID,
    "source_commit": SOURCE_COMMIT,
    "transport": "OWNER_MANAGED_PRIVATE_OVERLAY",
    "acl_policy_receipt_sha256": digest("acl"),
    "domains": [
        {
            "domain_id": f"domain-{number}",
            "hostname": f"synthetic-host-{number}",
            "overlay_ip": f"100.64.0.{number}",
            "agent_control_port": 29000,
            "etcd_client_port": 2379,
            "etcd_peer_port": 2380,
            "openbao_api_port": 8200,
            "openbao_cluster_port": 8201,
            "bind_exact_overlay_ip_only": True,
            "public_listener_allowed": False,
        }
        for number in (1, 2, 3)
    ],
    "raw_manifest_repository_allowed": False,
    "public_address_allowed": False,
    "dns_resolution_required": False,
}
rehash(endpoint, module.ENDPOINT_DOMAIN)
module.validate_endpoint_manifest(endpoint, endpoint_schema, SOURCE_COMMIT, RUN_ID)


def rejected_endpoint(mutate) -> None:  # noqa: ANN001
    candidate = copy.deepcopy(endpoint)
    mutate(candidate)
    rehash(candidate, module.ENDPOINT_DOMAIN)
    try:
        module.validate_endpoint_manifest(candidate, endpoint_schema, SOURCE_COMMIT, RUN_ID)
    except module.SafeFailure:
        return
    raise AssertionError("unsafe endpoint manifest mutation admitted")


endpoint_mutations = (
    lambda x: x.update(packet_kind="PUBLIC_ENDPOINTS"),
    lambda x: x.update(source_commit="b" * 40),
    lambda x: x.update(transport="PUBLIC_INTERNET"),
    lambda x: x["domains"].pop(),
    lambda x: x["domains"][1].update(domain_id="domain-1"),
    lambda x: x["domains"][1].update(hostname=x["domains"][0]["hostname"]),
    lambda x: x["domains"][1].update(overlay_ip=x["domains"][0]["overlay_ip"]),
    lambda x: x["domains"][0].update(overlay_ip="8.8.8.8"),
    lambda x: x["domains"][0].update(overlay_ip="127.0.0.1"),
    lambda x: x["domains"][0].update(etcd_client_port=29000),
    lambda x: x["domains"][0].update(bind_exact_overlay_ip_only=False),
    lambda x: x["domains"][0].update(public_listener_allowed=True),
    lambda x: x.update(raw_manifest_repository_allowed=True),
    lambda x: x.update(public_address_allowed=True),
    lambda x: x.update(dns_resolution_required=True),
    lambda x: x.update(unexpected="field"),
)
for mutation in endpoint_mutations:
    rejected_endpoint(mutation)


def credential(identity: str, usage: str) -> dict:
    return {
        "identity": identity,
        "certificate_path": f"/private/t22-a1/{identity}.crt",
        "private_key_path": f"/private/t22-a1/{identity}.key",
        "certificate_sha256": digest(f"cert:{identity}"),
        "spki_sha256": digest(f"spki:{identity}"),
        "issuer_spki_sha256": digest("spki:ca"),
        "not_after": "2026-07-23T04:00:00Z",
        "extended_key_usage": [usage],
        "private_key_file_mode": "0600",
        "private_key_export_allowed": False,
    }


credentials = {
    "schema": "agent_bridge.biocortex.track_b.t22_a1.runtime_credential_manifest.v1",
    "packet_kind": "T22_A1_PRIVATE_RUNTIME_CREDENTIAL_MANIFEST",
    "hashing_contract": {
        "hash_algorithm": "SHA-256",
        "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
        "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/runtime-credential-manifest/v1",
        "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256",
        "self_hash_field": "content_sha256",
        "self_hash_field_excluded": True,
        "cross_field_semantic_validation_required": True,
    },
    "run_id": RUN_ID,
    "source_commit": SOURCE_COMMIT,
    "private_endpoint_manifest_sha256": endpoint["content_sha256"],
    "ca": {
        "certificate_path": "/private/t22-a1/ca.crt",
        "certificate_sha256": digest("cert:ca"),
        "spki_sha256": digest("spki:ca"),
        "self_signed_private_run_ca": True,
        "private_key_path_present": False,
    },
    "coordinator": credential("coordinator", "TLS_WEB_CLIENT_AUTHENTICATION"),
    "domains": [credential(f"domain-{number}", "TLS_WEB_SERVER_AUTHENTICATION") for number in (1, 2, 3)],
    "mutual_tls_required": True,
    "certificate_chain_and_key_match_verification_required": True,
    "certificate_valid_through_execution_expiry_required": True,
    "ambient_credential_discovery_allowed": False,
    "credential_paths_in_repository_allowed": False,
    "private_key_material_embedded": False,
}
rehash(credentials, module.CREDENTIAL_DOMAIN)
module.validate_credential_manifest(
    credentials, credential_schema, SOURCE_COMMIT, RUN_ID,
    endpoint["content_sha256"], EXECUTION_EXPIRES,
)


def rejected_credentials(mutate) -> None:  # noqa: ANN001
    candidate = copy.deepcopy(credentials)
    mutate(candidate)
    rehash(candidate, module.CREDENTIAL_DOMAIN)
    try:
        module.validate_credential_manifest(
            candidate, credential_schema, SOURCE_COMMIT, RUN_ID,
            endpoint["content_sha256"], EXECUTION_EXPIRES,
        )
    except module.SafeFailure:
        return
    raise AssertionError("unsafe credential manifest mutation admitted")


credential_mutations = (
    lambda x: x.update(source_commit="b" * 40),
    lambda x: x.update(private_endpoint_manifest_sha256=digest("other-endpoints")),
    lambda x: x["ca"].update(certificate_path="relative/ca.crt"),
    lambda x: x["ca"].update(private_key_path_present=True),
    lambda x: x["coordinator"].update(extended_key_usage=["TLS_WEB_SERVER_AUTHENTICATION"]),
    lambda x: x["domains"][0].update(extended_key_usage=["TLS_WEB_CLIENT_AUTHENTICATION"]),
    lambda x: x["domains"].pop(),
    lambda x: x["domains"][1].update(identity="domain-1"),
    lambda x: x["domains"][1].update(issuer_spki_sha256=digest("wrong-ca")),
    lambda x: x["domains"][1].update(not_after="2026-07-22T23:30:00Z"),
    lambda x: x["domains"][1].update(private_key_path=x["domains"][0]["private_key_path"]),
    lambda x: x["domains"][1].update(certificate_sha256=x["domains"][0]["certificate_sha256"]),
    lambda x: x["domains"][1].update(spki_sha256=x["domains"][0]["spki_sha256"]),
    lambda x: x["domains"][1].update(private_key_file_mode="0644"),
    lambda x: x["domains"][1].update(private_key_export_allowed=True),
    lambda x: x.update(mutual_tls_required=False),
    lambda x: x.update(certificate_chain_and_key_match_verification_required=False),
    lambda x: x.update(certificate_valid_through_execution_expiry_required=False),
    lambda x: x.update(ambient_credential_discovery_allowed=True),
    lambda x: x.update(credential_paths_in_repository_allowed=True),
    lambda x: x.update(private_key_material_embedded=True),
    lambda x: x.update(unexpected="field"),
)
for mutation in credential_mutations:
    rejected_credentials(mutation)


def message(packet_kind: str, sequence: int, previous: str, result: str, failure_code, signer_role: str, namespace: str) -> dict:  # noqa: ANN001
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_agent_message.v1",
        "packet_kind": packet_kind,
        "hashing_contract": {
            "hash_algorithm": "SHA-256",
            "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
            "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/domain-agent-message/v1",
            "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256",
            "self_hash_field": "content_sha256",
            "self_hash_field_excluded": True,
            "detached_signature_covers_complete_canonical_packet": True,
            "cross_field_semantic_validation_required": True,
        },
        "run_id": RUN_ID,
        "source_commit": SOURCE_COMMIT,
        "execution_contract_sha256": digest("execution-contract"),
        "private_endpoint_manifest_sha256": endpoint["content_sha256"],
        "runtime_credential_manifest_sha256": credentials["content_sha256"],
        "domain_id": "domain-2",
        "direction": "COORDINATOR_TO_DOMAIN" if packet_kind.endswith("REQUEST") else "DOMAIN_TO_COORDINATOR",
        "sequence": sequence,
        "previous_message_sha256": previous,
        "nonce_sha256": digest("nonce"),
        "issued_at": "2026-07-22T23:00:00Z",
        "expires_at": "2026-07-22T23:00:30Z",
        "command": "PREFLIGHT",
        "payload_sha256": digest("payload"),
        "result": result,
        "failure_code": failure_code,
        "signature_binding": {
            "signer_role": signer_role,
            "signer_public_key_sha256": digest(f"key:{signer_role}"),
            "signature_scheme": "OPENSSH_SSHSIG_ED25519",
            "signature_namespace": namespace,
            "detached_signature_required": True,
            "signature_embedded": False,
        },
        "raw_endpoint_embedded": False,
        "credential_or_secret_embedded": False,
        "arbitrary_command_or_shell_allowed": False,
        "execution_or_production_claim": False,
    }
    rehash(value, module.MESSAGE_DOMAIN)
    return value


request = message(
    "T22_A1_DOMAIN_AGENT_REQUEST", 0, "0" * 64, "REQUESTED", None,
    "COORDINATOR_RUNTIME", "agent-bridge-t22-a1-coordinator-message-v1",
)
module.validate_agent_message(
    request, message_schema, SOURCE_COMMIT, RUN_ID, digest("execution-contract"),
    endpoint["content_sha256"], credentials["content_sha256"], NOW + timedelta(seconds=1),
)
response = message(
    "T22_A1_DOMAIN_AGENT_RESPONSE", 1, request["content_sha256"], "SUCCEEDED", None,
    "DOMAIN_OPERATOR", "agent-bridge-t22-a1-domain-message-v1",
)
module.validate_agent_message(
    response, message_schema, SOURCE_COMMIT, RUN_ID, digest("execution-contract"),
    endpoint["content_sha256"], credentials["content_sha256"], NOW + timedelta(seconds=1),
)
failed_response = message(
    "T22_A1_DOMAIN_AGENT_RESPONSE", 1, request["content_sha256"], "FAILED", "E_SYNTHETIC",
    "DOMAIN_OPERATOR", "agent-bridge-t22-a1-domain-message-v1",
)
module.validate_agent_message(
    failed_response, message_schema, SOURCE_COMMIT, RUN_ID, digest("execution-contract"),
    endpoint["content_sha256"], credentials["content_sha256"], NOW + timedelta(seconds=1),
)


def rejected_message(base: dict, mutate, now: datetime = NOW + timedelta(seconds=1)) -> None:  # noqa: ANN001
    candidate = copy.deepcopy(base)
    mutate(candidate)
    rehash(candidate, module.MESSAGE_DOMAIN)
    try:
        module.validate_agent_message(
            candidate, message_schema, SOURCE_COMMIT, RUN_ID, digest("execution-contract"),
            endpoint["content_sha256"], credentials["content_sha256"], now,
        )
    except module.SafeFailure:
        return
    raise AssertionError("unsafe agent message mutation admitted")


message_mutations = (
    lambda x: x.update(packet_kind="SHELL"),
    lambda x: x.update(source_commit="b" * 40),
    lambda x: x.update(execution_contract_sha256=digest("other-execution")),
    lambda x: x.update(private_endpoint_manifest_sha256=digest("other-endpoint")),
    lambda x: x.update(runtime_credential_manifest_sha256=digest("other-credentials")),
    lambda x: x.update(domain_id="domain-4"),
    lambda x: x.update(direction="DOMAIN_TO_COORDINATOR"),
    lambda x: x.update(sequence=-1),
    lambda x: x.update(nonce_sha256="0" * 64),
    lambda x: x.update(previous_message_sha256=digest("not-genesis")),
    lambda x: x.update(expires_at="2026-07-22T23:02:00Z"),
    lambda x: x.update(command="EXECUTE_SHELL"),
    lambda x: x.update(result="SUCCEEDED"),
    lambda x: x.update(failure_code="E_FALSE_REQUEST"),
    lambda x: x["signature_binding"].update(signer_role="DOMAIN_OPERATOR"),
    lambda x: x["signature_binding"].update(signature_namespace="agent-bridge-t22-a1-domain-message-v1"),
    lambda x: x["signature_binding"].update(detached_signature_required=False),
    lambda x: x.update(raw_endpoint_embedded=True),
    lambda x: x.update(credential_or_secret_embedded=True),
    lambda x: x.update(arbitrary_command_or_shell_allowed=True),
    lambda x: x.update(execution_or_production_claim=True),
    lambda x: x.update(unexpected="field"),
)
for mutation in message_mutations:
    rejected_message(request, mutation)
rejected_message(request, lambda x: None, NOW + timedelta(minutes=2))

coordinator_fault = copy.deepcopy(request)
coordinator_fault.update(domain_id="domain-1", command="STOP_OWNED_SERVICE_SET")
rehash(coordinator_fault, module.MESSAGE_DOMAIN)
try:
    module.validate_agent_message(
        coordinator_fault, message_schema, SOURCE_COMMIT, RUN_ID, digest("execution-contract"),
        endpoint["content_sha256"], credentials["content_sha256"], NOW + timedelta(seconds=1),
    )
except module.SafeFailure as error:
    assert str(error) == "E_AGENT_MESSAGE_COORDINATOR_FAULT_TARGET"
else:
    raise AssertionError("coordinator domain fault target admitted")

status = module.status()
assert status["status"] == "PRIVATE_RUNTIME_SCHEMAS_READY_REAL_MANIFESTS_AND_OWNER_EXECUTION_SIGNATURE_REQUIRED"
assert status["private_manifest_instances_read"] is False
assert status["credential_files_read"] is False and status["ambient_credentials_accessed"] is False
assert status["network_accessed"] is False
assert status["listeners_started"] == status["external_hosts_contacted"] == 0
assert status["services_started"] == status["faults_injected"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

negative_count = len(endpoint_mutations) + len(credential_mutations) + len(message_mutations) + 2
print("t22_a1_private_runtime_contracts_check\tpass")
print(f"directed_negative_test_count\t{negative_count}")
print("real_private_manifest_instances_read\t0")
print("credential_files_read\tfalse")
print("ambient_credentials_accessed\tfalse")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("external_hosts_contacted\t0")
print("services_started\t0")
print("faults_injected\t0")
