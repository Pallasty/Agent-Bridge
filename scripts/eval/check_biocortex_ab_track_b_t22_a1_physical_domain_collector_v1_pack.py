"""Synthetic offline KATs for the T22-A1 physical-domain collector."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_physical_domain_collector_v1.py"
spec = importlib.util.spec_from_file_location("t22a1physicalcollector", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

challenge_module = module.load_challenge_module()
_preflight, contract, proposal, _schema = challenge_module.load_committed_inputs()
module.load_challenge_module = lambda: challenge_module
NOW = datetime(2026, 7, 22, 23, 0, tzinfo=timezone.utc)
SOURCE_COMMIT = "a" * 40


def digest(label: str) -> str:
    import hashlib
    return hashlib.sha256(f"T22_A1_SYNTHETIC_PHYSICAL_COLLECTOR_ONLY:{label}".encode()).hexdigest()


def sign(path: Path, private_key: Path, namespace: str = challenge_module.SIGNATURE_NAMESPACE) -> Path:
    signature = path.with_suffix(path.suffix + ".sig")
    if signature.exists():
        signature.unlink()
    result = subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(private_key), "-n", namespace, str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    assert result.returncode == 0 and signature.is_file()
    return signature


ssh_keygen = shutil.which("ssh-keygen")
assert ssh_keygen is not None
with tempfile.TemporaryDirectory(prefix="t22-a1-physical-collector-kat-") as directory:
    private_root = Path(directory).resolve()
    owner_key = private_root / "synthetic-owner"
    wrong_owner_key = private_root / "synthetic-wrong-owner"
    domain_key = private_root / "synthetic-domain"
    wrong_domain_key = private_root / "synthetic-wrong-domain"
    for path in (owner_key, wrong_owner_key, domain_key, wrong_domain_key):
        subprocess.run(
            [ssh_keygen, "-q", "-t", "ed25519", "-N", "", "-C", "T22_A1_SYNTHETIC_ONLY", "-f", str(path)],
            check=True,
        )
    anchor = challenge_module.build_anchor(Path(str(owner_key) + ".pub"), proposal, proposal["proposal_sha256"])
    anchor_path = private_root / "owner-anchor.json"
    anchor_path.write_bytes(challenge_module.canonical(anchor) + b"\n")
    challenge_module.ANCHOR_PATH = anchor_path

    def make_challenge(label: str, expected_hostname: str = "synthetic-host") -> tuple[dict, Path, Path]:
        artifact_root = private_root / f"artifacts-{label}"
        arguments = argparse.Namespace(
            domain_id="domain-3",
            expected_hostname=expected_hostname,
            logical_alias=["synthetic-host" if expected_hostname == "synthetic-host" else expected_hostname],
            operating_system="LINUX",
            architecture="X86_64",
            provider_kind="OWNER_PHYSICAL",
            provider_identity_verifier_id=None,
            peer_endpoint_set_sha256=digest("endpoint-set"),
            acl_policy_receipt_sha256=digest("acl"),
            pinned_tool_receipt_sha256=digest("tools"),
            private_data_root_sha256=digest(f"data-root:{label}"),
            port_set_sha256=digest(f"ports:{label}"),
            domain_public_key=Path(str(domain_key) + ".pub"),
            artifact_root=artifact_root,
            maximum_lifetime_seconds=3600,
        )
        value = challenge_module.build_challenge(anchor, contract, proposal, arguments, SOURCE_COMMIT, NOW)
        path = private_root / f"challenge-{label}.json"
        path.write_bytes(challenge_module.canonical(value) + b"\n")
        return value, path, sign(path, owner_key)

    host = {
        "hostname": "synthetic-host",
        "operating_system": "LINUX",
        "architecture": "X86_64",
        "kernel_release": "synthetic-kernel",
    }
    identity_calls: list[str] = []

    def synthetic_identity_reader(operating_system: str) -> dict:
        identity_calls.append(operating_system)
        return {
            "machine": b"synthetic-machine-id",
            "hardware": b"synthetic-hardware-id",
            "boot": b"synthetic-boot-id",
        }

    valid_challenge, valid_path, valid_signature = make_challenge("valid")
    terminal = module.collect(
        valid_path, valid_signature, Path(str(domain_key) + ".pub"), domain_key,
        SOURCE_COMMIT, NOW + timedelta(seconds=1),
        host_observer=lambda: dict(host), identity_reader=synthetic_identity_reader,
    )
    assert terminal["status"] == "PASS_T22_A1_PRIVATE_PHYSICAL_DOMAIN_ATTESTATION_COLLECTION"
    assert terminal["identity_values_hashed_in_memory"] is True
    assert terminal["raw_identity_values_persisted"] is False
    assert terminal["domain_private_key_accessed_after_authorization"] is True
    assert terminal["ambient_or_external_credentials_accessed"] is False
    assert terminal["network_accessed"] is False
    assert terminal["external_hosts_contacted"] == terminal["services_started"] == terminal["faults_injected"] == 0
    assert terminal["execution_authorized"] is False and terminal["production_admissible"] is False
    unsigned_terminal = dict(terminal)
    claimed_terminal_sha256 = unsigned_terminal.pop("content_sha256")
    assert claimed_terminal_sha256 == module.receipt_digest(unsigned_terminal)
    assert identity_calls == ["LINUX"]
    output = Path(valid_challenge["artifact_scope"]["domain_output_directory"])
    assert {path.name for path in output.iterdir()} == {"domain-3.json", "domain-3.json.sig", "domain-3.pub"}
    assert all(path.stat().st_mode & 0o077 == 0 for path in output.iterdir())
    private_artifacts = list(Path(valid_challenge["artifact_scope"]["artifact_root"]).rglob("*"))
    for artifact in private_artifacts:
        if artifact.is_file():
            raw_artifact = artifact.read_bytes()
            assert b"synthetic-machine-id" not in raw_artifact
            assert b"synthetic-hardware-id" not in raw_artifact
            assert b"synthetic-boot-id" not in raw_artifact
    attestation_module = module.load_attestation_module()
    packet, raw = attestation_module.parse_canonical_packet(output / "domain-3.json")
    attestation_module.validate_attestation_packet(packet, SOURCE_COMMIT, NOW + timedelta(seconds=1))
    attestation_module.verify_detached_signature(
        raw, output / "domain-3.json.sig", output / "domain-3.pub", "domain-3",
        packet["operator_binding"]["public_key_sha256"],
    )

    initial_identity_count = len(identity_calls)
    wrong_owner_copy = private_root / "challenge-wrong-owner.json"
    wrong_owner_copy.write_bytes(valid_path.read_bytes())
    wrong_owner_signature = sign(wrong_owner_copy, wrong_owner_key)
    try:
        module.collect(
            valid_path, wrong_owner_signature, Path(str(domain_key) + ".pub"), domain_key,
            SOURCE_COMMIT, NOW + timedelta(seconds=2),
            host_observer=lambda: dict(host), identity_reader=synthetic_identity_reader,
        )
    except module.SafeFailure as error:
        assert str(error) == "E_OWNER_SIGNATURE_INVALID"
    else:
        raise AssertionError("wrong owner signature admitted by collector")
    assert len(identity_calls) == initial_identity_count

    key_challenge, key_path, key_signature = make_challenge("wrong-key")
    try:
        module.collect(
            key_path, key_signature, Path(str(domain_key) + ".pub"), wrong_domain_key,
            SOURCE_COMMIT, NOW + timedelta(seconds=1),
            host_observer=lambda: dict(host), identity_reader=synthetic_identity_reader,
        )
    except module.SafeFailure as error:
        assert str(error) == "E_DOMAIN_PRIVATE_KEY_MISMATCH"
    else:
        raise AssertionError("wrong domain private key admitted")
    assert len(identity_calls) == initial_identity_count
    wrong_key_terminal = Path(key_challenge["artifact_scope"]["artifact_root"]) / "challenge-uses" / f"{key_challenge['content_sha256']}.terminal.json"
    wrong_key_receipt = json.loads(wrong_key_terminal.read_text())
    assert wrong_key_receipt["stable_host_identity_read"] is False
    assert wrong_key_receipt["domain_private_key_accessed_after_authorization"] is True
    assert wrong_key_receipt["automatic_retry_allowed"] is False

    host_challenge, host_path, host_signature = make_challenge("wrong-host")
    try:
        module.collect(
            host_path, host_signature, Path(str(domain_key) + ".pub"), domain_key,
            SOURCE_COMMIT, NOW + timedelta(seconds=1),
            host_observer=lambda: {**host, "hostname": "different-host"},
            identity_reader=synthetic_identity_reader,
        )
    except module.SafeFailure as error:
        assert str(error) == "E_TARGET_HOST_MISMATCH"
    else:
        raise AssertionError("wrong target host admitted")
    assert len(identity_calls) == initial_identity_count
    host_terminal = Path(host_challenge["artifact_scope"]["artifact_root"]) / "challenge-uses" / f"{host_challenge['content_sha256']}.terminal.json"
    assert json.loads(host_terminal.read_text())["stable_host_identity_read"] is False

    replay_root = Path(valid_challenge["artifact_scope"]["artifact_root"])
    try:
        module.reserve_challenge_use(replay_root, valid_challenge, SOURCE_COMMIT, NOW + timedelta(seconds=2))
    except module.SafeFailure as error:
        assert str(error) == "E_PRIVATE_OUTPUT_EXISTS"
    else:
        raise AssertionError("collection challenge replay reservation admitted")
    assert len(identity_calls) == initial_identity_count

    read_challenge, read_path, read_signature = make_challenge("read-failure")

    def failing_identity_reader(operating_system: str) -> dict:
        identity_calls.append(operating_system)
        raise module.SafeFailure("E_SYNTHETIC_IDENTITY_READ")

    try:
        module.collect(
            read_path, read_signature, Path(str(domain_key) + ".pub"), domain_key,
            SOURCE_COMMIT, NOW + timedelta(seconds=1),
            host_observer=lambda: dict(host), identity_reader=failing_identity_reader,
        )
    except module.SafeFailure as error:
        assert str(error) == "E_SYNTHETIC_IDENTITY_READ"
    else:
        raise AssertionError("synthetic identity read failure admitted")
    read_terminal = Path(read_challenge["artifact_scope"]["artifact_root"]) / "challenge-uses" / f"{read_challenge['content_sha256']}.terminal.json"
    read_failure_receipt = json.loads(read_terminal.read_text())
    assert read_failure_receipt["stable_host_identity_read"] is True
    assert read_failure_receipt["raw_identity_values_persisted"] is False
    assert read_failure_receipt["automatic_retry_allowed"] is False

    expired_challenge, expired_path, expired_signature = make_challenge("expired")
    try:
        module.collect(
            expired_path, expired_signature, Path(str(domain_key) + ".pub"), domain_key,
            SOURCE_COMMIT, NOW + timedelta(hours=2),
            host_observer=lambda: dict(host), identity_reader=synthetic_identity_reader,
        )
    except module.SafeFailure as error:
        assert str(error) == "E_CHALLENGE_NOT_CURRENT"
    else:
        raise AssertionError("expired collection challenge admitted")
    assert len(identity_calls) == initial_identity_count + 1

    source_challenge, source_path, source_signature = make_challenge("wrong-source")
    try:
        module.collect(
            source_path, source_signature, Path(str(domain_key) + ".pub"), domain_key,
            "b" * 40, NOW + timedelta(seconds=1),
            host_observer=lambda: dict(host), identity_reader=synthetic_identity_reader,
        )
    except module.SafeFailure as error:
        assert str(error) == "E_CHALLENGE_BINDINGS"
    else:
        raise AssertionError("wrong source commit admitted")
    assert len(identity_calls) == initial_identity_count + 1

    public_challenge, public_path, public_signature = make_challenge("wrong-public-key")
    try:
        module.collect(
            public_path, public_signature, Path(str(wrong_domain_key) + ".pub"), wrong_domain_key,
            SOURCE_COMMIT, NOW + timedelta(seconds=1),
            host_observer=lambda: dict(host), identity_reader=synthetic_identity_reader,
        )
    except module.SafeFailure as error:
        assert str(error) == "E_DOMAIN_PUBLIC_KEY_BINDING"
    else:
        raise AssertionError("wrong domain public key admitted")
    assert len(identity_calls) == initial_identity_count + 1

    output_challenge, output_path, output_signature = make_challenge("preexisting-output")
    preexisting_output = Path(output_challenge["artifact_scope"]["domain_output_directory"])
    preexisting_output.mkdir(mode=0o700, parents=True)
    preexisting_output.chmod(0o700)
    try:
        module.collect(
            output_path, output_signature, Path(str(domain_key) + ".pub"), domain_key,
            SOURCE_COMMIT, NOW + timedelta(seconds=1),
            host_observer=lambda: dict(host), identity_reader=synthetic_identity_reader,
        )
    except module.SafeFailure as error:
        assert str(error) == "E_DOMAIN_OUTPUT_ALREADY_EXISTS"
    else:
        raise AssertionError("preexisting domain output admitted")
    assert len(identity_calls) == initial_identity_count + 1

    permissions_challenge, permissions_path, permissions_signature = make_challenge("key-permissions")
    insecure_private_key = private_root / "insecure-domain-private-key"
    shutil.copyfile(domain_key, insecure_private_key)
    insecure_private_key.chmod(0o644)
    try:
        module.collect(
            permissions_path, permissions_signature, Path(str(domain_key) + ".pub"), insecure_private_key,
            SOURCE_COMMIT, NOW + timedelta(seconds=1),
            host_observer=lambda: dict(host), identity_reader=synthetic_identity_reader,
        )
    except module.SafeFailure as error:
        assert str(error) == "E_DOMAIN_PRIVATE_KEY_PERMISSIONS"
    else:
        raise AssertionError("insecure domain private-key permissions admitted")
    assert len(identity_calls) == initial_identity_count + 1

    ready_status = module.status()
    assert ready_status["status"] == "BLOCKED_EXACT_OWNER_SIGNED_COLLECTION_CHALLENGE_REQUIRED"
    assert ready_status["owner_trust_anchor_present"] is True and ready_status["owner_trust_anchor_valid"] is True
    assert ready_status["stable_host_identity_read"] is False
    assert ready_status["domain_private_key_accessed"] is False

status = module.status()
assert status["status"] == "BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_REQUIRED"
assert status["owner_trust_anchor_present"] is False and status["owner_trust_anchor_valid"] is False
assert status["stable_host_identity_read"] is False
assert status["domain_private_key_accessed"] is False
assert status["ambient_or_external_credentials_accessed"] is False
assert status["network_accessed"] is False
assert status["external_hosts_contacted"] == status["services_started"] == status["faults_injected"] == 0
assert status["attestation_items_created"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

print("t22_a1_physical_domain_collector_check\tpass")
print("directed_negative_test_count\t10")
print("real_host_identifiers_read\tfalse")
print("synthetic_identity_read_count\t2")
print("network_accessed\tfalse")
print("ambient_or_external_credentials_accessed\tfalse")
print("external_hosts_contacted\t0")
print("services_started\t0")
print("faults_injected\t0")
print("real_attestation_items_created\t0")
