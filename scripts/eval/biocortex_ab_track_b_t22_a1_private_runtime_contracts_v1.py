"""Offline semantic validators for T22-A1 private runtime contracts.

The status path and validators do not read manifest instances unless explicitly
passed by the caller, do not inspect credential files, and never open sockets.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
ENDPOINT_SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-private-endpoint-manifest-schema-v1.json"
CREDENTIAL_SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-runtime-credential-manifest-schema-v1.json"
MESSAGE_SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-domain-agent-message-schema-v1.json"
EXPECTED_ENDPOINT_SCHEMA_SHA256 = "8741f130384d246077c281a8200a174f92c63fda565c9384ab7d6edc0f723953"
EXPECTED_CREDENTIAL_SCHEMA_SHA256 = "fe9b257edae7f93d20e81280e54b20da771c432b65ae5ac906231799ad4c10e2"
EXPECTED_MESSAGE_SCHEMA_SHA256 = "92d8a9e59e62b56afec200caf0e25517c7bf3322bc24078024d4c52993e9e3ee"
ENDPOINT_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/private-endpoint-manifest/v1\0"
CREDENTIAL_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/runtime-credential-manifest/v1\0"
MESSAGE_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-agent-message/v1\0"
CGNAT = ipaddress.ip_network("100.64.0.0/10")


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(domain: bytes, value: object) -> str:
    return hashlib.sha256(domain + canonical(value)).hexdigest()


def parse_time(value: str, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise SafeFailure(code) from error
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0, code)
    return parsed


def load_schema(path: Path, expected_sha256: str) -> dict:
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, "E_RUNTIME_SCHEMA_DIGEST")
    try:
        schema = json.loads(raw)
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        raise SafeFailure("E_RUNTIME_SCHEMA_INVALID") from error
    return schema


def load_schemas() -> tuple[dict, dict, dict]:
    return (
        load_schema(ENDPOINT_SCHEMA_PATH, EXPECTED_ENDPOINT_SCHEMA_SHA256),
        load_schema(CREDENTIAL_SCHEMA_PATH, EXPECTED_CREDENTIAL_SCHEMA_SHA256),
        load_schema(MESSAGE_SCHEMA_PATH, EXPECTED_MESSAGE_SCHEMA_SHA256),
    )


def schema_validate(schema: dict, value: object, code: str) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    require(not list(validator.iter_errors(value)), code)


def validate_self_digest(value: dict, domain: bytes, code: str) -> None:
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256", None)
    require(isinstance(claimed, str) and claimed == digest(domain, unsigned), code)


def is_private_overlay_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    prohibited = address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified
    if prohibited:
        return False
    if isinstance(address, ipaddress.IPv4Address):
        return address.is_private or address in CGNAT
    return address.is_private


def validate_endpoint_manifest(value: dict, schema: dict, expected_source_commit: str, expected_run_id: str) -> dict:
    schema_validate(schema, value, "E_ENDPOINT_MANIFEST_SCHEMA")
    require(value["source_commit"] == expected_source_commit and value["run_id"] == expected_run_id, "E_ENDPOINT_MANIFEST_RUN_BINDING")
    domains = value["domains"]
    require(len({domain["hostname"] for domain in domains}) == 3, "E_ENDPOINT_MANIFEST_HOSTNAME_UNIQUENESS")
    require(len({domain["overlay_ip"] for domain in domains}) == 3, "E_ENDPOINT_MANIFEST_IP_UNIQUENESS")
    for domain in domains:
        require(is_private_overlay_ip(domain["overlay_ip"]), "E_ENDPOINT_MANIFEST_NONPRIVATE_IP")
        ports = [domain[field] for field in (
            "agent_control_port", "etcd_client_port", "etcd_peer_port",
            "openbao_api_port", "openbao_cluster_port",
        )]
        require(len(ports) == len(set(ports)), "E_ENDPOINT_MANIFEST_PORT_COLLISION")
    validate_self_digest(value, ENDPOINT_DOMAIN, "E_ENDPOINT_MANIFEST_DIGEST")
    return value


def path_outside_repository(value: str) -> bool:
    path = Path(value)
    if not path.is_absolute():
        return False
    resolved = path.resolve(strict=False)
    repository = ROOT.resolve()
    return repository not in (resolved, *resolved.parents) and resolved not in repository.parents


def validate_credential_manifest(
    value: dict,
    schema: dict,
    expected_source_commit: str,
    expected_run_id: str,
    expected_endpoint_manifest_sha256: str,
    execution_expires_at: datetime,
) -> dict:
    schema_validate(schema, value, "E_CREDENTIAL_MANIFEST_SCHEMA")
    require(value["source_commit"] == expected_source_commit and value["run_id"] == expected_run_id, "E_CREDENTIAL_MANIFEST_RUN_BINDING")
    require(value["private_endpoint_manifest_sha256"] == expected_endpoint_manifest_sha256, "E_CREDENTIAL_ENDPOINT_BINDING")
    ca = value["ca"]
    require(path_outside_repository(ca["certificate_path"]), "E_CREDENTIAL_PATH_SCOPE")
    credentials = [value["coordinator"], *value["domains"]]
    require(value["coordinator"]["extended_key_usage"] == ["TLS_WEB_CLIENT_AUTHENTICATION"], "E_COORDINATOR_CERTIFICATE_USAGE")
    for credential in value["domains"]:
        require(credential["extended_key_usage"] == [
            "TLS_WEB_CLIENT_AUTHENTICATION", "TLS_WEB_SERVER_AUTHENTICATION",
        ], "E_DOMAIN_CERTIFICATE_USAGE")
    paths: list[str] = [ca["certificate_path"]]
    certificate_hashes: list[str] = [ca["certificate_sha256"]]
    spki_hashes: list[str] = [ca["spki_sha256"]]
    for credential in credentials:
        require(credential["issuer_spki_sha256"] == ca["spki_sha256"], "E_CREDENTIAL_ISSUER_BINDING")
        require(parse_time(credential["not_after"], "E_CREDENTIAL_NOT_AFTER") >= execution_expires_at, "E_CREDENTIAL_EXPIRY")
        require(path_outside_repository(credential["certificate_path"]) and path_outside_repository(credential["private_key_path"]), "E_CREDENTIAL_PATH_SCOPE")
        require(credential["certificate_path"] != credential["private_key_path"], "E_CREDENTIAL_CERT_KEY_PATH_COLLISION")
        paths.extend((credential["certificate_path"], credential["private_key_path"]))
        certificate_hashes.append(credential["certificate_sha256"])
        spki_hashes.append(credential["spki_sha256"])
    runtime_key = value["coordinator_runtime_signing_key"]
    require(runtime_key == {
        "identity": "coordinator-runtime",
        "public_key_path": runtime_key["public_key_path"],
        "private_key_path": runtime_key["private_key_path"],
        "public_key_sha256": runtime_key["public_key_sha256"],
        "signature_scheme": "OPENSSH_SSHSIG_ED25519",
        "request_signature_namespace": "agent-bridge-t22-a1-coordinator-message-v1",
        "private_key_file_mode": "0600",
        "private_key_export_allowed": False,
    }, "E_COORDINATOR_RUNTIME_KEY_BINDING")
    require(path_outside_repository(runtime_key["public_key_path"]) and path_outside_repository(runtime_key["private_key_path"]), "E_CREDENTIAL_PATH_SCOPE")
    require(runtime_key["public_key_path"] != runtime_key["private_key_path"], "E_COORDINATOR_RUNTIME_KEY_PATH_COLLISION")
    paths.extend((runtime_key["public_key_path"], runtime_key["private_key_path"]))
    require(len(paths) == len(set(paths)), "E_CREDENTIAL_PATH_REUSE")
    require(len(certificate_hashes) == len(set(certificate_hashes)), "E_CREDENTIAL_CERTIFICATE_REUSE")
    require(len(spki_hashes) == len(set(spki_hashes)), "E_CREDENTIAL_SPKI_REUSE")
    validate_self_digest(value, CREDENTIAL_DOMAIN, "E_CREDENTIAL_MANIFEST_DIGEST")
    return value


def validate_agent_message(
    value: dict,
    schema: dict,
    expected_source_commit: str,
    expected_run_id: str,
    expected_execution_contract_sha256: str,
    expected_endpoint_manifest_sha256: str,
    expected_credential_manifest_sha256: str,
    now: datetime,
) -> dict:
    schema_validate(schema, value, "E_AGENT_MESSAGE_SCHEMA")
    require(value["source_commit"] == expected_source_commit and value["run_id"] == expected_run_id, "E_AGENT_MESSAGE_RUN_BINDING")
    require(value["execution_contract_sha256"] == expected_execution_contract_sha256, "E_AGENT_MESSAGE_EXECUTION_BINDING")
    require(value["private_endpoint_manifest_sha256"] == expected_endpoint_manifest_sha256, "E_AGENT_MESSAGE_ENDPOINT_BINDING")
    require(value["runtime_credential_manifest_sha256"] == expected_credential_manifest_sha256, "E_AGENT_MESSAGE_CREDENTIAL_BINDING")
    issued = parse_time(value["issued_at"], "E_AGENT_MESSAGE_ISSUED_AT")
    expires = parse_time(value["expires_at"], "E_AGENT_MESSAGE_EXPIRES_AT")
    require(0 < (expires - issued).total_seconds() <= 60, "E_AGENT_MESSAGE_LIFETIME")
    require(issued <= now < expires, "E_AGENT_MESSAGE_NOT_CURRENT")
    if value["command"] == "STOP_OWNED_SERVICE_SET":
        require(value["domain_id"] in {"domain-2", "domain-3"}, "E_AGENT_MESSAGE_COORDINATOR_FAULT_TARGET")
    validate_self_digest(value, MESSAGE_DOMAIN, "E_AGENT_MESSAGE_DIGEST")
    return value


def status() -> dict:
    load_schemas()
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.private_runtime_contracts_status.v0",
        "status": "PRIVATE_RUNTIME_SCHEMAS_READY_REAL_MANIFESTS_AND_OWNER_EXECUTION_SIGNATURE_REQUIRED",
        "private_endpoint_manifest_schema_sha256": EXPECTED_ENDPOINT_SCHEMA_SHA256,
        "runtime_credential_manifest_schema_sha256": EXPECTED_CREDENTIAL_SCHEMA_SHA256,
        "domain_agent_message_schema_sha256": EXPECTED_MESSAGE_SCHEMA_SHA256,
        "private_manifest_instances_read": False,
        "credential_files_read": False,
        "ambient_credentials_accessed": False,
        "network_accessed": False,
        "listeners_started": 0,
        "external_hosts_contacted": 0,
        "services_started": 0,
        "faults_injected": 0,
        "execution_authorized": False,
        "production_admissible": False,
    }


if __name__ == "__main__":
    print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
