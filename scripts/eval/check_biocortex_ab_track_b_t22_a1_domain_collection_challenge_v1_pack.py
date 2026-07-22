"""Synthetic offline KATs for the T22-A1 collection-challenge gate."""
from __future__ import annotations

import argparse
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
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_collection_challenge_v1.py"
spec = importlib.util.spec_from_file_location("t22a1collectionchallenge", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

_preflight, contract, proposal, schema = module.load_committed_inputs()
NOW = datetime(2026, 7, 22, 22, 0, tzinfo=timezone.utc)
SOURCE_COMMIT = "a" * 40


def digest(label: str) -> str:
    return hashlib.sha256(f"T22_A1_SYNTHETIC_COLLECTION_CHALLENGE_ONLY:{label}".encode()).hexdigest()


def rewrite_digest(value: dict) -> None:
    value.pop("content_sha256", None)
    value["content_sha256"] = module.domain_digest(value)


def rejected_challenge(base: dict, anchor: dict, mutate, now: datetime = NOW) -> None:  # noqa: ANN001
    candidate = copy.deepcopy(base)
    mutate(candidate)
    rewrite_digest(candidate)
    try:
        module.validate_challenge(candidate, anchor, contract, proposal, schema, SOURCE_COMMIT, now)
    except module.SafeFailure:
        return
    raise AssertionError("unsafe challenge mutation admitted after digest recomputation")


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
with tempfile.TemporaryDirectory(prefix="t22-a1-collection-challenge-kat-") as directory:
    private_root = Path(directory).resolve()
    owner_key = private_root / "synthetic-owner"
    domain_key = private_root / "synthetic-domain"
    wrong_key = private_root / "synthetic-wrong-owner"
    for path in (owner_key, domain_key, wrong_key):
        subprocess.run(
            [ssh_keygen, "-q", "-t", "ed25519", "-N", "", "-C", "T22_A1_SYNTHETIC_ONLY", "-f", str(path)],
            check=True,
        )
    anchor = module.build_anchor(Path(str(owner_key) + ".pub"), proposal, proposal["proposal_sha256"])
    module.validate_anchor(anchor, proposal)
    arguments = argparse.Namespace(
        domain_id="domain-1",
        expected_hostname="tb14",
        logical_alias=["tb14", "aio2", "pallasting-ThinkBook-14-G5-IRH"],
        operating_system="LINUX",
        architecture="X86_64",
        provider_kind="OWNER_PHYSICAL",
        provider_identity_verifier_id=None,
        peer_endpoint_set_sha256=digest("endpoint-set"),
        acl_policy_receipt_sha256=digest("acl"),
        pinned_tool_receipt_sha256=digest("tools"),
        private_data_root_sha256=digest("data-root"),
        port_set_sha256=digest("ports"),
        domain_public_key=Path(str(domain_key) + ".pub"),
        artifact_root=private_root / "artifacts",
        maximum_lifetime_seconds=3600,
    )
    challenge = module.build_challenge(anchor, contract, proposal, arguments, SOURCE_COMMIT, NOW)
    assert challenge["target"]["logical_aliases"] == sorted(module.KNOWN_ALIAS_CLASS)
    assert challenge["claims"]["challenge_is_execution_authority"] is False
    challenge_path = private_root / "challenge.json"
    challenge_path.write_bytes(module.canonical(challenge) + b"\n")
    challenge_signature = sign(challenge_path, owner_key)

    stable_paths = {
        "/etc/machine-id", "/var/lib/dbus/machine-id", "/proc/sys/kernel/random/boot_id",
        "/sys/class/dmi/id/product_uuid", "/sys/class/dmi/id/product_serial",
    }
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if str(path) in stable_paths:
            raise AssertionError("stable host identity read before collector authorization")
        return original_read_bytes(path)

    Path.read_bytes = guarded_read_bytes
    try:
        receipt = module.verify_challenge_files(
            challenge_path, challenge_signature, anchor, SOURCE_COMMIT, NOW + timedelta(seconds=1),
        )
    finally:
        Path.read_bytes = original_read_bytes
    assert receipt["status"] == "OWNER_SIGNED_DOMAIN_COLLECTION_CHALLENGE_VERIFIED_NO_COLLECTION_PERFORMED"
    assert receipt["stable_host_identity_read"] is False
    assert receipt["credentials_accessed"] is False and receipt["network_accessed"] is False
    assert receipt["external_hosts_contacted"] == receipt["services_started"] == receipt["faults_injected"] == 0
    assert receipt["attestation_items_created"] == 0
    assert receipt["execution_authorized"] is False and receipt["production_admissible"] is False

    challenge_mutations = (
        lambda x: x.update(schema="other"),
        lambda x: x.update(packet_kind="EXECUTE"),
        lambda x: x.update(decision="AUTHORIZE_EXECUTION"),
        lambda x: x["hashing_contract"].update(self_hash_field_excluded=False),
        lambda x: x["owner_binding"].update(owner_public_key_sha256=digest("other-owner")),
        lambda x: x["owner_binding"].update(signature_namespace="agent-bridge-t22-a1-owner-v1"),
        lambda x: x["target"].update(domain_id="domain-4"),
        lambda x: x["target"].update(expected_hostname="missing-from-aliases"),
        lambda x: x["target"].update(logical_aliases=["aio2", "tb14"]),
        lambda x: x["target"].update(provider_kind="CLOUD_VM", provider_identity_verifier_id="unfrozen-provider-v1"),
        lambda x: x["bindings"].update(source_commit="b" * 40),
        lambda x: x["bindings"].update(owner_decision_proposal_sha256=digest("other-proposal")),
        lambda x: x["bindings"].update(admission_contract_sha256=digest("other-contract")),
        lambda x: x["bindings"].update(collection_challenge_schema_sha256=digest("other-schema")),
        lambda x: x["network_binding"].update(raw_endpoints_embedded=True),
        lambda x: x["network_binding"].update(overlay_credentials_embedded=True),
        lambda x: x["workload_binding"].update(private_key_export_allowed=True),
        lambda x: x["collection_authority"].update(maximum_lifetime_seconds=3601),
        lambda x: x["collection_authority"].update(expires_at=module.utc_text(NOW + timedelta(seconds=1800))),
        lambda x: x["collection_authority"]["allowed_reads_after_signature"].append("AMBIENT_CREDENTIALS"),
        lambda x: x["collection_authority"]["forbidden"].remove("NETWORK_OR_EXTERNAL_HOST_CONNECTION"),
        lambda x: x["artifact_scope"].update(artifact_root=str(ROOT)),
        lambda x: x["artifact_scope"].update(domain_output_directory=str(private_root / "artifacts" / "domain-2")),
        lambda x: x["artifact_scope"].update(repository_output_allowed=True),
        lambda x: x["artifact_scope"].update(raw_identity_values_allowed=True),
        lambda x: x["claims"].update(challenge_is_execution_authority=True),
        lambda x: x["claims"].update(distinct_physical_host_proved=True),
        lambda x: x["claims"].update(production_admissible=True),
        lambda x: x.update(unexpected="field"),
    )
    for mutation in challenge_mutations:
        rejected_challenge(challenge, anchor, mutation)

    expired = copy.deepcopy(challenge)
    rejected_challenge(expired, anchor, lambda x: None, NOW + timedelta(hours=2))

    anchor_mutations = (
        lambda x: x.update(owner_id="other"),
        lambda x: x.update(owner_decision_proposal_sha256=digest("other-proposal")),
        lambda x: x.update(public_key_sha256=digest("other-key")),
        lambda x: x.update(allowed_signature_namespaces=[module.SIGNATURE_NAMESPACE]),
        lambda x: x.update(unexpected="field"),
    )
    for mutation in anchor_mutations:
        candidate = copy.deepcopy(anchor)
        mutation(candidate)
        try:
            module.validate_anchor(candidate, proposal)
        except module.SafeFailure:
            continue
        raise AssertionError("unsafe owner anchor mutation admitted")

    malformed_public_key = private_root / "malformed.pub"
    malformed_public_key.write_text("ssh-ed25519 AAAA synthetic\n")
    try:
        module.build_anchor(malformed_public_key, proposal, proposal["proposal_sha256"])
    except module.SafeFailure as error:
        assert str(error) == "E_OWNER_PUBLIC_KEY_FORMAT"
    else:
        raise AssertionError("malformed Ed25519 owner key admitted")

    symlinked_public_key = private_root / "symlinked-owner.pub"
    symlinked_public_key.symlink_to(Path(str(owner_key) + ".pub"))
    try:
        module.build_anchor(symlinked_public_key, proposal, proposal["proposal_sha256"])
    except module.SafeFailure as error:
        assert str(error) == "E_OWNER_PUBLIC_KEY_FILE"
    else:
        raise AssertionError("symlinked owner public key admitted")

    generated_root = private_root / "generated-artifacts"
    exact_output = generated_root / "authorizations" / "domain-1-collection-challenge.json"
    module.prepare_challenge_output(exact_output, generated_root, "domain-1")
    assert generated_root.stat().st_mode & 0o077 == 0
    assert exact_output.parent.stat().st_mode & 0o077 == 0
    try:
        module.prepare_challenge_output(exact_output.with_name("other.json"), generated_root, "domain-1")
    except module.SafeFailure as error:
        assert str(error) == "E_CHALLENGE_OUTPUT_PATH"
    else:
        raise AssertionError("non-exact challenge output path admitted")
    insecure_root = private_root / "insecure-artifacts"
    insecure_root.mkdir(mode=0o755)
    insecure_root.chmod(0o755)
    try:
        module.prepare_challenge_output(
            insecure_root / "authorizations" / "domain-1-collection-challenge.json",
            insecure_root, "domain-1",
        )
    except module.SafeFailure as error:
        assert str(error) == "E_PRIVATE_ARTIFACT_DIRECTORY"
    else:
        raise AssertionError("insecure private artifact root admitted")

    wrong_signature = sign(challenge_path, wrong_key)
    try:
        module.verify_challenge_files(challenge_path, wrong_signature, anchor, SOURCE_COMMIT, NOW + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_OWNER_SIGNATURE_INVALID"
    else:
        raise AssertionError("wrong owner signature admitted")

    wrong_namespace_signature = sign(challenge_path, owner_key, "wrong-namespace")
    try:
        module.verify_challenge_files(challenge_path, wrong_namespace_signature, anchor, SOURCE_COMMIT, NOW + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_OWNER_SIGNATURE_INVALID"
    else:
        raise AssertionError("wrong signature namespace admitted")

    noncanonical_path = private_root / "noncanonical.json"
    noncanonical_path.write_text(json.dumps(challenge, indent=2) + "\n")
    noncanonical_signature = sign(noncanonical_path, owner_key)
    try:
        module.verify_challenge_files(noncanonical_path, noncanonical_signature, anchor, SOURCE_COMMIT, NOW + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_CHALLENGE_FRAMING"
    else:
        raise AssertionError("noncanonical challenge admitted")

status = module.status()
assert status["status"] == "BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_REQUIRED"
assert status["owner_trust_anchor_present"] is False
assert status["stable_host_identity_read"] is False
assert status["credentials_accessed"] is False and status["network_accessed"] is False
assert status["external_hosts_contacted"] == status["services_started"] == status["faults_injected"] == 0
assert status["attestation_items_created"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

negative_count = len(challenge_mutations) + 1 + len(anchor_mutations) + 3 + 4
print("t22_a1_domain_collection_challenge_check\tpass")
print(f"directed_negative_test_count\t{negative_count}")
print("real_host_identifiers_read\tfalse")
print("network_accessed\tfalse")
print("credentials_accessed\tfalse")
print("external_hosts_contacted\t0")
print("services_started\t0")
print("faults_injected\t0")
print("real_attestation_items_created\t0")
