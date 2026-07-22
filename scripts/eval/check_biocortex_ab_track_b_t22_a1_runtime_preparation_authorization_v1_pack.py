"""Synthetic offline KATs for the T22-A1 runtime-preparation authorization gate."""
from __future__ import annotations

import copy
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
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_runtime_preparation_authorization_v1.py"
spec = importlib.util.spec_from_file_location("t22a1runtimepreparation", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

collection, _runtime, contract, proposal, schema = module.load_inputs()
NOW = datetime(2026, 7, 22, 23, 30, tzinfo=timezone.utc)
SOURCE_COMMIT = "a" * 40
RUN_ID = "t22-a1-20260722T233000.000000z-123456789abc"


def digest(label: str) -> str:
    return hashlib.sha256(f"T22_A1_SYNTHETIC_RUNTIME_PREPARATION_ONLY:{label}".encode()).hexdigest()


def rewrite_digest(value: dict) -> None:
    value.pop("content_sha256", None)
    value["content_sha256"] = module.challenge_digest(value)


def rejected_challenge(base: dict, anchor: dict, mutate, now: datetime = NOW) -> None:  # noqa: ANN001
    candidate = copy.deepcopy(base)
    mutate(candidate)
    rewrite_digest(candidate)
    try:
        module.validate_challenge(
            candidate, anchor, contract, proposal, schema, SOURCE_COMMIT,
            base["bindings"]["exact_three_domain_attestation_set_sha256"],
            base["bindings"]["private_endpoint_manifest_content_sha256"], now,
        )
    except module.SafeFailure:
        return
    raise AssertionError("unsafe runtime-preparation mutation admitted after digest recomputation")


def sign(path: Path, private_key: Path, namespace: str = module.SIGNATURE_NAMESPACE) -> Path:
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
with tempfile.TemporaryDirectory(prefix="t22-a1-runtime-preparation-kat-") as directory:
    private_root = Path(directory).resolve()
    owner_key = private_root / "synthetic-owner"
    wrong_key = private_root / "synthetic-wrong-owner"
    for path in (owner_key, wrong_key):
        subprocess.run(
            [ssh_keygen, "-q", "-t", "ed25519", "-N", "", "-C", "T22_A1_SYNTHETIC_ONLY", "-f", str(path)],
            check=True,
        )
    anchor = collection.build_anchor(Path(str(owner_key) + ".pub"), proposal, proposal["proposal_sha256"])
    collection.validate_anchor(anchor, proposal)
    artifact_root = private_root / "artifacts"
    openssl = Path(shutil.which("openssl") or "").resolve(strict=True)
    ssh_keygen_path = Path(ssh_keygen).resolve(strict=True)
    attestation_set_sha256 = digest("attestation-set")
    endpoint_manifest_sha256 = digest("endpoint-manifest")
    challenge = module.build_challenge(
        anchor, contract, proposal, SOURCE_COMMIT, RUN_ID,
        attestation_set_sha256, endpoint_manifest_sha256, artifact_root,
        openssl, hashlib.sha256(openssl.read_bytes()).hexdigest(),
        ssh_keygen_path, hashlib.sha256(ssh_keygen_path.read_bytes()).hexdigest(),
        NOW, NOW + timedelta(hours=4), 3600, 3600,
    )
    assert challenge["claims"]["preparation_is_execution_authority"] is False
    assert challenge["preparation_authority"]["spend_limit_usd_cents"] == 0
    challenge_path = private_root / "challenge.json"
    challenge_path.write_bytes(module.canonical(challenge) + b"\n")
    challenge_signature = sign(challenge_path, owner_key)

    forbidden_reads = {
        artifact_root / "manifests" / "private-endpoints.json",
        artifact_root / "manifests" / "runtime-credentials.json",
        artifact_root / "credentials" / "coordinator-runtime.pub",
    }
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path.resolve(strict=False) in {item.resolve(strict=False) for item in forbidden_reads}:
            raise AssertionError("private manifest or credential read by authorization verifier")
        return original_read_bytes(path)

    Path.read_bytes = guarded_read_bytes
    try:
        receipt = module.verify_challenge_files(
            challenge_path, challenge_signature, anchor, SOURCE_COMMIT, NOW + timedelta(seconds=1),
        )
    finally:
        Path.read_bytes = original_read_bytes
    assert receipt["status"] == "OWNER_SIGNED_RUNTIME_PREPARATION_CHALLENGE_VERIFIED_NO_MATERIAL_GENERATED"
    assert receipt["private_endpoint_manifest_instance_read"] is False
    assert receipt["credential_files_read"] is False and receipt["runtime_material_generated"] is False
    assert receipt["network_accessed"] is False
    assert receipt["listeners_started"] == receipt["services_started"] == receipt["faults_injected"] == 0
    assert receipt["spend_usd_cents"] == 0
    assert receipt["execution_authorized"] is False and receipt["production_admissible"] is False

    challenge_mutations = (
        lambda x: x.update(schema="other"),
        lambda x: x.update(packet_kind="EXECUTE"),
        lambda x: x.update(decision="AUTHORIZE_EXECUTION"),
        lambda x: x["hashing_contract"].update(self_hash_field_excluded=False),
        lambda x: x["owner_binding"].update(owner_public_key_sha256=digest("other-owner")),
        lambda x: x["owner_binding"].update(signature_namespace="agent-bridge-t22-a1-owner-v1"),
        lambda x: x["bindings"].update(source_commit="b" * 40),
        lambda x: x["bindings"].update(owner_decision_proposal_sha256=digest("other-proposal")),
        lambda x: x["bindings"].update(admission_contract_sha256=digest("other-contract")),
        lambda x: x["bindings"].update(exact_three_domain_attestation_set_sha256=digest("other-attestations")),
        lambda x: x["bindings"].update(private_endpoint_manifest_schema_sha256=digest("other-endpoint-schema")),
        lambda x: x["bindings"].update(private_endpoint_manifest_content_sha256=digest("other-endpoints")),
        lambda x: x["bindings"].update(runtime_credential_manifest_schema_sha256=digest("other-credential-schema")),
        lambda x: x["bindings"].update(domain_agent_message_schema_sha256=digest("other-message-schema")),
        lambda x: x["bindings"].update(distributed_execution_contract_schema_sha256=digest("other-execution-schema")),
        lambda x: x["bindings"].update(runtime_preparation_challenge_schema_sha256=digest("other-preparation-schema")),
        lambda x: x["target"].update(run_id="t22-a1-invalid"),
        lambda x: x["target"].update(private_artifact_root=str(ROOT)),
        lambda x: x["target"].update(private_endpoint_manifest_path=str(artifact_root / "other.json")),
        lambda x: x["target"].update(runtime_credential_manifest_output_path=str(artifact_root / "other.json")),
        lambda x: x["target"].update(coordinator_runtime_public_key_output_path=str(artifact_root / "other.pub")),
        lambda x: x["target"].update(openssl_executable_path=str(ROOT / "synthetic-openssl")),
        lambda x: x["target"].update(ssh_keygen_executable_path=str(ROOT / "synthetic-ssh-keygen")),
        lambda x: x["target"].update(planned_execution_expires_at=module.utc_text(NOW + timedelta(minutes=30))),
        lambda x: x["target"].update(planned_execution_expires_at=module.utc_text(NOW + timedelta(hours=25))),
        lambda x: x["target"].update(credential_validity_margin_seconds=299),
        lambda x: x["preparation_authority"].update(maximum_lifetime_seconds=3601),
        lambda x: x["preparation_authority"].update(expires_at=module.utc_text(NOW + timedelta(minutes=30))),
        lambda x: x["preparation_authority"].update(one_preparation_per_challenge_sha256=False),
        lambda x: x["preparation_authority"].update(spend_limit_usd_cents=1),
        lambda x: x["preparation_authority"]["allowed_after_signature"].append("NETWORK"),
        lambda x: x["preparation_authority"]["forbidden"].remove("NETWORK_OR_EXTERNAL_HOST_CONNECTION"),
        lambda x: x["claims"].update(preparation_is_execution_authority=True),
        lambda x: x["claims"].update(three_failure_domain_execution_proved=True),
        lambda x: x["claims"].update(external_anti_rollback_proved=True),
        lambda x: x["claims"].update(production_admissible=True),
        lambda x: x.update(unexpected="field"),
    )
    for mutation in challenge_mutations:
        rejected_challenge(challenge, anchor, mutation)
    rejected_challenge(challenge, anchor, lambda x: None, NOW + timedelta(hours=2))
    try:
        module.validate_challenge(
            challenge, anchor, contract, proposal, schema, SOURCE_COMMIT,
            attestation_set_sha256, endpoint_manifest_sha256, datetime(2026, 7, 22, 23, 30),
        )
    except module.SafeFailure as error:
        assert str(error) == "E_PREPARATION_VALIDATION_TIME"
    else:
        raise AssertionError("naive validation time admitted")

    wrong_signature = sign(challenge_path, wrong_key)
    try:
        module.verify_challenge_files(
            challenge_path, wrong_signature, anchor, SOURCE_COMMIT, NOW + timedelta(seconds=1),
        )
    except module.SafeFailure as error:
        assert str(error) == "E_PREPARATION_OWNER_SIGNATURE_INVALID"
    else:
        raise AssertionError("wrong owner signature admitted")

    wrong_namespace_signature = sign(challenge_path, owner_key, "wrong-namespace")
    try:
        module.verify_challenge_files(
            challenge_path, wrong_namespace_signature, anchor, SOURCE_COMMIT, NOW + timedelta(seconds=1),
        )
    except module.SafeFailure as error:
        assert str(error) == "E_PREPARATION_OWNER_SIGNATURE_INVALID"
    else:
        raise AssertionError("wrong signature namespace admitted")

    noncanonical_path = private_root / "noncanonical.json"
    noncanonical_path.write_text(json.dumps(challenge, indent=2) + "\n")
    noncanonical_signature = sign(noncanonical_path, owner_key)
    try:
        module.verify_challenge_files(
            noncanonical_path, noncanonical_signature, anchor, SOURCE_COMMIT, NOW + timedelta(seconds=1),
        )
    except module.SafeFailure as error:
        assert str(error) in {"E_PREPARATION_CHALLENGE_FRAMING", "E_PREPARATION_CHALLENGE_NOT_CANONICAL"}
    else:
        raise AssertionError("noncanonical challenge admitted")

    exact_output = artifact_root / "authorizations" / "runtime-preparation-challenge.json"
    module.prepare_challenge_output(exact_output, artifact_root)
    assert artifact_root.stat().st_mode & 0o077 == 0
    assert exact_output.parent.stat().st_mode & 0o077 == 0
    try:
        module.prepare_challenge_output(exact_output.with_name("other.json"), artifact_root)
    except module.SafeFailure as error:
        assert str(error) == "E_PREPARATION_OUTPUT_PATH"
    else:
        raise AssertionError("non-exact runtime-preparation output path admitted")
    insecure_root = private_root / "insecure-artifacts"
    insecure_root.mkdir(mode=0o755)
    insecure_root.chmod(0o755)
    try:
        module.prepare_challenge_output(
            insecure_root / "authorizations" / "runtime-preparation-challenge.json", insecure_root,
        )
    except module.SafeFailure as error:
        assert str(error) == "E_PREPARATION_PRIVATE_ARTIFACT_DIRECTORY"
    else:
        raise AssertionError("insecure private artifact root admitted")

status = module.status()
assert status["status"] == "BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_REQUIRED"
assert status["owner_trust_anchor_present"] is False and status["owner_trust_anchor_valid"] is False
assert status["private_endpoint_manifest_instance_read"] is False
assert status["credential_files_read"] is False and status["runtime_material_generated"] is False
assert status["network_accessed"] is False
assert status["listeners_started"] == status["services_started"] == status["faults_injected"] == 0
assert status["spend_usd_cents"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

negative_count = len(challenge_mutations) + 2 + 3 + 2
print("t22_a1_runtime_preparation_authorization_check\tpass")
print(f"directed_negative_test_count\t{negative_count}")
print("real_private_endpoint_manifest_instances_read\t0")
print("credential_files_read\tfalse")
print("runtime_material_generated\tfalse")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("services_started\t0")
print("faults_injected\t0")
print("spend_usd_cents\t0")
