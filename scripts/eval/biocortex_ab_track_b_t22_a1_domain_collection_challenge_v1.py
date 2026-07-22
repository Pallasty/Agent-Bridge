"""Fail-closed owner challenge gate for T22-A1 domain identity collection.

`status`, `bind-anchor`, `generate`, and `verify` never read a stable host
identifier, inspect ambient credentials, access the network, start a service,
or collect an attestation. A future collector must call the same verification
path successfully before any identity read.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_three_domain_preflight_v1.py"
SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-domain-collection-challenge-schema-v1.json"
ANCHOR_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-owner-trust-anchor-v1.json"
CHALLENGE_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-collection-challenge/v1\0"
SIGNATURE_NAMESPACE = "agent-bridge-t22-a1-owner-collection-v1"
EXPECTED_SCHEMA_SHA256 = "26d078bb9716cdb443808755ef87c0962f5e4284f94be6f1d168c370a911676d"
MAX_PACKET_BYTES = 64 * 1024
MAX_KEY_BYTES = 16 * 1024
MAX_SIGNATURE_BYTES = 64 * 1024
HEX64 = re.compile(r"^[0-9a-f]{64}$")
OID40 = re.compile(r"^[0-9a-f]{40}$")
KNOWN_ALIAS_CLASS = {"aio2", "pallasting-ThinkBook-14-G5-IRH", "tb14"}


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def load_preflight_module():
    spec = importlib.util.spec_from_file_location("t22a1_collection_preflight", PREFLIGHT_SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def domain_digest(value: object) -> str:
    return hashlib.sha256(CHALLENGE_DOMAIN + canonical(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(HEX64.fullmatch(value)) and value != "0" * 64


def parse_time(value: object, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise SafeFailure(code) from error
    require(parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0, code)
    return parsed


def utc_text(value: datetime) -> str:
    require(value.tzinfo is not None and value.utcoffset().total_seconds() == 0, "E_TIMEZONE")
    return value.isoformat().replace("+00:00", "Z")


def read_bounded_regular(path: Path, maximum: int, code: str) -> bytes:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), code)
    metadata = path.stat()
    require(stat.S_ISREG(metadata.st_mode) and 0 < metadata.st_size <= maximum, code)
    return path.read_bytes()


def canonical_public_key_bytes(raw: bytes) -> bytes:
    require(0 < len(raw) <= MAX_KEY_BYTES, "E_OWNER_PUBLIC_KEY_SIZE")
    try:
        fields = raw.decode("ascii").strip().split()
    except UnicodeDecodeError as error:
        raise SafeFailure("E_OWNER_PUBLIC_KEY_FORMAT") from error
    require(len(fields) >= 2 and fields[0] == "ssh-ed25519", "E_OWNER_PUBLIC_KEY_FORMAT")
    try:
        blob = base64.b64decode(fields[1], validate=True)
    except ValueError as error:
        raise SafeFailure("E_OWNER_PUBLIC_KEY_FORMAT") from error

    def read_string(offset: int) -> tuple[bytes, int]:
        require(offset + 4 <= len(blob), "E_OWNER_PUBLIC_KEY_FORMAT")
        length = int.from_bytes(blob[offset:offset + 4], "big")
        start = offset + 4
        end = start + length
        require(end <= len(blob), "E_OWNER_PUBLIC_KEY_FORMAT")
        return blob[start:end], end

    algorithm, offset = read_string(0)
    key_material, offset = read_string(offset)
    require(algorithm == b"ssh-ed25519" and len(key_material) == 32 and offset == len(blob), "E_OWNER_PUBLIC_KEY_FORMAT")
    return f"ssh-ed25519 {fields[1]}\n".encode()


def public_key_identity(raw: bytes) -> tuple[bytes, str, str]:
    key = canonical_public_key_bytes(raw)
    blob = base64.b64decode(key.split()[1], validate=True)
    fingerprint = base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    return key, hashlib.sha256(key).hexdigest(), f"SHA256:{fingerprint}"


def write_exclusive(path: Path, raw: bytes, mode: int = 0o600) -> None:
    require(path.is_absolute() and not path.exists() and not path.is_symlink(), "E_OUTPUT_EXISTS_OR_INVALID")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(path.parent.is_dir() and not path.parent.is_symlink(), "E_OUTPUT_PARENT")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def load_committed_inputs() -> tuple[object, dict, dict, dict]:
    preflight = load_preflight_module()
    _, contract, proposal = preflight.load_and_validate()
    schema = json.loads(SCHEMA_PATH.read_text())
    require(sha256_file(SCHEMA_PATH) == EXPECTED_SCHEMA_SHA256, "E_COLLECTION_SCHEMA_DIGEST")
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as error:  # jsonschema exposes several schema-error subclasses
        raise SafeFailure("E_COLLECTION_SCHEMA_INVALID") from error
    return preflight, contract, proposal, schema


def build_anchor(public_key_path: Path, proposal: dict, confirmed_proposal_sha256: str) -> dict:
    require(confirmed_proposal_sha256 == proposal["proposal_sha256"], "E_PROPOSAL_CONFIRMATION")
    require(public_key_path.is_absolute() and public_key_path.is_file() and not public_key_path.is_symlink(), "E_OWNER_PUBLIC_KEY_FILE")
    resolved = public_key_path.resolve(strict=True)
    repository = ROOT.resolve()
    require(repository not in (resolved, *resolved.parents), "E_OWNER_PUBLIC_KEY_IN_REPOSITORY")
    raw = read_bounded_regular(resolved, MAX_KEY_BYTES, "E_OWNER_PUBLIC_KEY_FILE")
    key, key_sha256, fingerprint = public_key_identity(raw)
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.owner_trust_anchor.v1",
        "owner_id": "pallasting",
        "owner_role": "PROJECT_OWNER",
        "owner_decision_proposal_sha256": proposal["proposal_sha256"],
        "public_key": key.decode(),
        "public_key_sha256": key_sha256,
        "public_key_fingerprint": fingerprint,
        "allowed_signature_namespaces": [SIGNATURE_NAMESPACE, "agent-bridge-t22-a1-owner-v1"],
    }


def validate_anchor(anchor: object, proposal: dict) -> bytes:
    require(isinstance(anchor, dict) and set(anchor) == {
        "schema", "owner_id", "owner_role", "owner_decision_proposal_sha256",
        "public_key", "public_key_sha256", "public_key_fingerprint",
        "allowed_signature_namespaces",
    }, "E_OWNER_ANCHOR_SHAPE")
    require(anchor["schema"] == "agent_bridge.biocortex.track_b.t22_a1.owner_trust_anchor.v1", "E_OWNER_ANCHOR_SCHEMA")
    require(anchor["owner_id"] == "pallasting" and anchor["owner_role"] == "PROJECT_OWNER", "E_OWNER_ANCHOR_ROLE")
    require(anchor["owner_decision_proposal_sha256"] == proposal["proposal_sha256"], "E_OWNER_ANCHOR_PROPOSAL")
    require(anchor["allowed_signature_namespaces"] == [SIGNATURE_NAMESPACE, "agent-bridge-t22-a1-owner-v1"], "E_OWNER_ANCHOR_NAMESPACES")
    require(isinstance(anchor["public_key"], str), "E_OWNER_ANCHOR_PUBLIC_KEY")
    key, key_sha256, fingerprint = public_key_identity(anchor["public_key"].encode())
    require(anchor["public_key"].encode() == key, "E_OWNER_ANCHOR_PUBLIC_KEY_CANONICAL")
    require(anchor["public_key_sha256"] == key_sha256 and anchor["public_key_fingerprint"] == fingerprint, "E_OWNER_ANCHOR_PUBLIC_KEY_BINDING")
    return key


def current_source_commit() -> str:
    for arguments in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        result = subprocess.run(arguments, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        require(result.returncode == 0, "E_TRACKED_TREE_DIRTY")
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    require(result.returncode == 0 and bool(OID40.fullmatch(result.stdout.strip())), "E_SOURCE_COMMIT")
    return result.stdout.strip()


def validate_artifact_scope(scope: dict, domain_id: str) -> None:
    root = Path(scope["artifact_root"])
    output = Path(scope["domain_output_directory"])
    require(root.is_absolute() and output.is_absolute(), "E_ARTIFACT_SCOPE_ABSOLUTE")
    resolved_root = root.resolve(strict=False)
    resolved_output = output.resolve(strict=False)
    repository = ROOT.resolve()
    require(repository not in (resolved_root, *resolved_root.parents) and resolved_root not in repository.parents, "E_ARTIFACT_ROOT_IN_REPOSITORY")
    require(repository not in (resolved_output, *resolved_output.parents) and resolved_output not in repository.parents, "E_ARTIFACT_OUTPUT_IN_REPOSITORY")
    require(resolved_output == resolved_root / domain_id, "E_ARTIFACT_DOMAIN_DIRECTORY")


def prepare_challenge_output(path: Path, artifact_root: Path, domain_id: str) -> None:
    require(path.is_absolute() and artifact_root.is_absolute(), "E_OUTPUT_ABSOLUTE")
    root = artifact_root.resolve(strict=False)
    expected_parent = root / "authorizations"
    expected_path = expected_parent / f"{domain_id}-collection-challenge.json"
    require(path.resolve(strict=False) == expected_path, "E_CHALLENGE_OUTPUT_PATH")
    repository = ROOT.resolve()
    require(repository not in (root, *root.parents) and root not in repository.parents, "E_ARTIFACT_ROOT_IN_REPOSITORY")
    for directory in (root, expected_parent):
        if directory.exists():
            require(directory.is_dir() and not directory.is_symlink() and directory.stat().st_mode & 0o077 == 0, "E_PRIVATE_ARTIFACT_DIRECTORY")
        else:
            directory.mkdir(mode=0o700, parents=True, exist_ok=False)
            directory.chmod(0o700)


def validate_challenge(value: object, anchor: dict, contract: dict, proposal: dict, schema: dict, expected_source_commit: str, now: datetime) -> dict:
    require(now.tzinfo is not None and now.utcoffset().total_seconds() == 0, "E_VALIDATION_TIME")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    require(not list(validator.iter_errors(value)), "E_CHALLENGE_SCHEMA")
    assert isinstance(value, dict)
    owner = value["owner_binding"]
    validate_anchor(anchor, proposal)
    require(owner == {
        "owner_id": "pallasting",
        "owner_role": "PROJECT_OWNER",
        "owner_public_key_sha256": anchor["public_key_sha256"],
        "owner_public_key_fingerprint": anchor["public_key_fingerprint"],
        "signature_scheme": "OPENSSH_SSHSIG_ED25519",
        "signature_namespace": SIGNATURE_NAMESPACE,
    }, "E_CHALLENGE_OWNER_BINDING")
    bindings = value["bindings"]
    preflight = load_preflight_module()
    require(bindings == {
        "source_commit": expected_source_commit,
        "owner_decision_proposal_sha256": proposal["proposal_sha256"],
        "admission_contract_sha256": contract["contract_sha256"],
        "domain_attestation_schema_sha256": preflight.EXPECTED_SCHEMA_SHA256,
        "collection_challenge_schema_sha256": EXPECTED_SCHEMA_SHA256,
    }, "E_CHALLENGE_BINDINGS")
    target = value["target"]
    aliases = target["logical_aliases"]
    require(aliases == sorted(set(aliases)) and target["expected_hostname"] in aliases, "E_CHALLENGE_ALIASES")
    intersection = set(aliases) & KNOWN_ALIAS_CLASS
    require(not intersection or set(aliases).issuperset(KNOWN_ALIAS_CLASS), "E_CHALLENGE_KNOWN_ALIAS_CLASS")
    if target["provider_kind"] == "CLOUD_VM":
        raise SafeFailure("E_CLOUD_PROVIDER_IDENTITY_VERIFIER_NOT_FROZEN")
    authority = value["collection_authority"]
    issued = parse_time(authority["issued_at"], "E_CHALLENGE_ISSUED_AT")
    not_before = parse_time(authority["not_before"], "E_CHALLENGE_NOT_BEFORE")
    expires = parse_time(authority["expires_at"], "E_CHALLENGE_EXPIRES_AT")
    lifetime = authority["maximum_lifetime_seconds"]
    require(issued == not_before and expires - issued == timedelta(seconds=lifetime), "E_CHALLENGE_LIFETIME_BINDING")
    require(0 < lifetime <= 3600 and not_before <= now < expires, "E_CHALLENGE_NOT_CURRENT")
    validate_artifact_scope(value["artifact_scope"], target["domain_id"])
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256", None)
    require(is_sha256(claimed) and claimed == domain_digest(unsigned), "E_CHALLENGE_DIGEST")
    return value


def parse_canonical_challenge(path: Path) -> tuple[dict, bytes]:
    raw = read_bounded_regular(path, MAX_PACKET_BYTES, "E_CHALLENGE_FILE")
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "E_CHALLENGE_FRAMING")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SafeFailure("E_CHALLENGE_JSON") from error
    require(raw == canonical(value) + b"\n", "E_CHALLENGE_NOT_CANONICAL")
    return value, raw


def verify_owner_signature(packet_raw: bytes, signature_path: Path, owner_public_key: bytes) -> str:
    signature = read_bounded_regular(signature_path, MAX_SIGNATURE_BYTES, "E_OWNER_SIGNATURE_FILE")
    ssh_keygen = shutil.which("ssh-keygen")
    require(ssh_keygen is not None, "E_SSH_KEYGEN_MISSING")
    with tempfile.TemporaryDirectory(prefix="t22-a1-owner-collection-verify-") as directory:
        allowed = Path(directory) / "allowed_signers"
        allowed.write_bytes(b"pallasting " + owner_public_key)
        allowed.chmod(0o600)
        result = subprocess.run(
            [ssh_keygen, "-Y", "verify", "-f", str(allowed), "-I", "pallasting",
             "-n", SIGNATURE_NAMESPACE, "-s", str(signature_path)],
            input=packet_raw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C", "LC_ALL": "C"},
            check=False,
        )
    require(result.returncode == 0, "E_OWNER_SIGNATURE_INVALID")
    return hashlib.sha256(signature).hexdigest()


def verify_challenge_files(challenge_path: Path, signature_path: Path, anchor: dict, source_commit: str, now: datetime) -> dict:
    preflight, contract, proposal, schema = load_committed_inputs()
    owner_public_key = validate_anchor(anchor, proposal)
    challenge, raw = parse_canonical_challenge(challenge_path)
    validate_challenge(challenge, anchor, contract, proposal, schema, source_commit, now)
    signature_sha256 = verify_owner_signature(raw, signature_path, owner_public_key)
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_collection_challenge_verification_receipt.v0",
        "status": "OWNER_SIGNED_DOMAIN_COLLECTION_CHALLENGE_VERIFIED_NO_COLLECTION_PERFORMED",
        "domain_id": challenge["target"]["domain_id"],
        "source_commit": source_commit,
        "challenge_content_sha256": challenge["content_sha256"],
        "owner_signature_sha256": signature_sha256,
        "collection_may_begin_only_in_separate_collector": True,
        "stable_host_identity_read": False,
        "credentials_accessed": False,
        "network_accessed": False,
        "external_hosts_contacted": 0,
        "services_started": 0,
        "faults_injected": 0,
        "attestation_items_created": 0,
        "execution_authorized": False,
        "production_admissible": False,
    }


def build_challenge(anchor: dict, contract: dict, proposal: dict, arguments: argparse.Namespace, source_commit: str, issued_at: datetime) -> dict:
    _preflight, _contract, _proposal, schema = load_committed_inputs()
    validate_anchor(anchor, proposal)
    require(arguments.domain_public_key.is_absolute() and arguments.domain_public_key.is_file() and not arguments.domain_public_key.is_symlink(), "E_DOMAIN_PUBLIC_KEY_FILE")
    _, domain_public_key_sha256, _ = public_key_identity(read_bounded_regular(
        arguments.domain_public_key.resolve(strict=True), MAX_KEY_BYTES, "E_DOMAIN_PUBLIC_KEY_FILE",
    ))
    aliases = sorted(set(arguments.logical_alias))
    lifetime = arguments.maximum_lifetime_seconds
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_collection_challenge.v1",
        "packet_kind": "T22_A1_EXACT_DOMAIN_COLLECTION_CHALLENGE",
        "decision": "AUTHORIZE_ONE_T22_A1_PRIVATE_DOMAIN_ATTESTATION_COLLECTION_ONLY",
        "hashing_contract": {
            "hash_algorithm": "SHA-256",
            "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
            "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/domain-collection-challenge/v1",
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
        "target": {
            "domain_id": arguments.domain_id,
            "expected_hostname": arguments.expected_hostname,
            "logical_aliases": aliases,
            "operating_system": arguments.operating_system,
            "architecture": arguments.architecture,
            "provider_kind": arguments.provider_kind,
            "provider_identity_verifier_id": arguments.provider_identity_verifier_id,
        },
        "bindings": {
            "source_commit": source_commit,
            "owner_decision_proposal_sha256": proposal["proposal_sha256"],
            "admission_contract_sha256": contract["contract_sha256"],
            "domain_attestation_schema_sha256": _preflight.EXPECTED_SCHEMA_SHA256,
            "collection_challenge_schema_sha256": EXPECTED_SCHEMA_SHA256,
        },
        "network_binding": {
            "transport": "OWNER_MANAGED_PRIVATE_OVERLAY",
            "peer_endpoint_set_sha256": arguments.peer_endpoint_set_sha256,
            "acl_policy_receipt_sha256": arguments.acl_policy_receipt_sha256,
            "raw_endpoints_embedded": False,
            "overlay_credentials_embedded": False,
        },
        "workload_binding": {
            "pinned_tool_receipt_sha256": arguments.pinned_tool_receipt_sha256,
            "private_data_root_sha256": arguments.private_data_root_sha256,
            "port_set_sha256": arguments.port_set_sha256,
            "domain_public_key_sha256": domain_public_key_sha256,
            "private_key_export_allowed": False,
        },
        "collection_authority": {
            "issued_at": utc_text(issued_at),
            "not_before": utc_text(issued_at),
            "expires_at": utc_text(issued_at + timedelta(seconds=lifetime)),
            "maximum_lifetime_seconds": lifetime,
            "one_collection_per_challenge_sha256": True,
            "allowed_reads_after_signature": ["HOSTNAME", "OS_KERNEL_ARCHITECTURE", "MACHINE_ID_SOURCE", "HARDWARE_IDENTITY_SOURCE", "BOOT_ID_SOURCE"],
            "allowed_actions_after_signature": ["HASH_IDENTITY_VALUES_IN_MEMORY", "WRITE_ONE_PRIVATE_DOMAIN_ATTESTATION", "SIGN_WITH_EXACT_BOUND_DOMAIN_KEY", "WRITE_NONSECRET_COLLECTION_RECEIPT"],
            "forbidden": ["NETWORK_OR_EXTERNAL_HOST_CONNECTION", "AMBIENT_CREDENTIAL_DISCOVERY", "OVERLAY_CONFIGURATION_CHANGE", "CLOUD_OR_PROVIDER_API_ACCESS_WITHOUT_EXACT_PROVIDER_VERIFIER", "SERVICE_PROCESS_START", "FAULT_INJECTION", "NONZERO_SPEND", "PRODUCTION_OR_CUSTOMER_DATA", "RAW_IDENTITY_VALUE_PERSISTENCE", "EXECUTION_AUTHORITY_OR_AVAILABILITY_CLAIM"],
        },
        "artifact_scope": {
            "artifact_root": str(arguments.artifact_root),
            "domain_output_directory": str(arguments.artifact_root / arguments.domain_id),
            "repository_output_allowed": False,
            "directory_mode": "0700",
            "file_mode": "0600",
            "raw_identity_values_allowed": False,
        },
        "claims": {
            "challenge_is_execution_authority": False,
            "distinct_physical_host_proved": False,
            "site_or_power_independence_proved": False,
            "external_anti_rollback_proved": False,
            "production_admissible": False,
        },
    }
    value["content_sha256"] = domain_digest(value)
    validate_challenge(value, anchor, contract, proposal, schema, source_commit, issued_at)
    return value


def status() -> dict:
    anchor_present = ANCHOR_PATH.is_file() and not ANCHOR_PATH.is_symlink()
    anchor_valid = False
    if anchor_present:
        try:
            _, _, proposal, _ = load_committed_inputs()
            validate_anchor(json.loads(ANCHOR_PATH.read_text()), proposal)
            anchor_valid = True
        except (SafeFailure, KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
            anchor_valid = False
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_collection_challenge_status.v0",
        "status": "BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_REQUIRED" if not anchor_present else (
            "READY_TO_GENERATE_EXACT_COLLECTION_CHALLENGES" if anchor_valid else "BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_INVALID"
        ),
        "owner_trust_anchor_present": anchor_present,
        "owner_trust_anchor_valid": anchor_valid,
        "collection_challenge_schema_sha256": EXPECTED_SCHEMA_SHA256,
        "stable_host_identity_read": False,
        "credentials_accessed": False,
        "network_accessed": False,
        "external_hosts_contacted": 0,
        "services_started": 0,
        "faults_injected": 0,
        "attestation_items_created": 0,
        "execution_authorized": False,
        "production_admissible": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    bind = commands.add_parser("bind-anchor")
    bind.add_argument("--public-key", type=Path, required=True)
    bind.add_argument("--confirm-proposal-sha256", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--domain-id", choices=("domain-1", "domain-2", "domain-3"), required=True)
    generate.add_argument("--expected-hostname", required=True)
    generate.add_argument("--logical-alias", action="append", required=True)
    generate.add_argument("--operating-system", choices=("LINUX", "MACOS"), required=True)
    generate.add_argument("--architecture", choices=("X86_64", "AARCH64"), required=True)
    generate.add_argument("--provider-kind", choices=("OWNER_PHYSICAL", "CLOUD_VM"), required=True)
    generate.add_argument("--provider-identity-verifier-id")
    generate.add_argument("--peer-endpoint-set-sha256", required=True)
    generate.add_argument("--acl-policy-receipt-sha256", required=True)
    generate.add_argument("--pinned-tool-receipt-sha256", required=True)
    generate.add_argument("--private-data-root-sha256", required=True)
    generate.add_argument("--port-set-sha256", required=True)
    generate.add_argument("--domain-public-key", type=Path, required=True)
    generate.add_argument("--artifact-root", type=Path, required=True)
    generate.add_argument("--maximum-lifetime-seconds", type=int, default=3600)
    generate.add_argument("--out", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--challenge", type=Path, required=True)
    verify.add_argument("--signature", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "status":
        print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
        return
    _preflight, contract, proposal, _schema = load_committed_inputs()
    if arguments.command == "bind-anchor":
        require(not ANCHOR_PATH.exists(), "E_OWNER_ANCHOR_ALREADY_EXISTS")
        anchor = build_anchor(arguments.public_key, proposal, arguments.confirm_proposal_sha256)
        write_exclusive(ANCHOR_PATH, canonical(anchor) + b"\n")
        print(json.dumps({
            "status": "T22_A1_OWNER_TRUST_ANCHOR_BOUND_AWAITING_COMMIT",
            "anchor_path": str(ANCHOR_PATH.relative_to(ROOT)),
            "owner_decision_proposal_sha256": proposal["proposal_sha256"],
            "public_key_sha256": anchor["public_key_sha256"],
            "stable_host_identity_read": False,
            "execution_authorized": False,
        }, sort_keys=True, separators=(",", ":")))
        return
    require(ANCHOR_PATH.is_file() and not ANCHOR_PATH.is_symlink(), "E_OWNER_ANCHOR_REQUIRED")
    anchor = json.loads(ANCHOR_PATH.read_text())
    source_commit = current_source_commit()
    now = datetime.now(timezone.utc)
    if arguments.command == "generate":
        challenge = build_challenge(anchor, contract, proposal, arguments, source_commit, now)
        prepare_challenge_output(arguments.out, arguments.artifact_root, arguments.domain_id)
        write_exclusive(arguments.out, canonical(challenge) + b"\n")
        print(json.dumps({
            "status": "EXACT_DOMAIN_COLLECTION_CHALLENGE_GENERATED_AWAITING_OWNER_SIGNATURE",
            "challenge_path": str(arguments.out),
            "domain_id": challenge["target"]["domain_id"],
            "content_sha256": challenge["content_sha256"],
            "signature_namespace": SIGNATURE_NAMESPACE,
            "stable_host_identity_read": False,
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
