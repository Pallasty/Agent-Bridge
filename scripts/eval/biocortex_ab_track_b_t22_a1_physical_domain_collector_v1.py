"""Owner-authorized T22-A1 physical-host domain attestation collector.

No stable identity is read until the exact collection challenge and detached
owner signature have verified, the challenge has been atomically reserved for
one use, the bound domain key has been checked, and hostname/platform match.
Cloud VMs remain unsupported until a provider-specific identity verifier is
frozen.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import plistlib
import shutil
import socket
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
CHALLENGE_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_collection_challenge_v1.py"
ATTESTATION_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_attestation_v1.py"
RECEIPT_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-collection-terminal/v1\0"
IDENTITY_DOMAINS = {
    "machine": b"agent-bridge/biocortex/track-b/t22-a1/machine-identity/v1\0",
    "hardware": b"agent-bridge/biocortex/track-b/t22-a1/hardware-identity/v1\0",
    "boot": b"agent-bridge/biocortex/track-b/t22-a1/boot-identity/v1\0",
}
MAX_IDENTITY_BYTES = 4096


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


def load_challenge_module():
    return load_module("t22a1_collection_challenge_for_collector", CHALLENGE_SOURCE)


def load_attestation_module():
    return load_module("t22a1_domain_attestation_for_collector", ATTESTATION_SOURCE)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def receipt_digest(value: object) -> str:
    return hashlib.sha256(RECEIPT_DOMAIN + canonical(value)).hexdigest()


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def identity_digest(kind: str, raw: bytes) -> str:
    require(kind in IDENTITY_DOMAINS, "E_IDENTITY_KIND")
    normalized = raw.strip(b"\x00\r\n \t")
    require(0 < len(normalized) <= MAX_IDENTITY_BYTES, f"E_{kind.upper()}_IDENTITY_VALUE")
    return hashlib.sha256(IDENTITY_DOMAINS[kind] + normalized).hexdigest()


def ensure_private_directory(path: Path, create: bool) -> None:
    require(path.is_absolute() and not path.is_symlink(), "E_PRIVATE_DIRECTORY")
    if not path.exists() and create:
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
        path.chmod(0o700)
    require(path.is_dir() and not path.is_symlink(), "E_PRIVATE_DIRECTORY")
    require(path.stat().st_mode & 0o077 == 0, "E_PRIVATE_DIRECTORY_PERMISSIONS")


def write_exclusive(path: Path, raw: bytes) -> None:
    require(path.is_absolute() and not path.exists() and not path.is_symlink(), "E_PRIVATE_OUTPUT_EXISTS")
    ensure_private_directory(path.parent, create=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def validate_private_key(path: Path) -> None:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "E_DOMAIN_PRIVATE_KEY_FILE")
    metadata = path.stat()
    require(stat.S_ISREG(metadata.st_mode) and 0 < metadata.st_size <= 64 * 1024, "E_DOMAIN_PRIVATE_KEY_FILE")
    require(metadata.st_mode & 0o077 == 0, "E_DOMAIN_PRIVATE_KEY_PERMISSIONS")
    repository = ROOT.resolve()
    resolved = path.resolve(strict=True)
    require(repository not in (resolved, *resolved.parents), "E_DOMAIN_PRIVATE_KEY_IN_REPOSITORY")


def verify_private_key_matches(private_key: Path, expected_public_key: bytes) -> None:
    validate_private_key(private_key)
    ssh_keygen = shutil.which("ssh-keygen")
    require(ssh_keygen is not None, "E_SSH_KEYGEN_MISSING")
    try:
        result = subprocess.run(
            [ssh_keygen, "-y", "-f", str(private_key)], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C", "LC_ALL": "C"},
            timeout=10, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise SafeFailure("E_DOMAIN_PRIVATE_KEY_TIMEOUT") from error
    require(result.returncode == 0, "E_DOMAIN_PRIVATE_KEY_UNUSABLE")
    challenge_module = load_challenge_module()
    derived = foreign_call(challenge_module.canonical_public_key_bytes, result.stdout)
    require(derived == expected_public_key, "E_DOMAIN_PRIVATE_KEY_MISMATCH")


def normalize_platform(system: str, machine: str) -> tuple[str, str]:
    operating_system = {"Linux": "LINUX", "Darwin": "MACOS"}.get(system)
    architecture = {
        "x86_64": "X86_64", "amd64": "X86_64", "AMD64": "X86_64",
        "aarch64": "AARCH64", "arm64": "AARCH64", "ARM64": "AARCH64",
    }.get(machine)
    require(operating_system is not None, "E_HOST_OPERATING_SYSTEM")
    require(architecture is not None, "E_HOST_ARCHITECTURE")
    return operating_system, architecture


def observe_host() -> dict:
    operating_system, architecture = normalize_platform(platform.system(), platform.machine())
    hostname = socket.gethostname()
    require(isinstance(hostname, str) and 1 <= len(hostname) <= 255, "E_HOSTNAME")
    kernel_release = platform.release()
    require(isinstance(kernel_release, str) and 1 <= len(kernel_release) <= 128, "E_KERNEL_RELEASE")
    return {
        "hostname": hostname,
        "operating_system": operating_system,
        "architecture": architecture,
        "kernel_release": kernel_release,
    }


def read_identity_file(path: Path, code: str) -> bytes:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), code)
    metadata = path.stat()
    require(stat.S_ISREG(metadata.st_mode) and 0 < metadata.st_size <= MAX_IDENTITY_BYTES, code)
    raw = path.read_bytes()
    require(0 < len(raw.strip(b"\x00\r\n \t")) <= MAX_IDENTITY_BYTES, code)
    return raw


def first_identity_file(paths: tuple[Path, ...], code: str) -> bytes:
    for path in paths:
        if path.is_file() and not path.is_symlink():
            return read_identity_file(path, code)
    raise SafeFailure(code)


def read_linux_identity() -> dict:
    return {
        "machine": first_identity_file((Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")), "E_LINUX_MACHINE_ID_SOURCE"),
        "hardware": first_identity_file((
            Path("/sys/class/dmi/id/product_uuid"),
            Path("/sys/firmware/devicetree/base/serial-number"),
            Path("/sys/class/dmi/id/product_serial"),
        ), "E_LINUX_HARDWARE_IDENTITY_SOURCE"),
        "boot": read_identity_file(Path("/proc/sys/kernel/random/boot_id"), "E_LINUX_BOOT_ID_SOURCE"),
    }


def run_local_identity_command(arguments: list[str], code: str) -> bytes:
    executable = shutil.which(arguments[0])
    require(executable is not None, code)
    try:
        result = subprocess.run(
            [executable, *arguments[1:]], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C", "LC_ALL": "C"},
            timeout=10, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise SafeFailure(code) from error
    require(result.returncode == 0 and 0 < len(result.stdout) <= 256 * 1024, code)
    return result.stdout


def read_macos_identity() -> dict:
    try:
        plist = plistlib.loads(run_local_identity_command(
            ["ioreg", "-a", "-rd1", "-c", "IOPlatformExpertDevice"], "E_MACOS_IOREG_SOURCE",
        ))
    except (plistlib.InvalidFileException, ValueError, TypeError) as error:
        raise SafeFailure("E_MACOS_IOREG_FORMAT") from error
    require(isinstance(plist, list) and plist and isinstance(plist[0], dict), "E_MACOS_IOREG_FORMAT")
    record = plist[0]
    machine = record.get("IOPlatformUUID")
    hardware = record.get("IOPlatformSerialNumber")
    require(isinstance(machine, str) and isinstance(hardware, str), "E_MACOS_IOREG_FIELDS")
    boot = run_local_identity_command(["sysctl", "-n", "kern.bootsessionuuid"], "E_MACOS_BOOT_ID_SOURCE")
    return {"machine": machine.encode(), "hardware": hardware.encode(), "boot": boot}


def read_physical_identity(operating_system: str) -> dict:
    if operating_system == "LINUX":
        return read_linux_identity()
    if operating_system == "MACOS":
        return read_macos_identity()
    raise SafeFailure("E_IDENTITY_OPERATING_SYSTEM")


def reserve_challenge_use(artifact_root: Path, challenge: dict, source_commit: str, now: datetime) -> tuple[Path, Path]:
    ensure_private_directory(artifact_root, create=True)
    uses = artifact_root / "challenge-uses"
    ensure_private_directory(uses, create=True)
    stem = challenge["content_sha256"]
    reservation_path = uses / f"{stem}.reserved.json"
    terminal_path = uses / f"{stem}.terminal.json"
    reservation = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_collection_challenge_use_reservation.v1",
        "status": "COLLECTION_CHALLENGE_RESERVED_SINGLE_USE",
        "domain_id": challenge["target"]["domain_id"],
        "source_commit": source_commit,
        "challenge_content_sha256": stem,
        "reserved_at": utc_text(now),
        "automatic_retry_allowed": False,
        "execution_authorized": False,
        "production_admissible": False,
    }
    write_exclusive(reservation_path, canonical(reservation) + b"\n")
    return reservation_path, terminal_path


def write_terminal(path: Path, body: dict) -> dict:
    value = dict(body)
    value["content_sha256"] = receipt_digest(value)
    write_exclusive(path, canonical(value) + b"\n")
    return value


def sign_attestation(packet_path: Path, private_key: Path, namespace: str) -> Path:
    ssh_keygen = shutil.which("ssh-keygen")
    require(ssh_keygen is not None, "E_SSH_KEYGEN_MISSING")
    signature_path = packet_path.with_suffix(packet_path.suffix + ".sig")
    require(not signature_path.exists(), "E_ATTESTATION_SIGNATURE_EXISTS")
    try:
        result = subprocess.run(
            [ssh_keygen, "-Y", "sign", "-f", str(private_key), "-n", namespace, str(packet_path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C", "LC_ALL": "C"},
            timeout=10, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise SafeFailure("E_ATTESTATION_SIGN_TIMEOUT") from error
    require(result.returncode == 0 and signature_path.is_file() and not signature_path.is_symlink(), "E_ATTESTATION_SIGN")
    signature_path.chmod(0o600)
    return signature_path


def build_attestation(challenge: dict, host: dict, identity: dict, public_key_sha256: str, now: datetime, attestation_module) -> dict:  # noqa: ANN001
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_attestation.v1",
        "packet_kind": "T22_A1_HOST_DOMAIN_ATTESTATION",
        "hashing_contract": {
            "hash_algorithm": "SHA-256",
            "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
            "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/domain-attestation/v1",
            "hash_scope": "ENTIRE_PACKET_EXCEPT_ATTESTATION_SHA256",
            "self_hash_field": "attestation_sha256",
            "self_hash_field_excluded": True,
            "detached_signature_covers_complete_canonical_packet": True,
            "cross_field_semantic_validation_required": True,
            "candidate_reported_matches_authoritative": False,
        },
        "domain_id": challenge["target"]["domain_id"],
        "attested_at": utc_text(now),
        "expires_at": challenge["collection_authority"]["expires_at"],
        "source_commit": challenge["bindings"]["source_commit"],
        "host_identity": {
            "hostname": host["hostname"],
            "logical_aliases": challenge["target"]["logical_aliases"],
            "operating_system": host["operating_system"],
            "kernel_release": host["kernel_release"],
            "architecture": host["architecture"],
            "machine_id_sha256": identity_digest("machine", identity["machine"]),
            "hardware_identity_sha256": identity_digest("hardware", identity["hardware"]),
            "boot_id_sha256": identity_digest("boot", identity["boot"]),
            "physical_host_asserted": True,
            "provider_kind": "OWNER_PHYSICAL",
            "provider_identity_sha256": None,
            "region": None,
            "zone": None,
            "instance_identity_sha256": None,
        },
        "operator_binding": {
            "operator_role": "T22_A1_DOMAIN_OPERATOR",
            "public_key_sha256": public_key_sha256,
            "signature_scheme": "OPENSSH_SSHSIG_ED25519",
            "signature_namespace": attestation_module.SIGNATURE_NAMESPACE,
            "private_key_exported": False,
        },
        "network_binding": {
            "transport": "OWNER_MANAGED_PRIVATE_OVERLAY",
            "peer_endpoint_set_sha256": challenge["network_binding"]["peer_endpoint_set_sha256"],
            "acl_policy_receipt_sha256": challenge["network_binding"]["acl_policy_receipt_sha256"],
            "public_listener_allowed": False,
            "credential_material_embedded": False,
        },
        "workload_readiness": {
            "pinned_tool_receipt_sha256": challenge["workload_binding"]["pinned_tool_receipt_sha256"],
            "private_data_root_sha256": challenge["workload_binding"]["private_data_root_sha256"],
            "port_set_sha256": challenge["workload_binding"]["port_set_sha256"],
            "tracked_tree_clean": True,
            "ambient_credentials_required": False,
        },
        "claims": {
            "candidate_for_distinct_physical_host": True,
            "site_or_power_independence_proved": False,
            "production_admissible": False,
            "attestation_is_execution_authority": False,
        },
    }
    value["attestation_sha256"] = attestation_module.domain_digest(attestation_module.ATTESTATION_DOMAIN, value)
    foreign_call(attestation_module.validate_attestation_packet, value, challenge["bindings"]["source_commit"], now)
    return value


def collect(
    challenge_path: Path,
    owner_signature_path: Path,
    domain_public_key_path: Path,
    domain_private_key_path: Path,
    source_commit: str,
    now: datetime,
    host_observer: Callable[[], dict] = observe_host,
    identity_reader: Callable[[str], dict] = read_physical_identity,
) -> dict:
    challenge_module = load_challenge_module()
    attestation_module = load_attestation_module()
    _preflight, _contract, proposal, _schema = challenge_module.load_committed_inputs()
    require(challenge_module.ANCHOR_PATH.is_file() and not challenge_module.ANCHOR_PATH.is_symlink(), "E_OWNER_ANCHOR_REQUIRED")
    anchor = json.loads(challenge_module.ANCHOR_PATH.read_text())
    authorization = foreign_call(challenge_module.verify_challenge_files,
        challenge_path, owner_signature_path, anchor, source_commit, now,
    )
    challenge, _raw = foreign_call(challenge_module.parse_canonical_challenge, challenge_path)
    require(challenge["target"]["provider_kind"] == "OWNER_PHYSICAL", "E_COLLECTOR_OWNER_PHYSICAL_ONLY")
    artifact_root = Path(challenge["artifact_scope"]["artifact_root"])
    output_directory = Path(challenge["artifact_scope"]["domain_output_directory"])
    foreign_call(challenge_module.validate_artifact_scope, challenge["artifact_scope"], challenge["target"]["domain_id"])
    require(not output_directory.exists() and not output_directory.is_symlink(), "E_DOMAIN_OUTPUT_ALREADY_EXISTS")

    require(domain_public_key_path.is_absolute() and domain_public_key_path.is_file() and not domain_public_key_path.is_symlink(), "E_DOMAIN_PUBLIC_KEY_FILE")
    canonical_public_key, public_key_sha256 = foreign_call(attestation_module.canonical_public_key, domain_public_key_path)
    require(public_key_sha256 == challenge["workload_binding"]["domain_public_key_sha256"], "E_DOMAIN_PUBLIC_KEY_BINDING")
    _reservation_path, terminal_path = reserve_challenge_use(artifact_root, challenge, source_commit, now)
    domain_private_key_accessed = False
    stable_identity_read = False
    try:
        domain_private_key_accessed = True
        verify_private_key_matches(domain_private_key_path, canonical_public_key)
        host = host_observer()
        require(host == {
            "hostname": challenge["target"]["expected_hostname"],
            "operating_system": challenge["target"]["operating_system"],
            "architecture": challenge["target"]["architecture"],
            "kernel_release": host["kernel_release"],
        }, "E_TARGET_HOST_MISMATCH")
        stable_identity_read = True
        identity = identity_reader(host["operating_system"])
        require(isinstance(identity, dict) and set(identity) == {"machine", "hardware", "boot"}, "E_IDENTITY_READER_SHAPE")
        require(all(isinstance(identity[field], bytes) for field in identity), "E_IDENTITY_READER_TYPE")
        attestation = build_attestation(challenge, host, identity, public_key_sha256, now, attestation_module)
        del identity
        ensure_private_directory(output_directory, create=True)
        packet_path = output_directory / f"{challenge['target']['domain_id']}.json"
        public_path = output_directory / f"{challenge['target']['domain_id']}.pub"
        write_exclusive(packet_path, canonical(attestation) + b"\n")
        write_exclusive(public_path, canonical_public_key)
        signature_path = sign_attestation(packet_path, domain_private_key_path, attestation_module.SIGNATURE_NAMESPACE)
        signature_binding = foreign_call(attestation_module.verify_detached_signature,
            packet_path.read_bytes(), signature_path, public_path,
            challenge["target"]["domain_id"], public_key_sha256,
        )
        body = {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.physical_domain_collection_terminal.v1",
            "status": "PASS_T22_A1_PRIVATE_PHYSICAL_DOMAIN_ATTESTATION_COLLECTION",
            "failure_code": None,
            "domain_id": challenge["target"]["domain_id"],
            "source_commit": source_commit,
            "challenge_content_sha256": challenge["content_sha256"],
            "owner_signature_sha256": authorization["owner_signature_sha256"],
            "attestation_sha256": attestation["attestation_sha256"],
            "attestation_packet_file_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            "domain_public_key_sha256": public_key_sha256,
            "domain_signature_sha256": signature_binding["signature_sha256"],
            "identity_values_hashed_in_memory": True,
            "raw_identity_values_persisted": False,
            "domain_private_key_accessed_after_authorization": True,
            "ambient_or_external_credentials_accessed": False,
            "network_accessed": False,
            "external_hosts_contacted": 0,
            "services_started": 0,
            "faults_injected": 0,
            "spend_usd_cents": 0,
            "execution_authorized": False,
            "production_admissible": False,
            "completed_at": utc_text(now),
        }
        terminal = write_terminal(terminal_path, body)
        return terminal
    except (SafeFailure, OSError) as error:
        failure_code = str(error) if isinstance(error, SafeFailure) else "E_LOCAL_IO"
        body = {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.physical_domain_collection_terminal.v1",
            "status": "FAIL_T22_A1_PRIVATE_PHYSICAL_DOMAIN_ATTESTATION_COLLECTION_NO_RETRY",
            "failure_code": failure_code,
            "domain_id": challenge["target"]["domain_id"],
            "source_commit": source_commit,
            "challenge_content_sha256": challenge["content_sha256"],
            "stable_host_identity_read": stable_identity_read,
            "raw_identity_values_persisted": False,
            "domain_private_key_accessed_after_authorization": domain_private_key_accessed,
            "ambient_or_external_credentials_accessed": False,
            "network_accessed": False,
            "external_hosts_contacted": 0,
            "services_started": 0,
            "faults_injected": 0,
            "spend_usd_cents": 0,
            "automatic_retry_allowed": False,
            "execution_authorized": False,
            "production_admissible": False,
            "completed_at": utc_text(now),
        }
        if not terminal_path.exists():
            write_terminal(terminal_path, body)
        raise SafeFailure(failure_code) from error


def status() -> dict:
    challenge_status = load_challenge_module().status()
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.physical_domain_collector_status.v0",
        "status": "BLOCKED_EXACT_OWNER_SIGNED_COLLECTION_CHALLENGE_REQUIRED" if challenge_status["owner_trust_anchor_valid"] else challenge_status["status"],
        "owner_trust_anchor_present": challenge_status["owner_trust_anchor_present"],
        "owner_trust_anchor_valid": challenge_status["owner_trust_anchor_valid"],
        "supported_provider_kind": "OWNER_PHYSICAL",
        "cloud_provider_identity_verifier_frozen": False,
        "stable_host_identity_read": False,
        "domain_private_key_accessed": False,
        "ambient_or_external_credentials_accessed": False,
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
    collect_parser = commands.add_parser("collect")
    collect_parser.add_argument("--challenge", type=Path, required=True)
    collect_parser.add_argument("--owner-signature", type=Path, required=True)
    collect_parser.add_argument("--domain-public-key", type=Path, required=True)
    collect_parser.add_argument("--domain-private-key", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "status":
        print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
        return
    challenge_module = load_challenge_module()
    source_commit = challenge_module.current_source_commit()
    terminal = collect(
        arguments.challenge.resolve(strict=True), arguments.owner_signature.resolve(strict=True),
        arguments.domain_public_key, arguments.domain_private_key,
        source_commit, datetime.now(timezone.utc),
    )
    print(json.dumps(terminal, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except SafeFailure as error:
        print(json.dumps({"status": "BLOCKED_FAIL_CLOSED", "failure_code": str(error)}, sort_keys=True, separators=(",", ":")))
        sys.exit(1)
