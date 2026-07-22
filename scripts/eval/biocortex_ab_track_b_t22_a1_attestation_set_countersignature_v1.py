"""Owner countersignature gate for one exact T22-A1 three-domain set.

The admission path verifies owner authority before reading the private bundle,
atomically reserves the countersignature, then fully reverifies all three
domain packets and signatures. It creates no execution or network authority.
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
COLLECTION_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_collection_challenge_v1.py"
ATTESTATION_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_attestation_v1.py"
SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-attestation-set-countersignature-schema-v1.json"
EXPECTED_SCHEMA_SHA256 = "615959dbd1fbfe65da7830cd5b2bf4efc2ef9a917c94ae9438f820837d121a1c"
COUNTERSIGNATURE_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/attestation-set-countersignature/v1\0"
ADMISSION_RECEIPT_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/owner-countersigned-attestation-set-receipt/v1\0"
TERMINAL_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/attestation-set-countersignature-terminal/v1\0"
SIGNATURE_NAMESPACE = "agent-bridge-t22-a1-owner-attestation-set-v1"
MAX_PACKET_BYTES = 128 * 1024
MAX_SIGNATURE_BYTES = 64 * 1024


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def foreign_call(function, *arguments, **keywords):  # noqa: ANN001, ANN002, ANN003
    try:
        return function(*arguments, **keywords)
    except RuntimeError as error:
        raise SafeFailure(str(error)) from error


def load_module(name: str, source: Path):
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_collection_module():
    return load_module("t22a1_collection_for_set_countersignature", COLLECTION_SOURCE)


def load_attestation_module():
    return load_module("t22a1_attestation_for_set_countersignature", ATTESTATION_SOURCE)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(domain: bytes, value: object) -> str:
    return hashlib.sha256(domain + canonical(value)).hexdigest()


def utc_text(value: datetime) -> str:
    require(value.tzinfo is not None and value.utcoffset().total_seconds() == 0, "E_COUNTERSIGNATURE_TIMEZONE")
    return value.isoformat().replace("+00:00", "Z")


def parse_time(value: str, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise SafeFailure(code) from error
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0, code)
    return parsed


def load_inputs() -> tuple[object, object, dict, dict, dict]:
    collection = load_collection_module()
    attestation = load_attestation_module()
    preflight, contract, proposal, _collection_schema = collection.load_committed_inputs()
    raw = SCHEMA_PATH.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == EXPECTED_SCHEMA_SHA256, "E_COUNTERSIGNATURE_SCHEMA_DIGEST")
    try:
        schema = json.loads(raw)
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        raise SafeFailure("E_COUNTERSIGNATURE_SCHEMA_INVALID") from error
    require(preflight.EXPECTED_ATTESTATION_SET_COUNTERSIGNATURE_SCHEMA_SHA256 == EXPECTED_SCHEMA_SHA256, "E_COUNTERSIGNATURE_SCHEMA_PREFLIGHT_BINDING")
    return collection, attestation, contract, proposal, schema


def verified_set_from_receipt(receipt: dict) -> dict:
    return {
        "attestation_set_sha256": receipt["attestation_set_sha256"],
        "bundle_verification_receipt_sha256": receipt["content_sha256"],
        "verified_at": receipt["verified_at"],
        "earliest_attestation_expires_at": receipt["earliest_attestation_expires_at"],
        "packet_bindings": receipt["packet_bindings"],
        "signature_bindings": receipt["signature_bindings"],
        "set_validation": receipt["set_validation"],
    }


def stable_verified_set(value: dict) -> dict:
    return {
        key: value[key]
        for key in (
            "attestation_set_sha256", "earliest_attestation_expires_at",
            "packet_bindings", "signature_bindings", "set_validation",
        )
    }


def validate_admission_receipt(
    value: object,
    expected_source_commit: str,
    contract: dict,
    proposal: dict,
    now: datetime,
) -> dict:
    required = {
        "schema", "status", "source_commit", "admission_contract_sha256",
        "owner_decision_proposal_sha256", "attestation_set_countersignature_content_sha256",
        "owner_signature_sha256", "countersignature_bundle_verification_receipt_sha256",
        "admission_bundle_reverification_receipt_sha256", "attestation_set_sha256",
        "earliest_attestation_expires_at", "packet_bindings", "signature_bindings",
        "set_validation", "owner_countersignature_verified", "all_domain_attestations_current",
        "all_domain_signatures_verified", "all_domain_distinctness_checks_passed",
        "raw_identity_values_embedded", "credentials_accessed", "network_accessed",
        "external_hosts_contacted", "services_started", "faults_injected", "spend_usd_cents",
        "execution_authorized", "production_admissible", "admitted_at", "content_sha256",
    }
    require(isinstance(value, dict) and set(value) == required, "E_ADMITTED_SET_RECEIPT_SHAPE")
    assert isinstance(value, dict)
    require(value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.owner_countersigned_attestation_set_receipt.v1", "E_ADMITTED_SET_RECEIPT_SCHEMA")
    require(value["status"] == "THREE_DOMAIN_INPUT_SET_OWNER_COUNTERSIGNED_ADMITTED_NON_EXECUTING", "E_ADMITTED_SET_RECEIPT_STATUS")
    require(value["source_commit"] == expected_source_commit, "E_ADMITTED_SET_RECEIPT_SOURCE")
    require(value["admission_contract_sha256"] == contract["contract_sha256"], "E_ADMITTED_SET_RECEIPT_CONTRACT")
    require(value["owner_decision_proposal_sha256"] == proposal["proposal_sha256"], "E_ADMITTED_SET_RECEIPT_PROPOSAL")
    attestation = load_attestation_module()
    for field in (
        "attestation_set_countersignature_content_sha256", "owner_signature_sha256",
        "countersignature_bundle_verification_receipt_sha256",
        "admission_bundle_reverification_receipt_sha256", "attestation_set_sha256",
    ):
        require(attestation.is_sha256(value[field]), "E_ADMITTED_SET_RECEIPT_DIGEST")
    require(isinstance(value["packet_bindings"], list) and len(value["packet_bindings"]) == 3, "E_ADMITTED_SET_RECEIPT_PACKET_BINDINGS")
    require([item.get("domain_id") for item in value["packet_bindings"]] == ["domain-1", "domain-2", "domain-3"], "E_ADMITTED_SET_RECEIPT_PACKET_BINDINGS")
    require(all(set(item) == {"domain_id", "attestation_sha256"} and attestation.is_sha256(item["attestation_sha256"]) for item in value["packet_bindings"]), "E_ADMITTED_SET_RECEIPT_PACKET_BINDINGS")
    require(isinstance(value["signature_bindings"], list) and len(value["signature_bindings"]) == 3, "E_ADMITTED_SET_RECEIPT_SIGNATURE_BINDINGS")
    require([item.get("domain_id") for item in value["signature_bindings"]] == ["domain-1", "domain-2", "domain-3"], "E_ADMITTED_SET_RECEIPT_SIGNATURE_BINDINGS")
    require(all(
        set(item) == {"domain_id", "public_key_sha256", "signature_sha256"}
        and attestation.is_sha256(item["public_key_sha256"])
        and attestation.is_sha256(item["signature_sha256"])
        for item in value["signature_bindings"]
    ), "E_ADMITTED_SET_RECEIPT_SIGNATURE_BINDINGS")
    validation = value["set_validation"]
    require(isinstance(validation, dict) and set(validation) == {
        "domain_count", "distinct_machine_identity_count", "distinct_hardware_identity_count",
        "distinct_hostname_count", "distinct_domain_signing_key_count",
        "maximum_attestation_time_spread_seconds", "peer_endpoint_set_sha256",
        "acl_policy_receipt_sha256",
    }, "E_ADMITTED_SET_RECEIPT_SET_VALIDATION")
    require(validation["domain_count"] == validation["distinct_machine_identity_count"] == 3, "E_ADMITTED_SET_RECEIPT_DISTINCTNESS")
    require(validation["distinct_hardware_identity_count"] == validation["distinct_hostname_count"] == 3, "E_ADMITTED_SET_RECEIPT_DISTINCTNESS")
    require(validation["distinct_domain_signing_key_count"] == 3 and 0 <= validation["maximum_attestation_time_spread_seconds"] <= 300, "E_ADMITTED_SET_RECEIPT_DISTINCTNESS")
    require(attestation.is_sha256(validation["peer_endpoint_set_sha256"]) and attestation.is_sha256(validation["acl_policy_receipt_sha256"]), "E_ADMITTED_SET_RECEIPT_SET_VALIDATION")
    require(parse_time(value["admitted_at"], "E_ADMITTED_SET_RECEIPT_TIME") <= now < parse_time(value["earliest_attestation_expires_at"], "E_ADMITTED_SET_RECEIPT_EXPIRY"), "E_ADMITTED_SET_RECEIPT_NOT_CURRENT")
    require(value["owner_countersignature_verified"] is True, "E_ADMITTED_SET_RECEIPT_OWNER_SIGNATURE")
    require(value["all_domain_attestations_current"] is True and value["all_domain_signatures_verified"] is True, "E_ADMITTED_SET_RECEIPT_DOMAIN_VERIFICATION")
    require(value["all_domain_distinctness_checks_passed"] is True, "E_ADMITTED_SET_RECEIPT_DISTINCTNESS")
    require(value["raw_identity_values_embedded"] is False and value["credentials_accessed"] is False, "E_ADMITTED_SET_RECEIPT_SECRET_BOUNDARY")
    require(value["network_accessed"] is False and value["external_hosts_contacted"] == 0, "E_ADMITTED_SET_RECEIPT_NETWORK_BOUNDARY")
    require(value["services_started"] == value["faults_injected"] == value["spend_usd_cents"] == 0, "E_ADMITTED_SET_RECEIPT_SIDE_EFFECT_BOUNDARY")
    require(value["execution_authorized"] is False and value["production_admissible"] is False, "E_ADMITTED_SET_RECEIPT_CLAIMS")
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256")
    require(claimed == digest(ADMISSION_RECEIPT_DOMAIN, unsigned), "E_ADMITTED_SET_RECEIPT_DIGEST")
    return value


def parse_admission_receipt(
    path: Path,
    expected_source_commit: str,
    contract: dict,
    proposal: dict,
    now: datetime,
) -> dict:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "E_ADMITTED_SET_RECEIPT_FILE")
    require(0 < path.stat().st_size <= MAX_PACKET_BYTES and path.stat().st_mode & 0o077 == 0, "E_ADMITTED_SET_RECEIPT_FILE")
    raw = path.read_bytes()
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "E_ADMITTED_SET_RECEIPT_FRAMING")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SafeFailure("E_ADMITTED_SET_RECEIPT_JSON") from error
    require(raw == canonical(value) + b"\n", "E_ADMITTED_SET_RECEIPT_NOT_CANONICAL")
    return validate_admission_receipt(value, expected_source_commit, contract, proposal, now)


def validate_artifact_scope(scope: dict) -> None:
    root = Path(scope["private_artifact_root"])
    output = Path(scope["admitted_set_receipt_output_path"])
    require(root.is_absolute() and output.is_absolute(), "E_COUNTERSIGNATURE_ARTIFACT_PATH_ABSOLUTE")
    resolved_root = root.resolve(strict=False)
    repository = ROOT.resolve()
    require(repository not in (resolved_root, *resolved_root.parents) and resolved_root not in repository.parents, "E_COUNTERSIGNATURE_ARTIFACT_ROOT_IN_REPOSITORY")
    require(output.resolve(strict=False) == resolved_root / "admissions" / "owner-countersigned-attestation-set.json", "E_COUNTERSIGNATURE_ADMISSION_OUTPUT_PATH")


def challenge_digest(value: dict) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return digest(COUNTERSIGNATURE_DOMAIN, unsigned)


def validate_envelope(
    value: object,
    anchor: dict,
    contract: dict,
    proposal: dict,
    schema: dict,
    expected_source_commit: str,
    now: datetime,
) -> dict:
    require(now.tzinfo is not None and now.utcoffset().total_seconds() == 0, "E_COUNTERSIGNATURE_VALIDATION_TIME")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    require(not list(validator.iter_errors(value)), "E_COUNTERSIGNATURE_SCHEMA")
    assert isinstance(value, dict)
    collection = load_collection_module()
    foreign_call(collection.validate_anchor, anchor, proposal)
    require(value["owner_binding"] == {
        "owner_id": "pallasting",
        "owner_role": "PROJECT_OWNER",
        "owner_public_key_sha256": anchor["public_key_sha256"],
        "owner_public_key_fingerprint": anchor["public_key_fingerprint"],
        "signature_scheme": "OPENSSH_SSHSIG_ED25519",
        "signature_namespace": SIGNATURE_NAMESPACE,
    }, "E_COUNTERSIGNATURE_OWNER_BINDING")
    preflight = collection.load_preflight_module()
    require(value["bindings"] == {
        "source_commit": expected_source_commit,
        "owner_decision_proposal_sha256": proposal["proposal_sha256"],
        "admission_contract_sha256": contract["contract_sha256"],
        "domain_attestation_schema_sha256": preflight.EXPECTED_SCHEMA_SHA256,
        "attestation_set_countersignature_schema_sha256": EXPECTED_SCHEMA_SHA256,
    }, "E_COUNTERSIGNATURE_BINDINGS")
    authority = value["countersignature_authority"]
    issued = parse_time(authority["issued_at"], "E_COUNTERSIGNATURE_ISSUED_AT")
    not_before = parse_time(authority["not_before"], "E_COUNTERSIGNATURE_NOT_BEFORE")
    expires = parse_time(authority["expires_at"], "E_COUNTERSIGNATURE_EXPIRES_AT")
    lifetime = authority["maximum_lifetime_seconds"]
    earliest = parse_time(value["verified_set"]["earliest_attestation_expires_at"], "E_COUNTERSIGNATURE_ATTESTATION_EXPIRY")
    verified_at = parse_time(value["verified_set"]["verified_at"], "E_COUNTERSIGNATURE_VERIFIED_AT")
    require(issued == not_before and expires - issued == timedelta(seconds=lifetime), "E_COUNTERSIGNATURE_LIFETIME_BINDING")
    require(0 < lifetime <= 3600 and not_before <= now < expires <= earliest, "E_COUNTERSIGNATURE_NOT_CURRENT")
    require(verified_at == issued, "E_COUNTERSIGNATURE_VERIFICATION_TIME_BINDING")
    validate_artifact_scope(value["artifact_scope"])
    require(value["content_sha256"] == challenge_digest(value), "E_COUNTERSIGNATURE_DIGEST")
    return value


def parse_canonical_challenge(path: Path) -> tuple[dict, bytes]:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "E_COUNTERSIGNATURE_FILE")
    require(0 < path.stat().st_size <= MAX_PACKET_BYTES, "E_COUNTERSIGNATURE_FILE")
    raw = path.read_bytes()
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "E_COUNTERSIGNATURE_FRAMING")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SafeFailure("E_COUNTERSIGNATURE_JSON") from error
    require(raw == canonical(value) + b"\n", "E_COUNTERSIGNATURE_NOT_CANONICAL")
    return value, raw


def verify_owner_signature(raw: bytes, signature_path: Path, public_key: bytes) -> str:
    require(signature_path.is_absolute() and signature_path.is_file() and not signature_path.is_symlink(), "E_COUNTERSIGNATURE_SIGNATURE_FILE")
    signature = signature_path.read_bytes()
    require(0 < len(signature) <= MAX_SIGNATURE_BYTES, "E_COUNTERSIGNATURE_SIGNATURE_FILE")
    ssh_keygen = shutil.which("ssh-keygen")
    require(ssh_keygen is not None, "E_SSH_KEYGEN_MISSING")
    with tempfile.TemporaryDirectory(prefix="t22-a1-set-countersignature-verify-") as directory:
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
    require(result.returncode == 0, "E_COUNTERSIGNATURE_OWNER_SIGNATURE_INVALID")
    return hashlib.sha256(signature).hexdigest()


def build_challenge(
    anchor: dict,
    contract: dict,
    proposal: dict,
    bundle: Path,
    source_commit: str,
    artifact_root: Path,
    issued_at: datetime,
    maximum_lifetime_seconds: int = 3600,
) -> dict:
    collection, attestation, _contract, _proposal, schema = load_inputs()
    foreign_call(collection.validate_anchor, anchor, proposal)
    receipt = foreign_call(attestation.verify_bundle, bundle, source_commit, issued_at)
    earliest = parse_time(receipt["earliest_attestation_expires_at"], "E_COUNTERSIGNATURE_ATTESTATION_EXPIRY")
    available_seconds = int((earliest - issued_at).total_seconds())
    lifetime = min(maximum_lifetime_seconds, available_seconds)
    require(0 < lifetime <= 3600, "E_COUNTERSIGNATURE_LIFETIME")
    preflight = collection.load_preflight_module()
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.attestation_set_countersignature.v1",
        "packet_kind": "T22_A1_EXACT_THREE_DOMAIN_ATTESTATION_SET_OWNER_COUNTERSIGNATURE",
        "decision": "COUNTERSIGN_ONE_EXACT_REVERIFIED_T22_A1_THREE_DOMAIN_INPUT_SET_NON_EXECUTING",
        "hashing_contract": {
            "hash_algorithm": "SHA-256",
            "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
            "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/attestation-set-countersignature/v1",
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
            "domain_attestation_schema_sha256": preflight.EXPECTED_SCHEMA_SHA256,
            "attestation_set_countersignature_schema_sha256": EXPECTED_SCHEMA_SHA256,
        },
        "verified_set": verified_set_from_receipt(receipt),
        "artifact_scope": {
            "private_artifact_root": str(artifact_root),
            "admitted_set_receipt_output_path": str(artifact_root / "admissions" / "owner-countersigned-attestation-set.json"),
            "repository_output_allowed": False,
            "directory_mode": "0700",
            "file_mode": "0600",
        },
        "countersignature_authority": {
            "issued_at": utc_text(issued_at),
            "not_before": utc_text(issued_at),
            "expires_at": utc_text(issued_at + timedelta(seconds=lifetime)),
            "maximum_lifetime_seconds": lifetime,
            "one_admission_per_countersignature_sha256": True,
            "allowed_after_signature": ["REVERIFY_EXACT_PRIVATE_THREE_DOMAIN_BUNDLE", "WRITE_PRIVATE_NONSECRET_ADMITTED_SET_RECEIPT"],
            "forbidden": ["STABLE_HOST_IDENTITY_SOURCE_READ", "AMBIENT_CREDENTIAL_DISCOVERY_OR_ACCESS", "NETWORK_OR_EXTERNAL_HOST_CONNECTION", "PUBLIC_LISTENER", "OVERLAY_CONFIGURATION_CHANGE", "CLOUD_OR_PROVIDER_API_ACCESS", "NONZERO_SPEND", "SERVICE_PROCESS_START", "FAULT_INJECTION", "WORKLOAD_EXECUTION", "PRODUCTION_OR_CUSTOMER_DATA", "EXECUTION_AUTHORITY_OR_AVAILABILITY_CLAIM", "AUTOMATIC_RETRY"],
        },
        "claims": {
            "countersignature_is_execution_authority": False,
            "host_power_loss_proved": False,
            "site_power_network_independence_proved": False,
            "external_anti_rollback_proved": False,
            "production_admissible": False,
        },
    }
    value["content_sha256"] = challenge_digest(value)
    validate_envelope(value, anchor, contract, proposal, schema, source_commit, issued_at)
    return value


def ensure_private_directory(path: Path, create: bool) -> None:
    require(path.is_absolute() and not path.is_symlink(), "E_COUNTERSIGNATURE_PRIVATE_DIRECTORY")
    if not path.exists() and create:
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
        path.chmod(0o700)
    require(path.is_dir() and not path.is_symlink(), "E_COUNTERSIGNATURE_PRIVATE_DIRECTORY")
    require(path.stat().st_mode & 0o077 == 0, "E_COUNTERSIGNATURE_PRIVATE_DIRECTORY_PERMISSIONS")


def write_exclusive(path: Path, raw: bytes) -> None:
    require(path.is_absolute() and not path.exists() and not path.is_symlink(), "E_COUNTERSIGNATURE_OUTPUT_EXISTS")
    ensure_private_directory(path.parent, create=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def prepare_challenge_output(path: Path, artifact_root: Path) -> None:
    root = artifact_root.resolve(strict=False)
    require(path.is_absolute() and artifact_root.is_absolute(), "E_COUNTERSIGNATURE_OUTPUT_ABSOLUTE")
    require(path.resolve(strict=False) == root / "authorizations" / "attestation-set-countersignature.json", "E_COUNTERSIGNATURE_CHALLENGE_OUTPUT_PATH")
    validate_artifact_scope({
        "private_artifact_root": str(root),
        "admitted_set_receipt_output_path": str(root / "admissions" / "owner-countersigned-attestation-set.json"),
    })
    ensure_private_directory(root, create=True)
    ensure_private_directory(root / "authorizations", create=True)


def write_terminal(path: Path, body: dict) -> dict:
    value = dict(body)
    value["content_sha256"] = digest(TERMINAL_DOMAIN, value)
    write_exclusive(path, canonical(value) + b"\n")
    return value


def reserve(root: Path, challenge: dict, source_commit: str, now: datetime) -> tuple[Path, Path]:
    ensure_private_directory(root, create=False)
    uses = root / "attestation-set-countersignature-uses"
    ensure_private_directory(uses, create=True)
    stem = challenge["content_sha256"]
    reservation = uses / f"{stem}.reserved.json"
    terminal = uses / f"{stem}.terminal.json"
    write_exclusive(reservation, canonical({
        "schema": "agent_bridge.biocortex.track_b.t22_a1.attestation_set_countersignature_reservation.v1",
        "status": "ATTESTATION_SET_COUNTERSIGNATURE_RESERVED_SINGLE_USE",
        "source_commit": source_commit,
        "challenge_content_sha256": stem,
        "reserved_at": utc_text(now),
        "automatic_retry_allowed": False,
        "execution_authorized": False,
        "production_admissible": False,
    }) + b"\n")
    return reservation, terminal


def admit(
    challenge_path: Path,
    owner_signature_path: Path,
    bundle: Path,
    source_commit: str,
    now: datetime,
) -> dict:
    collection, attestation, contract, proposal, schema = load_inputs()
    require(collection.ANCHOR_PATH.is_file() and not collection.ANCHOR_PATH.is_symlink(), "E_OWNER_ANCHOR_REQUIRED")
    anchor = json.loads(collection.ANCHOR_PATH.read_text())
    public_key = foreign_call(collection.validate_anchor, anchor, proposal)
    challenge, raw = parse_canonical_challenge(challenge_path)
    validate_envelope(challenge, anchor, contract, proposal, schema, source_commit, now)
    owner_signature_sha256 = verify_owner_signature(raw, owner_signature_path, public_key)
    root = Path(challenge["artifact_scope"]["private_artifact_root"])
    output = Path(challenge["artifact_scope"]["admitted_set_receipt_output_path"])
    validate_artifact_scope(challenge["artifact_scope"])
    require(not output.exists() and not output.is_symlink(), "E_COUNTERSIGNATURE_ADMISSION_OUTPUT_EXISTS")
    _reservation, terminal_path = reserve(root, challenge, source_commit, now)
    bundle_read = False
    output_written = False
    try:
        bundle_read = True
        verification = foreign_call(attestation.verify_bundle, bundle, source_commit, now)
        require(
            stable_verified_set(challenge["verified_set"])
            == stable_verified_set(verified_set_from_receipt(verification)),
            "E_COUNTERSIGNATURE_REVERIFIED_SET_MISMATCH",
        )
        receipt = {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.owner_countersigned_attestation_set_receipt.v1",
            "status": "THREE_DOMAIN_INPUT_SET_OWNER_COUNTERSIGNED_ADMITTED_NON_EXECUTING",
            "source_commit": source_commit,
            "admission_contract_sha256": contract["contract_sha256"],
            "owner_decision_proposal_sha256": proposal["proposal_sha256"],
            "attestation_set_countersignature_content_sha256": challenge["content_sha256"],
            "owner_signature_sha256": owner_signature_sha256,
            "countersignature_bundle_verification_receipt_sha256": challenge["verified_set"]["bundle_verification_receipt_sha256"],
            "admission_bundle_reverification_receipt_sha256": verification["content_sha256"],
            "attestation_set_sha256": verification["attestation_set_sha256"],
            "earliest_attestation_expires_at": verification["earliest_attestation_expires_at"],
            "packet_bindings": verification["packet_bindings"],
            "signature_bindings": verification["signature_bindings"],
            "set_validation": verification["set_validation"],
            "owner_countersignature_verified": True,
            "all_domain_attestations_current": True,
            "all_domain_signatures_verified": True,
            "all_domain_distinctness_checks_passed": True,
            "raw_identity_values_embedded": False,
            "credentials_accessed": False,
            "network_accessed": False,
            "external_hosts_contacted": 0,
            "services_started": 0,
            "faults_injected": 0,
            "spend_usd_cents": 0,
            "execution_authorized": False,
            "production_admissible": False,
            "admitted_at": utc_text(now),
        }
        receipt["content_sha256"] = digest(ADMISSION_RECEIPT_DOMAIN, receipt)
        validate_admission_receipt(receipt, source_commit, contract, proposal, now)
        write_exclusive(output, canonical(receipt) + b"\n")
        output_written = True
        write_terminal(terminal_path, {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.attestation_set_countersignature_terminal.v1",
            "status": "PASS_T22_A1_OWNER_COUNTERSIGNED_ATTESTATION_SET_ADMISSION",
            "failure_code": None,
            "source_commit": source_commit,
            "challenge_content_sha256": challenge["content_sha256"],
            "admitted_set_receipt_sha256": receipt["content_sha256"],
            "private_bundle_read": True,
            "stable_host_identity_source_read": False,
            "credentials_accessed": False,
            "network_accessed": False,
            "services_started": 0,
            "faults_injected": 0,
            "automatic_retry_allowed": False,
            "execution_authorized": False,
            "production_admissible": False,
            "completed_at": utc_text(now),
        })
        return receipt
    except (SafeFailure, OSError) as error:
        failure_code = str(error) if isinstance(error, SafeFailure) else "E_COUNTERSIGNATURE_LOCAL_IO"
        if output_written and output.is_file() and not output.is_symlink():
            output.unlink()
        if not terminal_path.exists():
            write_terminal(terminal_path, {
                "schema": "agent_bridge.biocortex.track_b.t22_a1.attestation_set_countersignature_terminal.v1",
                "status": "FAIL_T22_A1_OWNER_COUNTERSIGNED_ATTESTATION_SET_ADMISSION_NO_RETRY",
                "failure_code": failure_code,
                "source_commit": source_commit,
                "challenge_content_sha256": challenge["content_sha256"],
                "private_bundle_read": bundle_read,
                "stable_host_identity_source_read": False,
                "credentials_accessed": False,
                "network_accessed": False,
                "services_started": 0,
                "faults_injected": 0,
                "automatic_retry_allowed": False,
                "execution_authorized": False,
                "production_admissible": False,
                "completed_at": utc_text(now),
            })
        raise SafeFailure(failure_code) from error


def status() -> dict:
    collection, _attestation, _contract, proposal, _schema = load_inputs()
    present = collection.ANCHOR_PATH.is_file() and not collection.ANCHOR_PATH.is_symlink()
    valid = False
    if present:
        try:
            collection.validate_anchor(json.loads(collection.ANCHOR_PATH.read_text()), proposal)
            valid = True
        except (RuntimeError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            valid = False
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.attestation_set_countersignature_status.v0",
        "status": "BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_REQUIRED" if not present else (
            "BLOCKED_EXACT_PRIVATE_THREE_DOMAIN_BUNDLE_AND_OWNER_COUNTERSIGNATURE_REQUIRED" if valid
            else "BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_INVALID"
        ),
        "owner_trust_anchor_present": present,
        "owner_trust_anchor_valid": valid,
        "private_bundle_read": False,
        "stable_host_identity_source_read": False,
        "credentials_accessed": False,
        "network_accessed": False,
        "external_hosts_contacted": 0,
        "services_started": 0,
        "faults_injected": 0,
        "execution_authorized": False,
        "production_admissible": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    generate = commands.add_parser("generate")
    generate.add_argument("--bundle", type=Path, required=True)
    generate.add_argument("--artifact-root", type=Path, required=True)
    generate.add_argument("--maximum-lifetime-seconds", type=int, default=3600)
    generate.add_argument("--out", type=Path, required=True)
    admission = commands.add_parser("admit")
    admission.add_argument("--challenge", type=Path, required=True)
    admission.add_argument("--owner-signature", type=Path, required=True)
    admission.add_argument("--bundle", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "status":
        print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
        return
    collection, _attestation, contract, proposal, _schema = load_inputs()
    require(collection.ANCHOR_PATH.is_file() and not collection.ANCHOR_PATH.is_symlink(), "E_OWNER_ANCHOR_REQUIRED")
    anchor = json.loads(collection.ANCHOR_PATH.read_text())
    source_commit = collection.current_source_commit()
    now = datetime.now(timezone.utc)
    if arguments.command == "generate":
        challenge = build_challenge(
            anchor, contract, proposal, arguments.bundle.resolve(strict=True), source_commit,
            arguments.artifact_root, now, arguments.maximum_lifetime_seconds,
        )
        prepare_challenge_output(arguments.out, arguments.artifact_root)
        write_exclusive(arguments.out, canonical(challenge) + b"\n")
        print(json.dumps({
            "status": "EXACT_ATTESTATION_SET_COUNTERSIGNATURE_GENERATED_AWAITING_OWNER_SIGNATURE",
            "challenge_path": str(arguments.out),
            "content_sha256": challenge["content_sha256"],
            "attestation_set_sha256": challenge["verified_set"]["attestation_set_sha256"],
            "signature_namespace": SIGNATURE_NAMESPACE,
            "execution_authorized": False,
        }, sort_keys=True, separators=(",", ":")))
        return
    receipt = admit(
        arguments.challenge.resolve(strict=True), arguments.owner_signature.resolve(strict=True),
        arguments.bundle.resolve(strict=True), source_commit, now,
    )
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except SafeFailure as error:
        print(json.dumps({"status": "BLOCKED_FAIL_CLOSED", "failure_code": str(error)}, sort_keys=True, separators=(",", ":")))
        sys.exit(1)
