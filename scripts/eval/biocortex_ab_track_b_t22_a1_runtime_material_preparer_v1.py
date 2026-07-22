"""Single-use, zero-network T22-A1 private runtime material preparer.

The preparer remains unreachable until the exact challenge and detached owner
signature verify. It consumes only a private endpoint manifest and locally
pinned cryptographic executables. It grants no execution or network authority.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
AUTHORIZATION_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_runtime_preparation_authorization_v1.py"
TERMINAL_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/runtime-preparation-terminal/v1\0"
MAX_PRIVATE_JSON_BYTES = 256 * 1024
MAX_TOOL_BYTES = 128 * 1024 * 1024
EXPECTED_MATERIAL_NAMES = {
    "ca.crt",
    "coordinator.crt", "coordinator.key",
    "domain-1.crt", "domain-1.key",
    "domain-2.crt", "domain-2.key",
    "domain-3.crt", "domain-3.key",
    "coordinator-runtime", "coordinator-runtime.pub",
}


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


def load_authorization_module():
    return load_module("t22a1_runtime_preparation_for_material_preparer", AUTHORIZATION_SOURCE)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def terminal_digest(value: object) -> str:
    return hashlib.sha256(TERMINAL_DOMAIN + canonical(value)).hexdigest()


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_private_directory(path: Path, create: bool) -> None:
    require(path.is_absolute() and not path.is_symlink(), "E_RUNTIME_PREPARATION_PRIVATE_DIRECTORY")
    if not path.exists() and create:
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
        path.chmod(0o700)
    require(path.is_dir() and not path.is_symlink(), "E_RUNTIME_PREPARATION_PRIVATE_DIRECTORY")
    require(path.stat().st_mode & 0o077 == 0, "E_RUNTIME_PREPARATION_DIRECTORY_PERMISSIONS")


def write_exclusive(path: Path, raw: bytes) -> None:
    require(path.is_absolute() and not path.exists() and not path.is_symlink(), "E_RUNTIME_PREPARATION_OUTPUT_EXISTS")
    ensure_private_directory(path.parent, create=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def sha256_file(path: Path, maximum_bytes: int, code: str) -> str:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), code)
    metadata = path.stat()
    require(stat.S_ISREG(metadata.st_mode) and 0 < metadata.st_size <= maximum_bytes, code)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_tool(path_text: str, expected_sha256: str, code: str) -> Path:
    path = Path(path_text)
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), code)
    resolved = path.resolve(strict=True)
    repository = ROOT.resolve()
    require(repository not in (resolved, *resolved.parents), code)
    require(resolved.stat().st_mode & 0o111 != 0, code)
    require(sha256_file(resolved, MAX_TOOL_BYTES, code) == expected_sha256, code)
    return resolved


def run_tool(executable: Path, arguments: list[str], code: str, input_bytes: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            [str(executable), *arguments], input=input_bytes,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={
                "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
                "HOME": "/nonexistent", "OPENSSL_CONF": "/dev/null",
            },
            timeout=30, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise SafeFailure(f"{code}_TIMEOUT") from error
    require(result.returncode == 0, code)
    return result.stdout


def read_endpoint_manifest(path: Path, runtime, source_commit: str, run_id: str, expected_content_sha256: str) -> dict:  # noqa: ANN001
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "E_ENDPOINT_MANIFEST_FILE")
    metadata = path.stat()
    require(stat.S_ISREG(metadata.st_mode) and 0 < metadata.st_size <= MAX_PRIVATE_JSON_BYTES, "E_ENDPOINT_MANIFEST_FILE")
    require(metadata.st_mode & 0o077 == 0, "E_ENDPOINT_MANIFEST_PERMISSIONS")
    raw = path.read_bytes()
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "E_ENDPOINT_MANIFEST_FRAMING")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SafeFailure("E_ENDPOINT_MANIFEST_JSON") from error
    require(raw == canonical(value) + b"\n", "E_ENDPOINT_MANIFEST_NOT_CANONICAL")
    endpoint_schema, _credential_schema, _message_schema = foreign_call(runtime.load_schemas)
    foreign_call(runtime.validate_endpoint_manifest, value, endpoint_schema, source_commit, run_id)
    require(value["content_sha256"] == expected_content_sha256, "E_ENDPOINT_MANIFEST_OWNER_BINDING")
    return value


def reserve_challenge_use(root: Path, challenge: dict, source_commit: str, now: datetime) -> tuple[Path, Path]:
    ensure_private_directory(root, create=False)
    uses = root / "runtime-preparation-uses"
    ensure_private_directory(uses, create=True)
    stem = challenge["content_sha256"]
    reservation_path = uses / f"{stem}.reserved.json"
    terminal_path = uses / f"{stem}.terminal.json"
    reservation = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.runtime_preparation_use_reservation.v1",
        "status": "RUNTIME_PREPARATION_CHALLENGE_RESERVED_SINGLE_USE",
        "run_id": challenge["target"]["run_id"],
        "source_commit": source_commit,
        "challenge_content_sha256": stem,
        "reserved_at": utc_text(now),
        "automatic_retry_allowed": False,
        "network_authorized": False,
        "execution_authorized": False,
        "production_admissible": False,
    }
    write_exclusive(reservation_path, canonical(reservation) + b"\n")
    return reservation_path, terminal_path


def write_terminal(path: Path, body: dict) -> dict:
    value = dict(body)
    value["content_sha256"] = terminal_digest(value)
    write_exclusive(path, canonical(value) + b"\n")
    return value


def safe_remove_private_tree(path: Path, expected_parent: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return True
    require(path.parent.resolve(strict=False) == expected_parent.resolve(strict=False), "E_RUNTIME_PREPARATION_CLEANUP_SCOPE")
    require(path.is_dir() and not path.is_symlink(), "E_RUNTIME_PREPARATION_CLEANUP_SCOPE")
    shutil.rmtree(path)
    return not path.exists()


def certificate_spki(openssl: Path, certificate: Path) -> bytes:
    public_key = run_tool(openssl, ["x509", "-in", str(certificate), "-pubkey", "-noout"], "E_CERTIFICATE_PUBLIC_KEY")
    return run_tool(openssl, ["pkey", "-pubin", "-outform", "DER"], "E_CERTIFICATE_SPKI", public_key)


def private_key_spki(openssl: Path, private_key: Path) -> bytes:
    return run_tool(openssl, ["pkey", "-in", str(private_key), "-pubout", "-outform", "DER"], "E_PRIVATE_KEY_SPKI")


def certificate_not_after(openssl: Path, certificate: Path) -> datetime:
    raw = run_tool(openssl, ["x509", "-in", str(certificate), "-noout", "-enddate"], "E_CERTIFICATE_EXPIRY")
    require(raw.startswith(b"notAfter=") and raw.endswith(b"\n"), "E_CERTIFICATE_EXPIRY")
    try:
        parsed = datetime.strptime(raw[len(b"notAfter="):].decode().strip(), "%b %d %H:%M:%S %Y %Z")
    except (UnicodeDecodeError, ValueError) as error:
        raise SafeFailure("E_CERTIFICATE_EXPIRY") from error
    return parsed.replace(tzinfo=timezone.utc)


def validate_leaf_certificate(
    openssl: Path,
    ca_certificate: Path,
    certificate: Path,
    private_key: Path,
    usages: list[str],
    required_not_after: datetime,
    overlay_ip: str | None,
) -> dict:
    require(certificate.stat().st_mode & 0o077 == 0 and private_key.stat().st_mode & 0o077 == 0, "E_RUNTIME_KEY_PERMISSIONS")
    run_tool(openssl, ["verify", "-CAfile", str(ca_certificate), str(certificate)], "E_CERTIFICATE_CHAIN")
    certificate_key = certificate_spki(openssl, certificate)
    require(certificate_key == private_key_spki(openssl, private_key), "E_CERTIFICATE_KEY_MISMATCH")
    purpose = run_tool(openssl, ["x509", "-in", str(certificate), "-noout", "-purpose"], "E_CERTIFICATE_PURPOSE")
    require(
        (b"SSL client : Yes" in purpose) == ("TLS_WEB_CLIENT_AUTHENTICATION" in usages)
        and (b"SSL server : Yes" in purpose) == ("TLS_WEB_SERVER_AUTHENTICATION" in usages),
        "E_CERTIFICATE_PURPOSE",
    )
    if "TLS_WEB_SERVER_AUTHENTICATION" in usages:
        san = run_tool(openssl, ["x509", "-in", str(certificate), "-noout", "-ext", "subjectAltName"], "E_CERTIFICATE_SAN")
        require(overlay_ip is not None and f"IP Address:{overlay_ip}".encode() in san, "E_CERTIFICATE_SAN")
    not_after = certificate_not_after(openssl, certificate)
    require(not_after >= required_not_after, "E_CERTIFICATE_VALIDITY_MARGIN")
    return {
        "certificate_sha256": sha256_file(certificate, MAX_PRIVATE_JSON_BYTES, "E_CERTIFICATE_FILE"),
        "spki_sha256": hashlib.sha256(certificate_key).hexdigest(),
        "not_after": utc_text(not_after),
    }


def generate_materials(
    staging: Path,
    endpoint: dict,
    challenge: dict,
    now: datetime,
    openssl: Path,
    ssh_keygen: Path,
) -> dict:
    ensure_private_directory(staging, create=True)
    planned_expiry = foreign_call(load_authorization_module().parse_time,
        challenge["target"]["planned_execution_expires_at"], "E_PREPARATION_PLANNED_EXPIRY",
    )
    required_not_after = planned_expiry + timedelta(seconds=challenge["target"]["credential_validity_margin_seconds"])
    lifetime_days = max(1, math.ceil((required_not_after - now).total_seconds() / 86400) + 1)
    require(lifetime_days <= 4, "E_CERTIFICATE_LIFETIME")
    old_umask = os.umask(0o077)
    try:
        ca_key = staging / "ca.key"
        ca_certificate = staging / "ca.crt"
        run_tool(openssl, ["genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", str(ca_key)], "E_CA_KEY_GENERATION")
        run_tool(openssl, [
            "req", "-x509", "-new", "-key", str(ca_key), "-sha256", "-days", str(lifetime_days),
            "-subj", f"/CN=t22-a1-{challenge['target']['run_id']}-ca",
            "-addext", "basicConstraints=critical,CA:TRUE,pathlen:0",
            "-addext", "keyUsage=critical,keyCertSign,cRLSign", "-out", str(ca_certificate),
        ], "E_CA_CERTIFICATE_GENERATION")
        identities = [("coordinator", None), *[
            (domain["domain_id"], domain["overlay_ip"]) for domain in endpoint["domains"]
        ]]
        for index, (identity, overlay_ip) in enumerate(identities):
            private_key = staging / f"{identity}.key"
            request = staging / f"{identity}.csr"
            certificate = staging / f"{identity}.crt"
            extensions = staging / f"{identity}.ext"
            run_tool(openssl, ["genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", str(private_key)], "E_LEAF_KEY_GENERATION")
            run_tool(openssl, ["req", "-new", "-key", str(private_key), "-subj", f"/CN={identity}.{challenge['target']['run_id']}", "-out", str(request)], "E_CERTIFICATE_REQUEST")
            usage = "clientAuth" if identity == "coordinator" else "clientAuth,serverAuth"
            extension_lines = [
                "basicConstraints=critical,CA:FALSE",
                "keyUsage=critical,digitalSignature",
                f"extendedKeyUsage={usage}",
            ]
            if overlay_ip is not None:
                extension_lines.append(f"subjectAltName=IP:{overlay_ip}")
            write_exclusive(extensions, ("\n".join(extension_lines) + "\n").encode())
            serial_arguments = ["-CAcreateserial"] if index == 0 else ["-CAserial", str(staging / "ca.srl")]
            run_tool(openssl, [
                "x509", "-req", "-in", str(request), "-CA", str(ca_certificate), "-CAkey", str(ca_key),
                *serial_arguments, "-out", str(certificate), "-days", str(lifetime_days), "-sha256",
                "-extfile", str(extensions),
            ], "E_LEAF_CERTIFICATE_GENERATION")
        runtime_private = staging / "coordinator-runtime"
        run_tool(ssh_keygen, [
            "-q", "-t", "ed25519", "-N", "", "-C", "T22_A1_COORDINATOR_RUNTIME",
            "-f", str(runtime_private),
        ], "E_COORDINATOR_RUNTIME_KEY_GENERATION")
    finally:
        os.umask(old_umask)

    for path in staging.iterdir():
        if path.is_file() and not path.is_symlink():
            path.chmod(0o600)
    run_tool(openssl, ["verify", "-CAfile", str(ca_certificate), str(ca_certificate)], "E_CA_SELF_VERIFICATION")
    ca_spki = certificate_spki(openssl, ca_certificate)
    require(certificate_not_after(openssl, ca_certificate) >= required_not_after, "E_CA_VALIDITY_MARGIN")
    leaf_metadata: dict[str, dict] = {}
    endpoint_by_id = {domain["domain_id"]: domain for domain in endpoint["domains"]}
    for identity in ("coordinator", "domain-1", "domain-2", "domain-3"):
        usages = ["TLS_WEB_CLIENT_AUTHENTICATION"] if identity == "coordinator" else [
            "TLS_WEB_CLIENT_AUTHENTICATION", "TLS_WEB_SERVER_AUTHENTICATION",
        ]
        overlay_ip = None if identity == "coordinator" else endpoint_by_id[identity]["overlay_ip"]
        leaf_metadata[identity] = validate_leaf_certificate(
            openssl, ca_certificate, staging / f"{identity}.crt", staging / f"{identity}.key",
            usages, required_not_after, overlay_ip,
        )
    runtime_private = staging / "coordinator-runtime"
    runtime_public = staging / "coordinator-runtime.pub"
    require(runtime_private.is_file() and runtime_public.is_file(), "E_COORDINATOR_RUNTIME_KEY_FILES")
    derived = run_tool(ssh_keygen, ["-y", "-f", str(runtime_private)], "E_COORDINATOR_RUNTIME_KEY_VERIFICATION")
    parts = derived.strip().split()
    require(len(parts) >= 2 and parts[0] == b"ssh-ed25519", "E_COORDINATOR_RUNTIME_PUBLIC_KEY")
    key_parts = parts[:2]
    canonical_public_key = b" ".join(key_parts) + b"\n"
    require(runtime_public.read_bytes().split()[:2] == key_parts, "E_COORDINATOR_RUNTIME_KEY_MISMATCH")
    runtime_public.write_bytes(canonical_public_key)
    runtime_public.chmod(0o600)
    for transient in [
        staging / "ca.key", staging / "ca.srl",
        *[staging / f"{identity}.{suffix}" for identity in ("coordinator", "domain-1", "domain-2", "domain-3") for suffix in ("csr", "ext")],
    ]:
        if transient.exists():
            transient.unlink()
    require({path.name for path in staging.iterdir()} == EXPECTED_MATERIAL_NAMES, "E_RUNTIME_MATERIAL_FILE_SET")
    require(all(path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0 for path in staging.iterdir()), "E_RUNTIME_MATERIAL_PERMISSIONS")
    return {
        "ca": {
            "certificate_sha256": sha256_file(ca_certificate, MAX_PRIVATE_JSON_BYTES, "E_CA_CERTIFICATE_FILE"),
            "spki_sha256": hashlib.sha256(ca_spki).hexdigest(),
        },
        "leaves": leaf_metadata,
        "coordinator_runtime_public_key": canonical_public_key,
        "coordinator_runtime_public_key_sha256": hashlib.sha256(canonical_public_key).hexdigest(),
        "required_not_after": utc_text(required_not_after),
    }


def build_credential_manifest(challenge: dict, endpoint: dict, metadata: dict, credentials_directory: Path, runtime) -> dict:  # noqa: ANN001
    ca_spki = metadata["ca"]["spki_sha256"]

    def credential(identity: str, usages: list[str]) -> dict:
        leaf = metadata["leaves"][identity]
        return {
            "identity": identity,
            "certificate_path": str(credentials_directory / f"{identity}.crt"),
            "private_key_path": str(credentials_directory / f"{identity}.key"),
            "certificate_sha256": leaf["certificate_sha256"],
            "spki_sha256": leaf["spki_sha256"],
            "issuer_spki_sha256": ca_spki,
            "not_after": leaf["not_after"],
            "extended_key_usage": usages,
            "private_key_file_mode": "0600",
            "private_key_export_allowed": False,
        }

    value = {
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
        "run_id": challenge["target"]["run_id"],
        "source_commit": challenge["bindings"]["source_commit"],
        "private_endpoint_manifest_sha256": endpoint["content_sha256"],
        "ca": {
            "certificate_path": str(credentials_directory / "ca.crt"),
            "certificate_sha256": metadata["ca"]["certificate_sha256"],
            "spki_sha256": ca_spki,
            "self_signed_private_run_ca": True,
            "private_key_path_present": False,
        },
        "coordinator": credential("coordinator", ["TLS_WEB_CLIENT_AUTHENTICATION"]),
        "domains": [credential(f"domain-{number}", [
            "TLS_WEB_CLIENT_AUTHENTICATION", "TLS_WEB_SERVER_AUTHENTICATION",
        ]) for number in (1, 2, 3)],
        "coordinator_runtime_signing_key": {
            "identity": "coordinator-runtime",
            "public_key_path": str(credentials_directory / "coordinator-runtime.pub"),
            "private_key_path": str(credentials_directory / "coordinator-runtime"),
            "public_key_sha256": metadata["coordinator_runtime_public_key_sha256"],
            "signature_scheme": "OPENSSH_SSHSIG_ED25519",
            "request_signature_namespace": "agent-bridge-t22-a1-coordinator-message-v1",
            "private_key_file_mode": "0600",
            "private_key_export_allowed": False,
        },
        "mutual_tls_required": True,
        "certificate_chain_and_key_match_verification_required": True,
        "certificate_valid_through_execution_expiry_required": True,
        "ambient_credential_discovery_allowed": False,
        "credential_paths_in_repository_allowed": False,
        "private_key_material_embedded": False,
    }
    value["content_sha256"] = runtime.digest(runtime.CREDENTIAL_DOMAIN, value)
    _endpoint_schema, credential_schema, _message_schema = foreign_call(runtime.load_schemas)
    execution_expiry = foreign_call(load_authorization_module().parse_time,
        challenge["target"]["planned_execution_expires_at"], "E_PREPARATION_PLANNED_EXPIRY",
    )
    foreign_call(
        runtime.validate_credential_manifest, value, credential_schema,
        challenge["bindings"]["source_commit"], challenge["target"]["run_id"],
        endpoint["content_sha256"], execution_expiry,
    )
    return value


def prepare(
    challenge_path: Path,
    owner_signature_path: Path,
    source_commit: str,
    now: datetime,
    material_generator: Callable[..., dict] = generate_materials,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict:
    authorization_module = load_authorization_module()
    collection, runtime, _contract, proposal, _schema = authorization_module.load_inputs()
    require(collection.ANCHOR_PATH.is_file() and not collection.ANCHOR_PATH.is_symlink(), "E_OWNER_ANCHOR_REQUIRED")
    try:
        anchor = json.loads(collection.ANCHOR_PATH.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SafeFailure("E_OWNER_ANCHOR_FILE") from error
    authorization = foreign_call(
        authorization_module.verify_challenge_files,
        challenge_path, owner_signature_path, anchor, source_commit, now,
    )
    challenge, _raw = foreign_call(authorization_module.parse_canonical_challenge, challenge_path)
    root = Path(challenge["target"]["private_artifact_root"])
    foreign_call(authorization_module.validate_paths, challenge["target"])
    ensure_private_directory(root, create=False)
    endpoint_path = Path(challenge["target"]["private_endpoint_manifest_path"])
    manifest_path = Path(challenge["target"]["runtime_credential_manifest_output_path"])
    credentials_directory = root / "credentials"
    staging = root / f".runtime-preparation-{challenge['content_sha256']}.staging"
    require(endpoint_path.is_file() and not endpoint_path.is_symlink(), "E_ENDPOINT_MANIFEST_FILE")
    require(not manifest_path.exists() and not manifest_path.is_symlink(), "E_RUNTIME_CREDENTIAL_MANIFEST_EXISTS")
    require(not credentials_directory.exists() and not credentials_directory.is_symlink(), "E_RUNTIME_CREDENTIAL_DIRECTORY_EXISTS")
    require(not staging.exists() and not staging.is_symlink(), "E_RUNTIME_PREPARATION_STAGING_EXISTS")
    _reservation_path, terminal_path = reserve_challenge_use(root, challenge, source_commit, now)
    endpoint_read = False
    generation_started = False
    published_credentials = False
    manifest_written = False
    try:
        openssl = validate_tool(
            challenge["target"]["openssl_executable_path"], challenge["target"]["openssl_executable_sha256"],
            "E_OPENSSL_TOOL_BINDING",
        )
        ssh_keygen = validate_tool(
            challenge["target"]["ssh_keygen_executable_path"], challenge["target"]["ssh_keygen_executable_sha256"],
            "E_SSH_KEYGEN_TOOL_BINDING",
        )
        endpoint_read = True
        endpoint = read_endpoint_manifest(
            endpoint_path, runtime, source_commit, challenge["target"]["run_id"],
            challenge["bindings"]["private_endpoint_manifest_content_sha256"],
        )
        generation_started = True
        metadata = material_generator(staging, endpoint, challenge, now, openssl, ssh_keygen)
        completion_time = clock()
        require(
            completion_time.tzinfo is not None and completion_time.utcoffset().total_seconds() == 0,
            "E_RUNTIME_PREPARATION_COMPLETION_TIME",
        )
        preparation_expires = foreign_call(
            authorization_module.parse_time,
            challenge["preparation_authority"]["expires_at"], "E_PREPARATION_EXPIRES_AT",
        )
        require(completion_time < preparation_expires, "E_PREPARATION_NOT_CURRENT_AFTER_GENERATION")
        require(
            sha256_file(openssl, MAX_TOOL_BYTES, "E_OPENSSL_TOOL_BINDING") == challenge["target"]["openssl_executable_sha256"]
            and sha256_file(ssh_keygen, MAX_TOOL_BYTES, "E_SSH_KEYGEN_TOOL_BINDING") == challenge["target"]["ssh_keygen_executable_sha256"],
            "E_RUNTIME_PREPARATION_TOOL_CHANGED",
        )
        manifest = build_credential_manifest(challenge, endpoint, metadata, credentials_directory, runtime)
        staging.rename(credentials_directory)
        published_credentials = True
        manifest_written = True
        write_exclusive(manifest_path, canonical(manifest) + b"\n")
        body = {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.runtime_preparation_terminal.v1",
            "status": "PASS_T22_A1_ZERO_NETWORK_PRIVATE_RUNTIME_MATERIAL_PREPARATION",
            "failure_code": None,
            "run_id": challenge["target"]["run_id"],
            "source_commit": source_commit,
            "challenge_content_sha256": challenge["content_sha256"],
            "owner_signature_sha256": authorization["owner_signature_sha256"],
            "exact_three_domain_attestation_set_sha256": challenge["bindings"]["exact_three_domain_attestation_set_sha256"],
            "owner_countersigned_attestation_set_receipt_sha256": challenge["bindings"]["owner_countersigned_attestation_set_receipt_sha256"],
            "private_endpoint_manifest_content_sha256": endpoint["content_sha256"],
            "runtime_credential_manifest_content_sha256": manifest["content_sha256"],
            "coordinator_runtime_public_key_sha256": metadata["coordinator_runtime_public_key_sha256"],
            "openssl_executable_sha256": challenge["target"]["openssl_executable_sha256"],
            "ssh_keygen_executable_sha256": challenge["target"]["ssh_keygen_executable_sha256"],
            "certificate_count": 5,
            "retained_private_key_count": 5,
            "private_ca_signing_key_retained": False,
            "certificate_chain_key_eku_expiry_and_endpoint_bindings_verified": True,
            "private_endpoint_manifest_instance_read": True,
            "raw_endpoint_values_in_receipt": False,
            "private_key_material_in_manifest_or_receipt": False,
            "ambient_or_preexisting_credentials_accessed": False,
            "network_accessed": False,
            "external_hosts_contacted": 0,
            "listeners_started": 0,
            "services_started": 0,
            "faults_injected": 0,
            "spend_usd_cents": 0,
            "automatic_retry_allowed": False,
            "execution_authorized": False,
            "production_admissible": False,
            "completed_at": utc_text(completion_time),
        }
        return write_terminal(terminal_path, body)
    except (SafeFailure, OSError) as error:
        failure_code = str(error) if isinstance(error, SafeFailure) else "E_RUNTIME_PREPARATION_LOCAL_IO"
        partial_destroyed = True
        try:
            if manifest_written and manifest_path.is_file() and not manifest_path.is_symlink():
                manifest_path.unlink()
            if published_credentials:
                partial_destroyed = safe_remove_private_tree(credentials_directory, root) and partial_destroyed
            if staging.exists():
                partial_destroyed = safe_remove_private_tree(staging, root) and partial_destroyed
            partial_destroyed = (
                partial_destroyed and not manifest_path.exists()
                and not credentials_directory.exists() and not staging.exists()
            )
        except (SafeFailure, OSError):
            partial_destroyed = False
        body = {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.runtime_preparation_terminal.v1",
            "status": "FAIL_T22_A1_ZERO_NETWORK_PRIVATE_RUNTIME_MATERIAL_PREPARATION_NO_RETRY",
            "failure_code": failure_code,
            "run_id": challenge["target"]["run_id"],
            "source_commit": source_commit,
            "challenge_content_sha256": challenge["content_sha256"],
            "private_endpoint_manifest_instance_read": endpoint_read,
            "runtime_material_generation_started": generation_started,
            "partial_runtime_material_destroyed": partial_destroyed,
            "raw_endpoint_values_in_receipt": False,
            "private_key_material_in_receipt": False,
            "ambient_or_preexisting_credentials_accessed": False,
            "network_accessed": False,
            "external_hosts_contacted": 0,
            "listeners_started": 0,
            "services_started": 0,
            "faults_injected": 0,
            "spend_usd_cents": 0,
            "automatic_retry_allowed": False,
            "execution_authorized": False,
            "production_admissible": False,
            "completed_at": utc_text(datetime.now(timezone.utc)),
        }
        if not terminal_path.exists():
            write_terminal(terminal_path, body)
        raise SafeFailure(failure_code) from error


def status() -> dict:
    authorization_status = load_authorization_module().status()
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.runtime_material_preparer_status.v0",
        "status": "BLOCKED_EXACT_OWNER_SIGNED_RUNTIME_PREPARATION_CHALLENGE_REQUIRED"
        if authorization_status["owner_trust_anchor_valid"] else authorization_status["status"],
        "owner_trust_anchor_present": authorization_status["owner_trust_anchor_present"],
        "owner_trust_anchor_valid": authorization_status["owner_trust_anchor_valid"],
        "private_endpoint_manifest_instance_read": False,
        "runtime_credential_files_read": False,
        "runtime_material_generated": False,
        "ambient_or_preexisting_credentials_accessed": False,
        "network_accessed": False,
        "external_hosts_contacted": 0,
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
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--challenge", type=Path, required=True)
    prepare_parser.add_argument("--owner-signature", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "status":
        print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
        return
    authorization_module = load_authorization_module()
    collection, _runtime, _contract, _proposal, _schema = authorization_module.load_inputs()
    source_commit = collection.current_source_commit()
    terminal = prepare(
        arguments.challenge.resolve(strict=True), arguments.owner_signature.resolve(strict=True),
        source_commit, datetime.now(timezone.utc),
    )
    print(json.dumps(terminal, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except SafeFailure as error:
        print(json.dumps({"status": "BLOCKED_FAIL_CLOSED", "failure_code": str(error)}, sort_keys=True, separators=(",", ":")))
        sys.exit(1)
