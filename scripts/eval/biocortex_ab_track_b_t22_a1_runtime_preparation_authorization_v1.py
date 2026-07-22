"""Fail-closed owner authorization for T22-A1 runtime material preparation.

This gate authorizes neither execution nor network access. `status`, `build`,
and `verify` do not read endpoint-manifest instances or credential files and do
not generate runtime material.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_CHALLENGE_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_collection_challenge_v1.py"
RUNTIME_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_private_runtime_contracts_v1.py"
SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-runtime-preparation-challenge-schema-v1.json"
EXPECTED_SCHEMA_SHA256 = "be45ac3a4d69a67d4f71e2acc2d2cb5f0ca03b23574640a02c50a5937d6c0282"
PREPARATION_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/runtime-preparation-challenge/v1\0"
SIGNATURE_NAMESPACE = "agent-bridge-t22-a1-owner-runtime-preparation-v1"
MAX_PACKET_BYTES = 64 * 1024
MAX_SIGNATURE_BYTES = 64 * 1024


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def load_module(name: str, source: Path):
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_collection_challenge_module():
    return load_module("t22a1_collection_for_runtime_preparation", COLLECTION_CHALLENGE_SOURCE)


def load_runtime_module():
    return load_module("t22a1_runtime_for_preparation_authorization", RUNTIME_SOURCE)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def challenge_digest(value: object) -> str:
    return hashlib.sha256(PREPARATION_DOMAIN + canonical(value)).hexdigest()


def parse_time(value: str, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise SafeFailure(code) from error
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0, code)
    return parsed


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def load_inputs() -> tuple[object, object, dict, dict, dict]:
    collection = load_collection_challenge_module()
    runtime = load_runtime_module()
    _preflight, contract, proposal, _collection_schema = collection.load_committed_inputs()
    raw = SCHEMA_PATH.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == EXPECTED_SCHEMA_SHA256, "E_PREPARATION_SCHEMA_DIGEST")
    try:
        schema = json.loads(raw)
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        raise SafeFailure("E_PREPARATION_SCHEMA_INVALID") from error
    return collection, runtime, contract, proposal, schema


def validate_paths(target: dict) -> None:
    root = Path(target["private_artifact_root"])
    endpoint = Path(target["private_endpoint_manifest_path"])
    credentials = Path(target["runtime_credential_manifest_output_path"])
    coordinator_key = Path(target["coordinator_runtime_public_key_output_path"])
    openssl = Path(target["openssl_executable_path"])
    ssh_keygen = Path(target["ssh_keygen_executable_path"])
    require(all(path.is_absolute() for path in (root, endpoint, credentials, coordinator_key, openssl, ssh_keygen)), "E_PREPARATION_PATH_ABSOLUTE")
    resolved_root = root.resolve(strict=False)
    repository = ROOT.resolve()
    require(repository not in (resolved_root, *resolved_root.parents) and resolved_root not in repository.parents, "E_PREPARATION_ROOT_IN_REPOSITORY")
    require(endpoint.resolve(strict=False) == resolved_root / "manifests" / "private-endpoints.json", "E_PREPARATION_ENDPOINT_PATH")
    require(credentials.resolve(strict=False) == resolved_root / "manifests" / "runtime-credentials.json", "E_PREPARATION_CREDENTIAL_PATH")
    require(coordinator_key.resolve(strict=False) == resolved_root / "credentials" / "coordinator-runtime.pub", "E_PREPARATION_COORDINATOR_KEY_PATH")
    for executable in (openssl, ssh_keygen):
        resolved = executable.resolve(strict=False)
        require(repository not in (resolved, *resolved.parents), "E_PREPARATION_TOOL_IN_REPOSITORY")


def validate_challenge(
    value: dict,
    anchor: dict,
    contract: dict,
    proposal: dict,
    schema: dict,
    expected_source_commit: str,
    expected_attestation_set_sha256: str,
    expected_endpoint_manifest_sha256: str,
    now: datetime,
) -> dict:
    require(now.tzinfo is not None and now.utcoffset().total_seconds() == 0, "E_PREPARATION_VALIDATION_TIME")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    require(not list(validator.iter_errors(value)), "E_PREPARATION_CHALLENGE_SCHEMA")
    collection = load_collection_challenge_module()
    runtime = load_runtime_module()
    foreign_anchor = collection.validate_anchor
    try:
        foreign_anchor(anchor, proposal)
    except RuntimeError as error:
        raise SafeFailure(str(error)) from error
    require(value["owner_binding"] == {
        "owner_id": "pallasting",
        "owner_role": "PROJECT_OWNER",
        "owner_public_key_sha256": anchor["public_key_sha256"],
        "owner_public_key_fingerprint": anchor["public_key_fingerprint"],
        "signature_scheme": "OPENSSH_SSHSIG_ED25519",
        "signature_namespace": SIGNATURE_NAMESPACE,
    }, "E_PREPARATION_OWNER_BINDING")
    preflight = collection.load_preflight_module()
    bindings = value["bindings"]
    require(bindings == {
        "source_commit": expected_source_commit,
        "owner_decision_proposal_sha256": proposal["proposal_sha256"],
        "admission_contract_sha256": contract["contract_sha256"],
        "exact_three_domain_attestation_set_sha256": expected_attestation_set_sha256,
        "private_endpoint_manifest_schema_sha256": runtime.EXPECTED_ENDPOINT_SCHEMA_SHA256,
        "private_endpoint_manifest_content_sha256": expected_endpoint_manifest_sha256,
        "runtime_credential_manifest_schema_sha256": runtime.EXPECTED_CREDENTIAL_SCHEMA_SHA256,
        "domain_agent_message_schema_sha256": runtime.EXPECTED_MESSAGE_SCHEMA_SHA256,
        "distributed_execution_contract_schema_sha256": preflight.EXPECTED_EXECUTION_SCHEMA_SHA256,
        "runtime_preparation_challenge_schema_sha256": EXPECTED_SCHEMA_SHA256,
    }, "E_PREPARATION_BINDINGS")
    authority = value["preparation_authority"]
    issued = parse_time(authority["issued_at"], "E_PREPARATION_ISSUED_AT")
    not_before = parse_time(authority["not_before"], "E_PREPARATION_NOT_BEFORE")
    expires = parse_time(authority["expires_at"], "E_PREPARATION_EXPIRES_AT")
    lifetime = authority["maximum_lifetime_seconds"]
    require(issued == not_before and expires - issued == timedelta(seconds=lifetime), "E_PREPARATION_LIFETIME_BINDING")
    require(0 < lifetime <= 3600 and not_before <= now < expires, "E_PREPARATION_NOT_CURRENT")
    planned_expiry = parse_time(value["target"]["planned_execution_expires_at"], "E_PREPARATION_PLANNED_EXPIRY")
    require(expires < planned_expiry <= issued + timedelta(hours=24), "E_PREPARATION_EXECUTION_WINDOW")
    validate_paths(value["target"])
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256", None)
    require(isinstance(claimed, str) and claimed == challenge_digest(unsigned), "E_PREPARATION_DIGEST")
    return value


def parse_canonical_challenge(path: Path) -> tuple[dict, bytes]:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "E_PREPARATION_CHALLENGE_FILE")
    require(0 < path.stat().st_size <= MAX_PACKET_BYTES, "E_PREPARATION_CHALLENGE_FILE")
    raw = path.read_bytes()
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "E_PREPARATION_CHALLENGE_FRAMING")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SafeFailure("E_PREPARATION_CHALLENGE_JSON") from error
    require(raw == canonical(value) + b"\n", "E_PREPARATION_CHALLENGE_NOT_CANONICAL")
    return value, raw


def prepare_challenge_output(path: Path, artifact_root: Path) -> None:
    require(path.is_absolute() and artifact_root.is_absolute(), "E_PREPARATION_OUTPUT_ABSOLUTE")
    root = artifact_root.resolve(strict=False)
    expected_parent = root / "authorizations"
    expected_path = expected_parent / "runtime-preparation-challenge.json"
    require(path.resolve(strict=False) == expected_path, "E_PREPARATION_OUTPUT_PATH")
    repository = ROOT.resolve()
    require(repository not in (root, *root.parents) and root not in repository.parents, "E_PREPARATION_ROOT_IN_REPOSITORY")
    for directory in (root, expected_parent):
        if directory.exists():
            require(
                directory.is_dir() and not directory.is_symlink()
                and directory.stat().st_mode & 0o077 == 0,
                "E_PREPARATION_PRIVATE_ARTIFACT_DIRECTORY",
            )
        else:
            directory.mkdir(mode=0o700, parents=True, exist_ok=False)
            directory.chmod(0o700)


def verify_signature(raw: bytes, signature_path: Path, public_key: bytes) -> str:
    require(signature_path.is_absolute() and signature_path.is_file() and not signature_path.is_symlink(), "E_PREPARATION_SIGNATURE_FILE")
    signature = signature_path.read_bytes()
    require(0 < len(signature) <= MAX_SIGNATURE_BYTES, "E_PREPARATION_SIGNATURE_FILE")
    ssh_keygen = shutil.which("ssh-keygen")
    require(ssh_keygen is not None, "E_SSH_KEYGEN_MISSING")
    with tempfile.TemporaryDirectory(prefix="t22-a1-runtime-preparation-verify-") as directory:
        allowed = Path(directory) / "allowed_signers"
        allowed.write_bytes(b"pallasting " + public_key)
        allowed.chmod(0o600)
        result = subprocess.run(
            [ssh_keygen, "-Y", "verify", "-f", str(allowed), "-I", "pallasting",
             "-n", SIGNATURE_NAMESPACE, "-s", str(signature_path)],
            input=raw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C", "LC_ALL": "C"},
            check=False,
        )
    require(result.returncode == 0, "E_PREPARATION_OWNER_SIGNATURE_INVALID")
    return hashlib.sha256(signature).hexdigest()


def build_challenge(
    anchor: dict,
    contract: dict,
    proposal: dict,
    source_commit: str,
    run_id: str,
    attestation_set_sha256: str,
    endpoint_manifest_sha256: str,
    artifact_root: Path,
    openssl_executable: Path,
    openssl_executable_sha256: str,
    ssh_keygen_executable: Path,
    ssh_keygen_executable_sha256: str,
    issued_at: datetime,
    planned_execution_expires_at: datetime,
    maximum_lifetime_seconds: int = 3600,
    credential_validity_margin_seconds: int = 3600,
) -> dict:
    collection, runtime, _contract, _proposal, schema = load_inputs()
    try:
        collection.validate_anchor(anchor, proposal)
    except RuntimeError as error:
        raise SafeFailure(str(error)) from error
    preflight = collection.load_preflight_module()
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.runtime_preparation_challenge.v1",
        "packet_kind": "T22_A1_EXACT_RUNTIME_MATERIAL_PREPARATION_CHALLENGE",
        "decision": "AUTHORIZE_ONE_T22_A1_ZERO_NETWORK_PRIVATE_RUNTIME_MATERIAL_PREPARATION_ONLY",
        "hashing_contract": {
            "hash_algorithm": "SHA-256",
            "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
            "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/runtime-preparation-challenge/v1",
            "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256",
            "self_hash_field": "content_sha256",
            "self_hash_field_excluded": True,
            "detached_owner_signature_covers_complete_canonical_packet": True,
            "cross_field_semantic_validation_required": True,
        },
        "owner_binding": {
            "owner_id": "pallasting",
            "owner_role": "PROJECT_OWNER",
            "owner_public_key_sha256": anchor["public_key_sha256"],
            "owner_public_key_fingerprint": anchor["public_key_fingerprint"],
            "signature_scheme": "OPENSSH_SSHSIG_ED25519",
            "signature_namespace": SIGNATURE_NAMESPACE,
        },
        "bindings": {
            "source_commit": source_commit,
            "owner_decision_proposal_sha256": proposal["proposal_sha256"],
            "admission_contract_sha256": contract["contract_sha256"],
            "exact_three_domain_attestation_set_sha256": attestation_set_sha256,
            "private_endpoint_manifest_schema_sha256": runtime.EXPECTED_ENDPOINT_SCHEMA_SHA256,
            "private_endpoint_manifest_content_sha256": endpoint_manifest_sha256,
            "runtime_credential_manifest_schema_sha256": runtime.EXPECTED_CREDENTIAL_SCHEMA_SHA256,
            "domain_agent_message_schema_sha256": runtime.EXPECTED_MESSAGE_SCHEMA_SHA256,
            "distributed_execution_contract_schema_sha256": preflight.EXPECTED_EXECUTION_SCHEMA_SHA256,
            "runtime_preparation_challenge_schema_sha256": EXPECTED_SCHEMA_SHA256,
        },
        "target": {
            "run_id": run_id,
            "private_artifact_root": str(artifact_root),
            "private_endpoint_manifest_path": str(artifact_root / "manifests" / "private-endpoints.json"),
            "runtime_credential_manifest_output_path": str(artifact_root / "manifests" / "runtime-credentials.json"),
            "coordinator_runtime_public_key_output_path": str(artifact_root / "credentials" / "coordinator-runtime.pub"),
            "openssl_executable_path": str(openssl_executable),
            "openssl_executable_sha256": openssl_executable_sha256,
            "ssh_keygen_executable_path": str(ssh_keygen_executable),
            "ssh_keygen_executable_sha256": ssh_keygen_executable_sha256,
            "planned_execution_expires_at": utc_text(planned_execution_expires_at),
            "credential_validity_margin_seconds": credential_validity_margin_seconds,
        },
        "preparation_authority": {
            "issued_at": utc_text(issued_at),
            "not_before": utc_text(issued_at),
            "expires_at": utc_text(issued_at + timedelta(seconds=maximum_lifetime_seconds)),
            "maximum_lifetime_seconds": maximum_lifetime_seconds,
            "one_preparation_per_challenge_sha256": True,
            "spend_limit_usd_cents": 0,
            "allowed_after_signature": ["READ_EXACT_PRIVATE_ENDPOINT_MANIFEST", "USE_LOCAL_SYSTEM_CSPRNG", "GENERATE_EPHEMERAL_PRIVATE_RUN_CA", "GENERATE_COORDINATOR_MTLS_CLIENT_KEYPAIR", "GENERATE_THREE_DOMAIN_MTLS_SERVER_KEYPAIRS", "GENERATE_COORDINATOR_RUNTIME_ED25519_KEYPAIR", "VERIFY_CERTIFICATE_CHAINS_KEYS_EKU_EXPIRY_AND_ENDPOINT_BINDINGS", "WRITE_EXACT_PRIVATE_RUNTIME_CREDENTIAL_MANIFEST", "WRITE_NONSECRET_PREPARATION_TERMINAL_RECEIPT"],
            "forbidden": ["AMBIENT_OR_PREEXISTING_CREDENTIAL_DISCOVERY_OR_ACCESS", "NETWORK_OR_EXTERNAL_HOST_CONNECTION", "PUBLIC_LISTENER", "OVERLAY_CONFIGURATION_CHANGE", "CLOUD_OR_PROVIDER_API_ACCESS", "NONZERO_SPEND", "SERVICE_PROCESS_START", "FAULT_INJECTION", "WORKLOAD_EXECUTION", "PRODUCTION_OR_CUSTOMER_DATA", "RAW_ENDPOINT_CREDENTIAL_OR_PRIVATE_KEY_REPOSITORY_OUTPUT", "EXECUTION_AUTHORITY_OR_AVAILABILITY_CLAIM", "AUTOMATIC_RETRY"],
        },
        "claims": {
            "preparation_is_execution_authority": False,
            "three_failure_domain_execution_proved": False,
            "external_anti_rollback_proved": False,
            "production_admissible": False,
        },
    }
    value["content_sha256"] = challenge_digest(value)
    validate_challenge(
        value, anchor, contract, proposal, schema, source_commit,
        attestation_set_sha256, endpoint_manifest_sha256, issued_at,
    )
    return value


def verify_challenge_files(path: Path, signature_path: Path, anchor: dict, source_commit: str, now: datetime) -> dict:
    collection, _runtime, contract, proposal, schema = load_inputs()
    try:
        public_key = collection.validate_anchor(anchor, proposal)
    except RuntimeError as error:
        raise SafeFailure(str(error)) from error
    value, raw = parse_canonical_challenge(path)
    validate_challenge(
        value, anchor, contract, proposal, schema, source_commit,
        value["bindings"]["exact_three_domain_attestation_set_sha256"],
        value["bindings"]["private_endpoint_manifest_content_sha256"], now,
    )
    signature_sha256 = verify_signature(raw, signature_path, public_key)
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.runtime_preparation_challenge_verification_receipt.v0",
        "status": "OWNER_SIGNED_RUNTIME_PREPARATION_CHALLENGE_VERIFIED_NO_MATERIAL_GENERATED",
        "run_id": value["target"]["run_id"],
        "source_commit": source_commit,
        "challenge_content_sha256": value["content_sha256"],
        "owner_signature_sha256": signature_sha256,
        "private_endpoint_manifest_instance_read": False,
        "credential_files_read": False,
        "runtime_material_generated": False,
        "network_accessed": False,
        "listeners_started": 0,
        "services_started": 0,
        "faults_injected": 0,
        "spend_usd_cents": 0,
        "execution_authorized": False,
        "production_admissible": False,
    }


def status() -> dict:
    collection, _runtime, _contract, proposal, _schema = load_inputs()
    anchor_present = collection.ANCHOR_PATH.is_file() and not collection.ANCHOR_PATH.is_symlink()
    anchor_valid = False
    if anchor_present:
        try:
            collection.validate_anchor(json.loads(collection.ANCHOR_PATH.read_text()), proposal)
            anchor_valid = True
        except (RuntimeError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            anchor_valid = False
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.runtime_preparation_authorization_status.v0",
        "status": "BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_REQUIRED" if not anchor_present else (
            "BLOCKED_EXACT_ADMITTED_ATTESTATION_SET_ENDPOINT_MANIFEST_AND_OWNER_PREPARATION_SIGNATURE_REQUIRED"
            if anchor_valid else "BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_INVALID"
        ),
        "owner_trust_anchor_present": anchor_present,
        "owner_trust_anchor_valid": anchor_valid,
        "runtime_preparation_challenge_schema_sha256": EXPECTED_SCHEMA_SHA256,
        "private_endpoint_manifest_instance_read": False,
        "credential_files_read": False,
        "runtime_material_generated": False,
        "network_accessed": False,
        "listeners_started": 0,
        "services_started": 0,
        "faults_injected": 0,
        "spend_usd_cents": 0,
        "execution_authorized": False,
        "production_admissible": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    generate = commands.add_parser("generate")
    generate.add_argument("--run-id", required=True)
    generate.add_argument("--attestation-set-sha256", required=True)
    generate.add_argument("--endpoint-manifest-sha256", required=True)
    generate.add_argument("--artifact-root", type=Path, required=True)
    generate.add_argument("--openssl-executable", type=Path, required=True)
    generate.add_argument("--openssl-executable-sha256", required=True)
    generate.add_argument("--ssh-keygen-executable", type=Path, required=True)
    generate.add_argument("--ssh-keygen-executable-sha256", required=True)
    generate.add_argument("--planned-execution-expires-at", required=True)
    generate.add_argument("--maximum-lifetime-seconds", type=int, default=3600)
    generate.add_argument("--credential-validity-margin-seconds", type=int, default=3600)
    generate.add_argument("--out", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--challenge", type=Path, required=True)
    verify.add_argument("--signature", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "status":
        print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
        return
    collection, _runtime, contract, proposal, _schema = load_inputs()
    require(collection.ANCHOR_PATH.is_file() and not collection.ANCHOR_PATH.is_symlink(), "E_OWNER_ANCHOR_REQUIRED")
    try:
        anchor = json.loads(collection.ANCHOR_PATH.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SafeFailure("E_OWNER_ANCHOR_FILE") from error
    source_commit = collection.current_source_commit()
    now = datetime.now(timezone.utc)
    if arguments.command == "generate":
        planned_expiry = parse_time(arguments.planned_execution_expires_at, "E_PREPARATION_PLANNED_EXPIRY")
        challenge = build_challenge(
            anchor, contract, proposal, source_commit, arguments.run_id,
            arguments.attestation_set_sha256, arguments.endpoint_manifest_sha256,
            arguments.artifact_root,
            arguments.openssl_executable, arguments.openssl_executable_sha256,
            arguments.ssh_keygen_executable, arguments.ssh_keygen_executable_sha256,
            now, planned_expiry,
            arguments.maximum_lifetime_seconds, arguments.credential_validity_margin_seconds,
        )
        prepare_challenge_output(arguments.out, arguments.artifact_root)
        collection.write_exclusive(arguments.out, canonical(challenge) + b"\n")
        print(json.dumps({
            "schema": "agent_bridge.biocortex.track_b.t22_a1.runtime_preparation_challenge_generation_receipt.v0",
            "status": "EXACT_ZERO_NETWORK_RUNTIME_PREPARATION_CHALLENGE_GENERATED_AWAITING_OWNER_SIGNATURE",
            "challenge_path": str(arguments.out),
            "run_id": challenge["target"]["run_id"],
            "content_sha256": challenge["content_sha256"],
            "signature_namespace": SIGNATURE_NAMESPACE,
            "private_endpoint_manifest_instance_read": False,
            "runtime_material_generated": False,
            "network_accessed": False,
            "execution_authorized": False,
        }, sort_keys=True, separators=(",", ":")))
        return
    receipt = verify_challenge_files(
        arguments.challenge.resolve(strict=True), arguments.signature.resolve(strict=True),
        anchor, source_commit, now,
    )
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except SafeFailure as error:
        print(json.dumps({"status": "BLOCKED_FAIL_CLOSED", "failure_code": str(error)}, sort_keys=True, separators=(",", ":")))
        sys.exit(1)
