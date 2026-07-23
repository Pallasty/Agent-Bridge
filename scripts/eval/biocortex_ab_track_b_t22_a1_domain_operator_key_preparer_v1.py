"""Explicit, zero-network T22-A1 domain-operator key preparation.

This tool creates one new Ed25519 key beneath an exact private host-local root.
It never discovers credentials, connects to another host, reads stable machine
identity, or grants collection/execution authority.  The exact ssh-keygen
binary hash and expected hostname are caller-bound, and an attempt is reserved
once so a partial or ambiguous identity is never silently reused.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import socket
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
CHALLENGE_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_collection_challenge_v1.py"
RECEIPT_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-operator-key-preparation/v1\0"
DOMAIN_IDS = ("domain-1", "domain-2", "domain-3")
OID40_LENGTH = 40
MAX_KEY_BYTES = 64 * 1024


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def load_challenge_module():
    spec = importlib.util.spec_from_file_location("t22a1_challenge_for_domain_key_preparer", CHALLENGE_SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: object) -> str:
    return hashlib.sha256(RECEIPT_DOMAIN + canonical(value)).hexdigest()


def utc_text(value: datetime) -> str:
    require(value.tzinfo is not None and value.utcoffset().total_seconds() == 0, "E_DOMAIN_KEY_TIMEZONE")
    return value.isoformat().replace("+00:00", "Z")


def is_sha256(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and value != "0" * 64
        and all(character in "0123456789abcdef" for character in value)
    )


def path_outside_repository(path: Path) -> bool:
    require(path.is_absolute(), "E_DOMAIN_KEY_PRIVATE_ROOT")
    resolved = path.resolve(strict=False)
    repository = ROOT.resolve()
    return repository not in (resolved, *resolved.parents) and resolved not in repository.parents


def ensure_private_directory(path: Path, create: bool) -> None:
    require(path.is_absolute() and not path.is_symlink(), "E_DOMAIN_KEY_PRIVATE_DIRECTORY")
    if create and not path.exists():
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
        path.chmod(0o700)
    require(
        path.is_dir() and not path.is_symlink()
        and path.stat().st_uid == os.geteuid()
        and stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
        "E_DOMAIN_KEY_PRIVATE_DIRECTORY",
    )


def write_exclusive(path: Path, value: dict) -> None:
    require(path.is_absolute() and not path.exists() and not path.is_symlink(), "E_DOMAIN_KEY_OUTPUT_EXISTS")
    ensure_private_directory(path.parent, create=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def validate_ssh_keygen(path: Path, expected_sha256: str) -> str:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "E_DOMAIN_KEY_SSH_KEYGEN_FILE")
    metadata = path.stat()
    require(
        stat.S_ISREG(metadata.st_mode) and metadata.st_uid in {0, os.geteuid()}
        and metadata.st_mode & 0o022 == 0 and os.access(path, os.X_OK)
        and is_sha256(expected_sha256),
        "E_DOMAIN_KEY_SSH_KEYGEN_FILE",
    )
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    require(observed == expected_sha256, "E_DOMAIN_KEY_SSH_KEYGEN_BINDING")
    return observed


def validate_generated_key(
    private_key: Path,
    public_key: Path,
    ssh_keygen: Path,
    command_runner: Callable[..., subprocess.CompletedProcess],
) -> tuple[str, str]:
    for path, private in ((private_key, True), (public_key, False)):
        require(path.is_file() and not path.is_symlink(), "E_DOMAIN_KEY_GENERATED_FILE")
        metadata = path.stat()
        require(
            stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.geteuid()
            and 0 < metadata.st_size <= MAX_KEY_BYTES
            and (not private or metadata.st_mode & 0o077 == 0),
            "E_DOMAIN_KEY_GENERATED_FILE",
        )
    challenge = load_challenge_module()
    canonical_public, public_sha256, fingerprint = challenge.public_key_identity(public_key.read_bytes())
    try:
        derived = command_runner(
            [str(ssh_keygen), "-y", "-f", str(private_key)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={"LANG": "C", "LC_ALL": "C"}, shell=False,
            close_fds=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SafeFailure("E_DOMAIN_KEY_PAIR_VERIFICATION") from error
    require(derived.returncode == 0 and 0 < len(derived.stdout) <= MAX_KEY_BYTES, "E_DOMAIN_KEY_PAIR_VERIFICATION")
    derived_public = challenge.canonical_public_key_bytes(derived.stdout)
    require(derived_public == canonical_public, "E_DOMAIN_KEY_PAIR_MISMATCH")
    return public_sha256, fingerprint


def prepare(
    domain_id: str,
    expected_hostname: str,
    private_root: Path,
    ssh_keygen: Path,
    expected_ssh_keygen_sha256: str,
    source_commit: str,
    now: datetime,
    hostname_observer: Callable[[], str] = socket.gethostname,
    command_runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict:
    require(domain_id in DOMAIN_IDS, "E_DOMAIN_KEY_DOMAIN")
    require(
        isinstance(expected_hostname, str) and 1 <= len(expected_hostname) <= 255,
        "E_DOMAIN_KEY_HOSTNAME",
    )
    require(
        isinstance(source_commit, str) and len(source_commit) == OID40_LENGTH
        and all(character in "0123456789abcdef" for character in source_commit),
        "E_DOMAIN_KEY_SOURCE_COMMIT",
    )
    utc_text(now)
    require(path_outside_repository(private_root), "E_DOMAIN_KEY_PRIVATE_ROOT")
    observed_tool_sha256 = validate_ssh_keygen(ssh_keygen, expected_ssh_keygen_sha256)
    observed_hostname = hostname_observer()
    require(observed_hostname == expected_hostname, "E_DOMAIN_KEY_HOST_BINDING")
    ensure_private_directory(private_root, create=True)
    keys = private_root / "keys"
    receipts = private_root / "key-preparation"
    ensure_private_directory(keys, create=True)
    ensure_private_directory(receipts, create=True)
    private_key = keys / f"{domain_id}-operator"
    public_key = keys / f"{domain_id}-operator.pub"
    reservation = receipts / f"{domain_id}.reserved.json"
    terminal_path = receipts / f"{domain_id}.terminal.json"
    write_exclusive(reservation, {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_operator_key_preparation_reservation.v1",
        "status": "EXACT_DOMAIN_OPERATOR_KEY_PREPARATION_RESERVED_SINGLE_ATTEMPT",
        "domain_id": domain_id, "expected_hostname": expected_hostname,
        "source_commit": source_commit, "ssh_keygen_sha256": observed_tool_sha256,
        "reserved_at": utc_text(now), "automatic_retry_allowed": False,
        "execution_authorized": False, "production_admissible": False,
    })
    require(
        not private_key.exists() and not private_key.is_symlink()
        and not public_key.exists() and not public_key.is_symlink(),
        "E_DOMAIN_KEY_OUTPUT_EXISTS",
    )
    try:
        try:
            result = command_runner(
                [str(ssh_keygen), "-q", "-t", "ed25519", "-N", "",
                 "-C", f"T22_A1_{domain_id.upper().replace('-', '_')}_{expected_hostname}",
                 "-f", str(private_key)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env={"LANG": "C", "LC_ALL": "C"}, shell=False,
                close_fds=True, timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SafeFailure("E_DOMAIN_KEY_GENERATION") from error
        require(result.returncode == 0, "E_DOMAIN_KEY_GENERATION")
        private_key.chmod(0o600)
        public_key.chmod(0o600)
        public_sha256, fingerprint = validate_generated_key(
            private_key, public_key, ssh_keygen, command_runner,
        )
        value = {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_operator_key_preparation_terminal.v1",
            "status": "PASS_T22_A1_DEDICATED_DOMAIN_OPERATOR_KEY_PREPARED",
            "failure_code": None, "domain_id": domain_id,
            "expected_hostname": expected_hostname, "source_commit": source_commit,
            "ssh_keygen_path": str(ssh_keygen), "ssh_keygen_sha256": observed_tool_sha256,
            "private_key_path": str(private_key), "public_key_path": str(public_key),
            "private_key_file_mode": "0600", "public_key_file_mode": "0600",
            "public_key_sha256": public_sha256, "public_key_fingerprint": fingerprint,
            "key_pair_verified": True, "private_key_exported": False,
            "stable_host_identity_read": False,
            "ambient_or_existing_credentials_accessed": False,
            "network_accessed": False, "external_hosts_contacted": 0,
            "services_started": 0, "faults_injected": 0, "spend_usd_cents": 0,
            "automatic_retry_allowed": False, "execution_authorized": False,
            "production_admissible": False, "completed_at": utc_text(now),
        }
        value["content_sha256"] = digest(value)
        write_exclusive(terminal_path, value)
        return value
    except Exception as error:
        for path in (public_key, private_key):
            if path.is_file() and not path.is_symlink():
                path.unlink()
        failure_code = str(error) if isinstance(error, RuntimeError) and str(error).startswith("E_") else "E_DOMAIN_KEY_LOCAL_FAILURE"
        if not terminal_path.exists():
            failure = {
                "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_operator_key_preparation_terminal.v1",
                "status": "FAIL_T22_A1_DOMAIN_OPERATOR_KEY_PREPARATION_NO_RETRY",
                "failure_code": failure_code, "domain_id": domain_id,
                "expected_hostname": expected_hostname, "source_commit": source_commit,
                "partial_key_material_removed": True, "automatic_retry_allowed": False,
                "network_accessed": False, "external_hosts_contacted": 0,
                "services_started": 0, "faults_injected": 0, "spend_usd_cents": 0,
                "execution_authorized": False, "production_admissible": False,
                "completed_at": utc_text(now),
            }
            failure["content_sha256"] = digest(failure)
            write_exclusive(terminal_path, failure)
        raise SafeFailure(failure_code) from error


def current_source_commit() -> str:
    for arguments in (("git", "diff", "--quiet"), ("git", "diff", "--cached", "--quiet")):
        result = subprocess.run(arguments, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        require(result.returncode == 0, "E_DOMAIN_KEY_TRACKED_TREE_DIRTY")
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    value = result.stdout.strip()
    require(result.returncode == 0, "E_DOMAIN_KEY_SOURCE_COMMIT")
    return value


def status() -> dict:
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_operator_key_preparer_status.v0",
        "status": "READY_EXPLICIT_ZERO_NETWORK_DEDICATED_DOMAIN_KEY_PREPARATION",
        "supported_domain_ids": list(DOMAIN_IDS), "automatic_retry_allowed": False,
        "real_key_items_created": 0, "stable_host_identity_read": False,
        "ambient_or_existing_credentials_accessed": False,
        "network_accessed": False, "external_hosts_contacted": 0,
        "services_started": 0, "faults_injected": 0, "spend_usd_cents": 0,
        "execution_authorized": False, "production_admissible": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--domain-id", choices=DOMAIN_IDS, required=True)
    prepare_parser.add_argument("--expected-hostname", required=True)
    prepare_parser.add_argument("--private-root", type=Path, required=True)
    prepare_parser.add_argument("--ssh-keygen", type=Path, required=True)
    prepare_parser.add_argument("--confirm-ssh-keygen-sha256", required=True)
    arguments = parser.parse_args()
    if arguments.command == "status":
        print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
        return
    result = prepare(
        arguments.domain_id, arguments.expected_hostname, arguments.private_root,
        arguments.ssh_keygen, arguments.confirm_ssh_keygen_sha256,
        current_source_commit(), datetime.now(timezone.utc),
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except SafeFailure as error:
        print(json.dumps({"status": "BLOCKED_FAIL_CLOSED", "failure_code": str(error)}, sort_keys=True, separators=(",", ":")))
        sys.exit(1)
