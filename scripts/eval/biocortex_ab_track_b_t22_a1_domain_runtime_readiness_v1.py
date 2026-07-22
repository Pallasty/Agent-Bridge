"""Offline contracts and set verifier for private T22-A1 runtime readiness.

The status path reads no real instance. The explicit verifier reads only the
supplied private readiness and attestation bundles; it never probes a host,
reads a runtime credential/private key, opens a socket, starts a service, or
injects a fault.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-domain-runtime-readiness-schema-v1.json"
ATTESTATION_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_attestation_v1.py"
EXPECTED_SCHEMA_SHA256 = "4c44d3e4617007999af5812d0332fa22f98d1d6302349123bb7c7adb43aa014d"
READINESS_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-runtime-readiness/v1\0"
READINESS_SET_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-runtime-readiness-set/v1\0"
READINESS_SET_RECEIPT_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-runtime-readiness-set-verification-receipt/v1\0"
SIGNATURE_NAMESPACE = "agent-bridge-t22-a1-domain-readiness-v1"
EXECUTABLE_NAMES = ("python3", "etcd", "etcdctl", "bao", "openssl", "ssh-keygen")
DOMAIN_IDS = ("domain-1", "domain-2", "domain-3")
MAX_PACKET_BYTES = 256 * 1024
MAX_SIGNATURE_BYTES = 64 * 1024
OID40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: object) -> str:
    return hashlib.sha256(READINESS_DOMAIN + canonical(value)).hexdigest()


def domain_digest(domain: bytes, value: object) -> str:
    return hashlib.sha256(domain + canonical(value)).hexdigest()


def load_attestation_module():
    spec = importlib.util.spec_from_file_location("t22a1_readiness_attestation", ATTESTATION_SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def foreign_call(function, *args):  # noqa: ANN001, ANN201
    try:
        return function(*args)
    except Exception as error:
        if error.__class__.__name__ == "SafeFailure":
            raise SafeFailure(str(error)) from error
        raise


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


def read_canonical_packet(path: Path) -> tuple[dict, bytes]:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "E_READINESS_PACKET_FILE")
    metadata = path.stat()
    require(
        stat.S_ISREG(metadata.st_mode) and metadata.st_mode & 0o077 == 0
        and 0 < metadata.st_size <= MAX_PACKET_BYTES,
        "E_READINESS_PACKET_FILE",
    )
    raw = path.read_bytes()
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "E_READINESS_PACKET_FRAMING")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SafeFailure("E_READINESS_PACKET_JSON") from error
    require(raw == canonical(value) + b"\n", "E_READINESS_PACKET_NOT_CANONICAL")
    return value, raw


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
    require(parse_time(attestation["attested_at"], "E_READINESS_ATTESTED_AT") <= collected, "E_READINESS_PRECEDES_ATTESTATION")
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


def verify_readiness_signature(
    packet_raw: bytes,
    signature_path: Path,
    public_key_path: Path,
    domain_id: str,
    expected_public_key_sha256: str,
) -> dict:
    require(signature_path.is_absolute() and signature_path.is_file() and not signature_path.is_symlink(), "E_READINESS_SIGNATURE_FILE")
    signature_metadata = signature_path.stat()
    require(
        stat.S_ISREG(signature_metadata.st_mode) and signature_metadata.st_mode & 0o077 == 0
        and 0 < signature_metadata.st_size <= MAX_SIGNATURE_BYTES,
        "E_READINESS_SIGNATURE_FILE",
    )
    signature = signature_path.read_bytes()
    attestation = load_attestation_module()
    public_key, public_key_sha256 = foreign_call(attestation.canonical_public_key, public_key_path)
    require(public_key_sha256 == expected_public_key_sha256, "E_READINESS_PUBLIC_KEY_BINDING")
    ssh_keygen = shutil.which("ssh-keygen")
    require(ssh_keygen is not None, "E_READINESS_SSH_KEYGEN_MISSING")
    with tempfile.TemporaryDirectory(prefix="t22-a1-readiness-verify-") as directory:
        allowed = Path(directory) / "allowed_signers"
        allowed.write_bytes(domain_id.encode() + b" " + public_key)
        allowed.chmod(0o600)
        result = subprocess.run(
            [ssh_keygen, "-Y", "verify", "-f", str(allowed), "-I", domain_id,
             "-n", SIGNATURE_NAMESPACE, "-s", str(signature_path)],
            input=packet_raw,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C", "LC_ALL": "C"},
            check=False,
        )
    require(result.returncode == 0, "E_READINESS_SIGNATURE_INVALID")
    return {
        "public_key_sha256": public_key_sha256,
        "signature_sha256": hashlib.sha256(signature).hexdigest(),
    }


def verify_bundle(
    bundle: Path,
    attestation_bundle: Path,
    source_commit: str,
    run_id: str,
    contract: dict,
    proposal: dict,
    admitted_set_receipt_sha256: str,
    endpoint_manifest: dict,
    credential_manifest: dict,
    runtime_preparation_terminal_sha256: str,
    now: datetime,
) -> dict:
    require(isinstance(source_commit, str) and bool(OID40.fullmatch(source_commit)), "E_READINESS_SOURCE_COMMIT")
    require(isinstance(run_id, str) and bool(run_id), "E_READINESS_RUN_ID")
    require(now.tzinfo is not None and now.utcoffset().total_seconds() == 0, "E_READINESS_VALIDATION_TIME")
    require(
        isinstance(contract, dict) and isinstance(contract.get("contract_sha256"), str)
        and bool(HEX64.fullmatch(contract["contract_sha256"]))
        and isinstance(contract.get("evidence"), dict)
        and isinstance(contract["evidence"].get("maximum_attestation_time_spread_seconds"), int),
        "E_READINESS_CONTRACT_INPUT",
    )
    require(
        isinstance(proposal, dict) and isinstance(proposal.get("proposal_sha256"), str)
        and bool(HEX64.fullmatch(proposal["proposal_sha256"])),
        "E_READINESS_PROPOSAL_INPUT",
    )
    require(
        all(isinstance(value, str) and bool(HEX64.fullmatch(value)) for value in (
            admitted_set_receipt_sha256,
            endpoint_manifest.get("content_sha256") if isinstance(endpoint_manifest, dict) else None,
            credential_manifest.get("content_sha256") if isinstance(credential_manifest, dict) else None,
            runtime_preparation_terminal_sha256,
        )),
        "E_READINESS_UPSTREAM_DIGEST_INPUT",
    )
    require(bundle.is_absolute() and bundle.is_dir() and not bundle.is_symlink(), "E_READINESS_BUNDLE_DIRECTORY")
    require(bundle.stat().st_mode & 0o077 == 0, "E_READINESS_BUNDLE_PERMISSIONS")
    expected_names = {f"{domain_id}{suffix}" for domain_id in DOMAIN_IDS for suffix in (".json", ".json.sig")}
    require({path.name for path in bundle.iterdir()} == expected_names, "E_READINESS_BUNDLE_FILE_SET")

    attestation = load_attestation_module()
    attestation_receipt = foreign_call(attestation.verify_bundle, attestation_bundle, source_commit, now)
    attestation_packets = {
        domain_id: foreign_call(attestation.parse_canonical_packet, attestation_bundle / f"{domain_id}.json")[0]
        for domain_id in DOMAIN_IDS
    }
    schema = load_schema()
    packets: list[dict] = []
    packet_bindings: list[dict] = []
    signature_bindings: list[dict] = []
    for domain_id in DOMAIN_IDS:
        packet, packet_raw = read_canonical_packet(bundle / f"{domain_id}.json")
        validate_readiness(
            packet, schema, source_commit, run_id, domain_id, contract, proposal,
            attestation_packets[domain_id], admitted_set_receipt_sha256,
            endpoint_manifest, credential_manifest, runtime_preparation_terminal_sha256, now,
        )
        signature = verify_readiness_signature(
            packet_raw,
            bundle / f"{domain_id}.json.sig",
            attestation_bundle / f"{domain_id}.pub",
            domain_id,
            attestation_packets[domain_id]["operator_binding"]["public_key_sha256"],
        )
        packets.append(packet)
        packet_bindings.append({"domain_id": domain_id, "readiness_packet_sha256": packet["content_sha256"]})
        signature_bindings.append({"domain_id": domain_id, **signature})

    require(len({packet["content_sha256"] for packet in packets}) == 3, "E_READINESS_SET_DUPLICATE_PACKET")
    require(len({binding["signature_sha256"] for binding in signature_bindings}) == 3, "E_READINESS_SET_DUPLICATE_SIGNATURE")
    collected = [parse_time(packet["collected_at"], "E_READINESS_COLLECTED_AT") for packet in packets]
    spread = int((max(collected) - min(collected)).total_seconds())
    require(spread <= contract["evidence"]["maximum_attestation_time_spread_seconds"], "E_READINESS_SET_CLOCK_SPREAD")
    earliest_expiry = min(parse_time(packet["expires_at"], "E_READINESS_EXPIRES_AT") for packet in packets)
    set_payload = {
        "source_commit": source_commit,
        "run_id": run_id,
        "attestation_set_sha256": attestation_receipt["attestation_set_sha256"],
        "owner_countersigned_attestation_set_receipt_sha256": admitted_set_receipt_sha256,
        "private_endpoint_manifest_content_sha256": endpoint_manifest["content_sha256"],
        "runtime_credential_manifest_content_sha256": credential_manifest["content_sha256"],
        "runtime_preparation_terminal_receipt_sha256": runtime_preparation_terminal_sha256,
        "packets": packet_bindings,
        "signatures": signature_bindings,
    }
    receipt = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_runtime_readiness_set_verification_receipt.v0",
        "status": "THREE_DOMAIN_RUNTIME_READINESS_SET_VERIFIED_NON_EXECUTING",
        "verified_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_commit": source_commit,
        "run_id": run_id,
        "attestation_set_sha256": attestation_receipt["attestation_set_sha256"],
        "attestation_bundle_reverification_receipt_sha256": attestation_receipt["content_sha256"],
        "owner_countersigned_attestation_set_receipt_sha256": admitted_set_receipt_sha256,
        "private_endpoint_manifest_content_sha256": endpoint_manifest["content_sha256"],
        "runtime_credential_manifest_content_sha256": credential_manifest["content_sha256"],
        "runtime_preparation_terminal_receipt_sha256": runtime_preparation_terminal_sha256,
        "runtime_readiness_set_sha256": domain_digest(READINESS_SET_DOMAIN, set_payload),
        "earliest_readiness_expires_at": earliest_expiry.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "maximum_collection_time_spread_seconds": spread,
        "packet_bindings": packet_bindings,
        "signature_bindings": signature_bindings,
        "all_three_packets_current": True,
        "all_three_domain_signatures_verified": True,
        "same_attested_domain_keys_reverified": True,
        "credential_files_accessed": 0,
        "network_accessed": False,
        "external_hosts_contacted": 0,
        "listeners_started": 0,
        "services_started": 0,
        "faults_injected": 0,
        "spend_usd_cents": 0,
        "execution_authorized": False,
        "production_admissible": False,
    }
    receipt["content_sha256"] = domain_digest(READINESS_SET_RECEIPT_DOMAIN, receipt)
    return receipt


def status() -> dict:
    load_schema()
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_runtime_readiness_status.v0",
        "status": "OFFLINE_DOMAIN_RUNTIME_READINESS_CONTRACT_AND_SET_VERIFIER_READY_REAL_PACKET_COLLECTION_BLOCKED",
        "real_packet_instances_read": 0, "real_host_identifiers_read": False,
        "real_tool_or_credential_files_read": 0, "network_accessed": False,
        "external_hosts_contacted": 0, "listeners_started": 0,
        "services_started": 0, "faults_injected": 0,
        "execution_authorized": False, "production_admissible": False,
        "schema_sha256": EXPECTED_SCHEMA_SHA256,
    }


if __name__ == "__main__":
    print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
