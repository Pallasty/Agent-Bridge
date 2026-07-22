"""Offline contracts for private T22-A1 host-local runtime readiness.

This module validates already-built packet values. It never reads a real
packet instance, host identity, tool, credential, private key, or endpoint and
never opens a socket, starts a listener/service, or injects a fault.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-domain-runtime-readiness-schema-v1.json"
EXPECTED_SCHEMA_SHA256 = "4c44d3e4617007999af5812d0332fa22f98d1d6302349123bb7c7adb43aa014d"
READINESS_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-runtime-readiness/v1\0"
SIGNATURE_NAMESPACE = "agent-bridge-t22-a1-domain-readiness-v1"
EXECUTABLE_NAMES = ("python3", "etcd", "etcdctl", "bao", "openssl", "ssh-keygen")


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: object) -> str:
    return hashlib.sha256(READINESS_DOMAIN + canonical(value)).hexdigest()


def parse_time(value: str, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise SafeFailure(code) from error
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0, code)
    return parsed


def path_outside_repository(value: str) -> bool:
    path = Path(value)
    if not path.is_absolute():
        return False
    resolved = path.resolve(strict=False)
    repository = ROOT.resolve()
    return repository not in (resolved, *resolved.parents) and resolved not in repository.parents


def load_schema() -> dict:
    raw = SCHEMA_PATH.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == EXPECTED_SCHEMA_SHA256, "E_READINESS_SCHEMA_DIGEST")
    try:
        schema = json.loads(raw)
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        raise SafeFailure("E_READINESS_SCHEMA_INVALID") from error
    return schema


def validate_readiness(
    value: object,
    schema: dict,
    source_commit: str,
    run_id: str,
    domain_id: str,
    contract: dict,
    proposal: dict,
    attestation: dict,
    admitted_set_receipt_sha256: str,
    endpoint_manifest: dict,
    credential_manifest: dict,
    runtime_preparation_terminal_sha256: str,
    now: datetime,
) -> dict:
    require(now.tzinfo is not None and now.utcoffset().total_seconds() == 0, "E_READINESS_VALIDATION_TIME")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    require(not list(validator.iter_errors(value)), "E_READINESS_SCHEMA")
    assert isinstance(value, dict)
    require(value["source_commit"] == source_commit and value["run_id"] == run_id and value["domain_id"] == domain_id, "E_READINESS_RUN_BINDING")
    require(attestation["source_commit"] == source_commit and attestation["domain_id"] == domain_id, "E_READINESS_ATTESTATION_RUN_BINDING")
    collected = parse_time(value["collected_at"], "E_READINESS_COLLECTED_AT")
    expires = parse_time(value["expires_at"], "E_READINESS_EXPIRES_AT")
    require(collected <= now < expires and timedelta(seconds=1) <= expires - collected <= timedelta(hours=1), "E_READINESS_NOT_CURRENT")
    require(expires <= parse_time(attestation["expires_at"], "E_READINESS_ATTESTATION_EXPIRY"), "E_READINESS_ATTESTATION_WINDOW")
    require(value["bindings"] == {
        "owner_decision_proposal_sha256": proposal["proposal_sha256"],
        "admission_contract_sha256": contract["contract_sha256"],
        "domain_attestation_packet_sha256": attestation["attestation_sha256"],
        "owner_countersigned_attestation_set_receipt_sha256": admitted_set_receipt_sha256,
        "private_endpoint_manifest_content_sha256": endpoint_manifest["content_sha256"],
        "runtime_credential_manifest_content_sha256": credential_manifest["content_sha256"],
        "runtime_preparation_terminal_receipt_sha256": runtime_preparation_terminal_sha256,
    }, "E_READINESS_EVIDENCE_BINDINGS")
    host = attestation["host_identity"]
    require(value["host_binding"] == {
        "hostname": host["hostname"], "operating_system": host["operating_system"],
        "architecture": host["architecture"], "machine_id_sha256": host["machine_id_sha256"],
        "hardware_identity_sha256": host["hardware_identity_sha256"],
        "boot_id_sha256": host["boot_id_sha256"],
    }, "E_READINESS_HOST_BINDING")
    endpoint_rows = {row["domain_id"]: row for row in endpoint_manifest["domains"]}
    require(domain_id in endpoint_rows, "E_READINESS_ENDPOINT_DOMAIN")
    endpoint = endpoint_rows[domain_id]
    workload = attestation["workload_readiness"]
    require(value["endpoint_binding"] == {
        "overlay_ip": endpoint["overlay_ip"], "agent_control_port": endpoint["agent_control_port"],
        "etcd_client_port": endpoint["etcd_client_port"], "etcd_peer_port": endpoint["etcd_peer_port"],
        "openbao_api_port": endpoint["openbao_api_port"], "openbao_cluster_port": endpoint["openbao_cluster_port"],
        "port_set_sha256": workload["port_set_sha256"],
        "bind_exact_overlay_ip_only": True, "public_listener_allowed": False,
    }, "E_READINESS_ENDPOINT_BINDING")
    toolchain = value["toolchain"]
    require(toolchain["pinned_tool_receipt_sha256"] == workload["pinned_tool_receipt_sha256"], "E_READINESS_TOOL_RECEIPT_BINDING")
    executables = toolchain["executables"]
    require([row["name"] for row in executables] == list(EXECUTABLE_NAMES), "E_READINESS_EXECUTABLE_ORDER")
    executable_paths = [row["path"] for row in executables]
    executable_hashes = [row["sha256"] for row in executables]
    require(all(path_outside_repository(path) for path in [toolchain["pinned_tool_receipt_path"], *executable_paths]), "E_READINESS_TOOL_PATH_SCOPE")
    require(len(executable_paths) == len(set(executable_paths)) and len(executable_hashes) == len(set(executable_hashes)), "E_READINESS_TOOL_REUSE")
    local = value["local_paths"]
    root = Path(local["domain_private_root"]).resolve(strict=False)
    require(path_outside_repository(str(root)), "E_READINESS_PRIVATE_ROOT_SCOPE")
    require(local["private_data_root_sha256"] == workload["private_data_root_sha256"], "E_READINESS_PRIVATE_ROOT_BINDING")
    require(local == {
        "domain_private_root": str(root),
        "private_data_root_sha256": workload["private_data_root_sha256"],
        "etcd_data_dir": str(root / "etcd"),
        "openbao_data_dir": str(root / "openbao"),
        "owned_logs_dir": str(root / "logs"),
        "domain_evidence_dir": str(root / "evidence"),
        "execution_reservation_dir": str(root / "execution-reservations"),
        "all_paths_outside_repository": True, "directory_mode": "0700",
    }, "E_READINESS_LOCAL_PATH_CLOSURE")
    placement = value["credential_placement"]
    credentials_root = root / "credentials"
    domain_credential = credential_manifest["domains"][int(domain_id[-1]) - 1]
    domain_identity = placement["domain_identity"]
    require(domain_identity == {
        "certificate_path": str(credentials_root / "domain.crt"),
        "private_key_path": str(credentials_root / "domain.key"),
        "certificate_sha256": domain_credential["certificate_sha256"],
        "spki_sha256": domain_credential["spki_sha256"],
        "private_key_spki_sha256": domain_credential["spki_sha256"],
        "private_key_file_mode": "0600", "certificate_private_key_match_verified": True,
    }, "E_READINESS_DOMAIN_CREDENTIAL_BINDING")
    require(placement["ca_certificate_path"] == str(credentials_root / "ca.crt") and placement["ca_certificate_sha256"] == credential_manifest["ca"]["certificate_sha256"], "E_READINESS_CA_BINDING")
    operator_sha256 = attestation["operator_binding"]["public_key_sha256"]
    require(placement["domain_operator_public_key_path"] == str(credentials_root / "domain-operator.pub"), "E_READINESS_OPERATOR_PATH")
    require(placement["domain_operator_private_key_path"] == str(credentials_root / "domain-operator"), "E_READINESS_OPERATOR_PATH")
    require(placement["domain_operator_public_key_sha256"] == operator_sha256, "E_READINESS_OPERATOR_KEY_BINDING")
    coordinator = placement["coordinator_material"]
    if domain_id == "domain-1":
        expected = credential_manifest["coordinator"]
        runtime_key = credential_manifest["coordinator_runtime_signing_key"]
        require(coordinator == {
            "client_identity": {
                "certificate_path": str(credentials_root / "coordinator.crt"),
                "private_key_path": str(credentials_root / "coordinator.key"),
                "certificate_sha256": expected["certificate_sha256"], "spki_sha256": expected["spki_sha256"],
                "private_key_spki_sha256": expected["spki_sha256"], "private_key_file_mode": "0600",
                "certificate_private_key_match_verified": True,
            },
            "runtime_public_key_path": str(credentials_root / "coordinator-runtime.pub"),
            "runtime_private_key_path": str(credentials_root / "coordinator-runtime"),
            "runtime_public_key_sha256": runtime_key["public_key_sha256"],
            "runtime_private_key_file_mode": "0600", "runtime_key_pair_verified": True,
        }, "E_READINESS_COORDINATOR_CREDENTIAL_BINDING")
    else:
        require(coordinator is None, "E_READINESS_COORDINATOR_MATERIAL_SCOPE")
    credential_paths = [
        placement["ca_certificate_path"], domain_identity["certificate_path"], domain_identity["private_key_path"],
        placement["domain_operator_public_key_path"], placement["domain_operator_private_key_path"],
    ]
    if coordinator is not None:
        credential_paths.extend([
            coordinator["client_identity"]["certificate_path"], coordinator["client_identity"]["private_key_path"],
            coordinator["runtime_public_key_path"], coordinator["runtime_private_key_path"],
        ])
    require(all(path_outside_repository(path) for path in credential_paths) and len(credential_paths) == len(set(credential_paths)), "E_READINESS_CREDENTIAL_PATH_SCOPE")
    require(value["signature_binding"] == {
        "signer_role": "T22_A1_DOMAIN_OPERATOR", "signer_public_key_sha256": operator_sha256,
        "signature_scheme": "OPENSSH_SSHSIG_ED25519", "signature_namespace": SIGNATURE_NAMESPACE,
        "detached_signature_required": True, "signature_embedded": False,
    }, "E_READINESS_SIGNATURE_BINDING")
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256")
    require(claimed == digest(unsigned), "E_READINESS_DIGEST")
    return value


def status() -> dict:
    load_schema()
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_runtime_readiness_status.v0",
        "status": "OFFLINE_DOMAIN_RUNTIME_READINESS_CONTRACT_READY_REAL_PACKET_COLLECTION_BLOCKED",
        "real_packet_instances_read": 0, "real_host_identifiers_read": False,
        "real_tool_or_credential_files_read": 0, "network_accessed": False,
        "external_hosts_contacted": 0, "listeners_started": 0,
        "services_started": 0, "faults_injected": 0,
        "execution_authorized": False, "production_admissible": False,
        "schema_sha256": EXPECTED_SCHEMA_SHA256,
    }


if __name__ == "__main__":
    print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
