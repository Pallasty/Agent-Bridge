"""Synthetic offline KATs for the T22-A1 runtime material preparer."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_runtime_material_preparer_v1.py"
spec = importlib.util.spec_from_file_location("t22a1runtimepreparer", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

authorization_module = module.load_authorization_module()
collection, runtime, contract, proposal, _schema = authorization_module.load_inputs()
authorization_module.load_inputs = lambda: (collection, runtime, contract, proposal, _schema)
module.load_authorization_module = lambda: authorization_module
NOW = datetime.now(timezone.utc).replace(microsecond=0)
SOURCE_COMMIT = "a" * 40
RUN_ID = f"t22-a1-{NOW.strftime('%Y%m%dT%H%M%S')}.000000z-123456789abc"


def digest(label: str) -> str:
    return hashlib.sha256(f"T22_A1_SYNTHETIC_RUNTIME_MATERIAL_ONLY:{label}".encode()).hexdigest()


def sign(path: Path, private_key: Path, namespace: str = authorization_module.SIGNATURE_NAMESPACE) -> Path:
    signature = path.with_suffix(path.suffix + ".sig")
    if signature.exists():
        signature.unlink()
    result = subprocess.run(
        [str(SSH_KEYGEN), "-Y", "sign", "-f", str(private_key), "-n", namespace, str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    assert result.returncode == 0 and signature.is_file()
    return signature


def endpoint_manifest(run_id: str, source_commit: str, label: str) -> dict:
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.private_endpoint_manifest.v1",
        "packet_kind": "T22_A1_PRIVATE_ENDPOINT_MANIFEST",
        "hashing_contract": {
            "hash_algorithm": "SHA-256",
            "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
            "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/private-endpoint-manifest/v1",
            "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256",
            "self_hash_field": "content_sha256",
            "self_hash_field_excluded": True,
            "cross_field_semantic_validation_required": True,
        },
        "run_id": run_id,
        "source_commit": source_commit,
        "transport": "OWNER_MANAGED_PRIVATE_OVERLAY",
        "acl_policy_receipt_sha256": digest(f"acl:{label}"),
        "domains": [
            {
                "domain_id": f"domain-{number}",
                "hostname": f"synthetic-host-{number}",
                "overlay_ip": f"100.64.10.{number}",
                "agent_control_port": 29000,
                "etcd_client_port": 2379,
                "etcd_peer_port": 2380,
                "openbao_api_port": 8200,
                "openbao_cluster_port": 8201,
                "bind_exact_overlay_ip_only": True,
                "public_listener_allowed": False,
            }
            for number in (1, 2, 3)
        ],
        "raw_manifest_repository_allowed": False,
        "public_address_allowed": False,
        "dns_resolution_required": False,
    }
    value["content_sha256"] = runtime.digest(runtime.ENDPOINT_DOMAIN, value)
    endpoint_schema, _credential_schema, _message_schema = runtime.load_schemas()
    runtime.validate_endpoint_manifest(value, endpoint_schema, source_commit, run_id)
    return value


def create_private_root(base: Path, label: str, endpoint: dict) -> tuple[Path, Path]:
    root = base / f"artifacts-{label}"
    manifests = root / "manifests"
    manifests.mkdir(mode=0o700, parents=True)
    root.chmod(0o700)
    manifests.chmod(0o700)
    path = manifests / "private-endpoints.json"
    path.write_bytes(module.canonical(endpoint) + b"\n")
    path.chmod(0o600)
    return root, path


def create_challenge(
    base: Path,
    owner_key: Path,
    anchor: dict,
    label: str,
    endpoint: dict,
    root: Path,
    endpoint_binding: str | None = None,
    openssl_sha256: str | None = None,
    issued_at: datetime = NOW,
) -> tuple[dict, Path, Path]:
    challenge = authorization_module.build_challenge(
        anchor, contract, proposal, SOURCE_COMMIT, endpoint["run_id"],
        digest(f"attestation-set:{label}"), endpoint_binding or endpoint["content_sha256"], root,
        OPENSSL, openssl_sha256 or OPENSSL_SHA256,
        SSH_KEYGEN, SSH_KEYGEN_SHA256,
        issued_at, issued_at + timedelta(hours=4), 3600, 3600,
    )
    path = base / f"runtime-preparation-{label}.json"
    path.write_bytes(authorization_module.canonical(challenge) + b"\n")
    return challenge, path, sign(path, owner_key)


OPENSSL = Path(shutil.which("openssl") or "").resolve(strict=True)
SSH_KEYGEN = Path(shutil.which("ssh-keygen") or "").resolve(strict=True)
OPENSSL_SHA256 = hashlib.sha256(OPENSSL.read_bytes()).hexdigest()
SSH_KEYGEN_SHA256 = hashlib.sha256(SSH_KEYGEN.read_bytes()).hexdigest()

with tempfile.TemporaryDirectory(prefix="t22-a1-runtime-material-kat-") as directory:
    private_root = Path(directory).resolve()
    owner_key = private_root / "synthetic-owner"
    wrong_owner_key = private_root / "synthetic-wrong-owner"
    for key in (owner_key, wrong_owner_key):
        subprocess.run(
            [str(SSH_KEYGEN), "-q", "-t", "ed25519", "-N", "", "-C", "T22_A1_SYNTHETIC_ONLY", "-f", str(key)],
            check=True,
        )
    anchor = collection.build_anchor(Path(str(owner_key) + ".pub"), proposal, proposal["proposal_sha256"])
    anchor_path = private_root / "owner-anchor.json"
    anchor_path.write_bytes(collection.canonical(anchor) + b"\n")
    anchor_path.chmod(0o600)
    collection.ANCHOR_PATH = anchor_path

    endpoint = endpoint_manifest(RUN_ID, SOURCE_COMMIT, "valid")
    artifact_root, endpoint_path = create_private_root(private_root, "valid", endpoint)
    challenge, challenge_path, signature_path = create_challenge(
        private_root, owner_key, anchor, "valid", endpoint, artifact_root,
    )
    terminal = module.prepare(
        challenge_path, signature_path, SOURCE_COMMIT, NOW + timedelta(seconds=1),
    )
    assert terminal["status"] == "PASS_T22_A1_ZERO_NETWORK_PRIVATE_RUNTIME_MATERIAL_PREPARATION"
    assert terminal["certificate_count"] == terminal["retained_private_key_count"] == 5
    assert terminal["private_ca_signing_key_retained"] is False
    assert terminal["certificate_chain_key_eku_expiry_and_endpoint_bindings_verified"] is True
    assert terminal["private_endpoint_manifest_instance_read"] is True
    assert terminal["raw_endpoint_values_in_receipt"] is False
    assert terminal["private_key_material_in_manifest_or_receipt"] is False
    assert terminal["ambient_or_preexisting_credentials_accessed"] is False
    assert terminal["network_accessed"] is False
    assert terminal["external_hosts_contacted"] == terminal["listeners_started"] == 0
    assert terminal["services_started"] == terminal["faults_injected"] == terminal["spend_usd_cents"] == 0
    assert terminal["automatic_retry_allowed"] is False
    assert terminal["execution_authorized"] is False and terminal["production_admissible"] is False
    unsigned_terminal = dict(terminal)
    claimed_terminal_sha256 = unsigned_terminal.pop("content_sha256")
    assert claimed_terminal_sha256 == module.terminal_digest(unsigned_terminal)

    credentials_directory = artifact_root / "credentials"
    assert {path.name for path in credentials_directory.iterdir()} == module.EXPECTED_MATERIAL_NAMES
    assert not (credentials_directory / "ca.key").exists()
    assert all(path.stat().st_mode & 0o077 == 0 for path in credentials_directory.iterdir())
    manifest_path = artifact_root / "manifests" / "runtime-credentials.json"
    assert manifest_path.stat().st_mode & 0o077 == 0
    manifest = json.loads(manifest_path.read_text())
    _endpoint_schema, credential_schema, _message_schema = runtime.load_schemas()
    runtime.validate_credential_manifest(
        manifest, credential_schema, SOURCE_COMMIT, RUN_ID, endpoint["content_sha256"], NOW + timedelta(hours=4),
    )
    assert manifest["content_sha256"] == terminal["runtime_credential_manifest_content_sha256"]
    runtime_public = (credentials_directory / "coordinator-runtime.pub").read_bytes()
    assert hashlib.sha256(runtime_public).hexdigest() == terminal["coordinator_runtime_public_key_sha256"]
    terminal_raw = module.canonical(terminal)
    assert all(domain["overlay_ip"].encode() not in terminal_raw for domain in endpoint["domains"])
    assert str(artifact_root).encode() not in terminal_raw

    try:
        module.reserve_challenge_use(artifact_root, challenge, SOURCE_COMMIT, NOW + timedelta(seconds=2))
    except module.SafeFailure as error:
        assert str(error) == "E_RUNTIME_PREPARATION_OUTPUT_EXISTS"
    else:
        raise AssertionError("runtime preparation replay reservation admitted")

    wrong_owner_endpoint = endpoint_manifest(RUN_ID, SOURCE_COMMIT, "wrong-owner")
    wrong_owner_root, wrong_owner_endpoint_path = create_private_root(private_root, "wrong-owner", wrong_owner_endpoint)
    _wrong_owner_challenge, wrong_owner_challenge_path, _ = create_challenge(
        private_root, owner_key, anchor, "wrong-owner", wrong_owner_endpoint, wrong_owner_root,
    )
    wrong_owner_signature = sign(wrong_owner_challenge_path, wrong_owner_key)
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path.resolve(strict=False) == wrong_owner_endpoint_path.resolve(strict=False):
            raise AssertionError("endpoint read before owner signature verification")
        return original_read_bytes(path)

    Path.read_bytes = guarded_read_bytes
    try:
        try:
            module.prepare(
                wrong_owner_challenge_path, wrong_owner_signature,
                SOURCE_COMMIT, NOW + timedelta(seconds=1),
            )
        except module.SafeFailure as error:
            assert str(error) == "E_PREPARATION_OWNER_SIGNATURE_INVALID"
        else:
            raise AssertionError("wrong owner signature admitted")
    finally:
        Path.read_bytes = original_read_bytes

    expired_endpoint = endpoint_manifest(RUN_ID, SOURCE_COMMIT, "expired")
    expired_root, expired_endpoint_path = create_private_root(private_root, "expired", expired_endpoint)
    _expired_challenge, expired_challenge_path, expired_signature = create_challenge(
        private_root, owner_key, anchor, "expired", expired_endpoint, expired_root,
    )
    Path.read_bytes = lambda path: (_ for _ in ()).throw(AssertionError("endpoint read after expired authority")) \
        if path.resolve(strict=False) == expired_endpoint_path.resolve(strict=False) else original_read_bytes(path)
    try:
        try:
            module.prepare(expired_challenge_path, expired_signature, SOURCE_COMMIT, NOW + timedelta(hours=2))
        except module.SafeFailure as error:
            assert str(error) == "E_PREPARATION_NOT_CURRENT"
        else:
            raise AssertionError("expired runtime preparation authority admitted")
    finally:
        Path.read_bytes = original_read_bytes

    tool_endpoint = endpoint_manifest(RUN_ID, SOURCE_COMMIT, "tool")
    tool_root, _tool_endpoint_path = create_private_root(private_root, "tool", tool_endpoint)
    tool_challenge, tool_challenge_path, tool_signature = create_challenge(
        private_root, owner_key, anchor, "tool", tool_endpoint, tool_root,
        openssl_sha256=digest("wrong-openssl"),
    )
    try:
        module.prepare(tool_challenge_path, tool_signature, SOURCE_COMMIT, NOW + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_OPENSSL_TOOL_BINDING"
    else:
        raise AssertionError("wrong signed OpenSSL digest admitted")
    tool_terminal = json.loads((tool_root / "runtime-preparation-uses" / f"{tool_challenge['content_sha256']}.terminal.json").read_text())
    assert tool_terminal["private_endpoint_manifest_instance_read"] is False
    assert tool_terminal["runtime_material_generation_started"] is False
    assert tool_terminal["automatic_retry_allowed"] is False

    binding_endpoint = endpoint_manifest(RUN_ID, SOURCE_COMMIT, "binding")
    binding_root, _binding_endpoint_path = create_private_root(private_root, "binding", binding_endpoint)
    binding_challenge, binding_challenge_path, binding_signature = create_challenge(
        private_root, owner_key, anchor, "binding", binding_endpoint, binding_root,
        endpoint_binding=digest("wrong-endpoint"),
    )
    try:
        module.prepare(binding_challenge_path, binding_signature, SOURCE_COMMIT, NOW + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_ENDPOINT_MANIFEST_OWNER_BINDING"
    else:
        raise AssertionError("wrong endpoint content binding admitted")
    binding_terminal = json.loads((binding_root / "runtime-preparation-uses" / f"{binding_challenge['content_sha256']}.terminal.json").read_text())
    assert binding_terminal["private_endpoint_manifest_instance_read"] is True
    assert binding_terminal["runtime_material_generation_started"] is False

    failure_endpoint = endpoint_manifest(RUN_ID, SOURCE_COMMIT, "generator-failure")
    failure_root, _failure_endpoint_path = create_private_root(private_root, "generator-failure", failure_endpoint)
    failure_challenge, failure_challenge_path, failure_signature = create_challenge(
        private_root, owner_key, anchor, "generator-failure", failure_endpoint, failure_root,
    )

    def failing_generator(staging: Path, *_args) -> dict:  # noqa: ANN002
        module.ensure_private_directory(staging, create=True)
        module.write_exclusive(staging / "partial-secret.key", b"SYNTHETIC_PARTIAL_SECRET\n")
        raise module.SafeFailure("E_SYNTHETIC_MATERIAL_GENERATION")

    try:
        module.prepare(
            failure_challenge_path, failure_signature, SOURCE_COMMIT,
            NOW + timedelta(seconds=1), material_generator=failing_generator,
        )
    except module.SafeFailure as error:
        assert str(error) == "E_SYNTHETIC_MATERIAL_GENERATION"
    else:
        raise AssertionError("injected material generation failure admitted")
    assert not (failure_root / f".runtime-preparation-{failure_challenge['content_sha256']}.staging").exists()
    assert not (failure_root / "credentials").exists()
    assert not (failure_root / "manifests" / "runtime-credentials.json").exists()
    failure_terminal = json.loads((failure_root / "runtime-preparation-uses" / f"{failure_challenge['content_sha256']}.terminal.json").read_text())
    assert failure_terminal["runtime_material_generation_started"] is True
    assert failure_terminal["partial_runtime_material_destroyed"] is True
    assert failure_terminal["automatic_retry_allowed"] is False
    assert b"SYNTHETIC_PARTIAL_SECRET" not in module.canonical(failure_terminal)

    permissions_endpoint = endpoint_manifest(RUN_ID, SOURCE_COMMIT, "permissions")
    permissions_root, permissions_endpoint_path = create_private_root(private_root, "permissions", permissions_endpoint)
    permissions_endpoint_path.chmod(0o644)
    permissions_challenge, permissions_challenge_path, permissions_signature = create_challenge(
        private_root, owner_key, anchor, "permissions", permissions_endpoint, permissions_root,
    )
    try:
        module.prepare(permissions_challenge_path, permissions_signature, SOURCE_COMMIT, NOW + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_ENDPOINT_MANIFEST_PERMISSIONS"
    else:
        raise AssertionError("insecure endpoint manifest permissions admitted")
    permissions_terminal = json.loads((permissions_root / "runtime-preparation-uses" / f"{permissions_challenge['content_sha256']}.terminal.json").read_text())
    assert permissions_terminal["runtime_material_generation_started"] is False
    assert permissions_terminal["automatic_retry_allowed"] is False

    source_endpoint = endpoint_manifest(RUN_ID, SOURCE_COMMIT, "source")
    source_root, _source_endpoint_path = create_private_root(private_root, "source", source_endpoint)
    _source_challenge, source_challenge_path, source_signature = create_challenge(
        private_root, owner_key, anchor, "source", source_endpoint, source_root,
    )
    try:
        module.prepare(source_challenge_path, source_signature, "b" * 40, NOW + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_PREPARATION_BINDINGS"
    else:
        raise AssertionError("wrong source commit admitted")

    namespace_endpoint = endpoint_manifest(RUN_ID, SOURCE_COMMIT, "namespace")
    namespace_root, _namespace_endpoint_path = create_private_root(private_root, "namespace", namespace_endpoint)
    _namespace_challenge, namespace_challenge_path, _namespace_signature = create_challenge(
        private_root, owner_key, anchor, "namespace", namespace_endpoint, namespace_root,
    )
    namespace_signature = sign(namespace_challenge_path, owner_key, "wrong-namespace")
    try:
        module.prepare(namespace_challenge_path, namespace_signature, SOURCE_COMMIT, NOW + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_PREPARATION_OWNER_SIGNATURE_INVALID"
    else:
        raise AssertionError("wrong owner signature namespace admitted")

    completion_endpoint = endpoint_manifest(RUN_ID, SOURCE_COMMIT, "completion-expiry")
    completion_root, _completion_endpoint_path = create_private_root(private_root, "completion-expiry", completion_endpoint)
    completion_challenge, completion_challenge_path, completion_signature = create_challenge(
        private_root, owner_key, anchor, "completion-expiry", completion_endpoint, completion_root,
    )
    try:
        module.prepare(
            completion_challenge_path, completion_signature, SOURCE_COMMIT,
            NOW + timedelta(seconds=1), clock=lambda: NOW + timedelta(hours=2),
        )
    except module.SafeFailure as error:
        assert str(error) == "E_PREPARATION_NOT_CURRENT_AFTER_GENERATION"
    else:
        raise AssertionError("runtime material published after preparation authority expired")
    assert not (completion_root / "credentials").exists()
    assert not (completion_root / "manifests" / "runtime-credentials.json").exists()
    completion_terminal = json.loads((completion_root / "runtime-preparation-uses" / f"{completion_challenge['content_sha256']}.terminal.json").read_text())
    assert completion_terminal["runtime_material_generation_started"] is True
    assert completion_terminal["partial_runtime_material_destroyed"] is True
    assert completion_terminal["automatic_retry_allowed"] is False

    ready_status = module.status()
    assert ready_status["status"] == "BLOCKED_EXACT_OWNER_SIGNED_RUNTIME_PREPARATION_CHALLENGE_REQUIRED"
    assert ready_status["owner_trust_anchor_present"] is True and ready_status["owner_trust_anchor_valid"] is True
    assert ready_status["private_endpoint_manifest_instance_read"] is False
    assert ready_status["runtime_credential_files_read"] is False and ready_status["runtime_material_generated"] is False
    assert ready_status["network_accessed"] is False and ready_status["execution_authorized"] is False

status = module.status()
assert status["status"] == "BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_REQUIRED"
assert status["owner_trust_anchor_present"] is False and status["owner_trust_anchor_valid"] is False
assert status["private_endpoint_manifest_instance_read"] is False
assert status["runtime_credential_files_read"] is False and status["runtime_material_generated"] is False
assert status["ambient_or_preexisting_credentials_accessed"] is False
assert status["network_accessed"] is False
assert status["external_hosts_contacted"] == status["listeners_started"] == 0
assert status["services_started"] == status["faults_injected"] == status["spend_usd_cents"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

print("t22_a1_runtime_material_preparer_check\tpass")
print("synthetic_success_count\t1")
print("directed_negative_test_count\t10")
print("real_private_endpoint_manifest_instances_read\t0")
print("real_credentials_or_private_keys_read\t0")
print("synthetic_certificate_count\t5")
print("synthetic_retained_private_key_count\t5")
print("synthetic_private_ca_signing_keys_retained\t0")
print("network_accessed\tfalse")
print("external_hosts_contacted\t0")
print("listeners_started\t0")
print("services_started\t0")
print("faults_injected\t0")
print("spend_usd_cents\t0")
