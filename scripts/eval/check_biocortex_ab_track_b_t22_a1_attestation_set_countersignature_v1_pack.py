"""Synthetic offline KATs for exact T22-A1 attestation-set countersignature."""
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
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_attestation_set_countersignature_v1.py"
spec = importlib.util.spec_from_file_location("t22a1setcountersignature", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

collection = module.load_collection_module()
attestation = module.load_attestation_module()
_preflight, contract, proposal, _collection_schema = collection.load_committed_inputs()
module.load_collection_module = lambda: collection
module.load_attestation_module = lambda: attestation
NOW = datetime(2026, 7, 22, 20, 0, tzinfo=timezone.utc)
SOURCE_COMMIT = "a" * 40


def digest(label: str) -> str:
    return hashlib.sha256(f"T22_A1_SYNTHETIC_SET_COUNTERSIGNATURE_ONLY:{label}".encode()).hexdigest()


def packet(domain_number: int, public_key: Path) -> dict:
    domain_id = f"domain-{domain_number}"
    hostname = {1: "tb14", 2: "maxiaodeMac-Pro.local", 3: "third-host"}[domain_number]
    aliases = {
        1: ["aio2", "pallasting-ThinkBook-14-G5-IRH", "tb14"],
        2: ["mac", "maxiaodeMac-Pro.local"],
        3: ["third-host"],
    }[domain_number]
    issued = NOW + timedelta(seconds=domain_number)
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
        "domain_id": domain_id,
        "attested_at": module.utc_text(issued),
        "expires_at": module.utc_text(issued + timedelta(hours=1)),
        "source_commit": SOURCE_COMMIT,
        "host_identity": {
            "hostname": hostname,
            "logical_aliases": aliases,
            "operating_system": "MACOS" if domain_number == 2 else "LINUX",
            "kernel_release": "synthetic-kernel",
            "architecture": "AARCH64" if domain_number == 2 else "X86_64",
            "machine_id_sha256": digest(f"machine:{domain_number}"),
            "hardware_identity_sha256": digest(f"hardware:{domain_number}"),
            "boot_id_sha256": digest(f"boot:{domain_number}"),
            "physical_host_asserted": True,
            "provider_kind": "OWNER_PHYSICAL",
            "provider_identity_sha256": None,
            "region": None,
            "zone": None,
            "instance_identity_sha256": None,
        },
        "operator_binding": {
            "operator_role": "T22_A1_DOMAIN_OPERATOR",
            "public_key_sha256": attestation.canonical_public_key(public_key)[1],
            "signature_scheme": "OPENSSH_SSHSIG_ED25519",
            "signature_namespace": attestation.SIGNATURE_NAMESPACE,
            "private_key_exported": False,
        },
        "network_binding": {
            "transport": "OWNER_MANAGED_PRIVATE_OVERLAY",
            "peer_endpoint_set_sha256": digest("endpoint-set"),
            "acl_policy_receipt_sha256": digest("acl"),
            "public_listener_allowed": False,
            "credential_material_embedded": False,
        },
        "workload_readiness": {
            "pinned_tool_receipt_sha256": digest(f"tools:{domain_number}"),
            "private_data_root_sha256": digest(f"data:{domain_number}"),
            "port_set_sha256": digest(f"ports:{domain_number}"),
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
    value["attestation_sha256"] = attestation.domain_digest(attestation.ATTESTATION_DOMAIN, value)
    return value


def write_bundle(bundle: Path, domain_keys: list[Path]) -> None:
    bundle.mkdir(mode=0o700)
    bundle.chmod(0o700)
    for number, key in enumerate(domain_keys, start=1):
        public = bundle / f"domain-{number}.pub"
        shutil.copyfile(str(key) + ".pub", public)
        value = packet(number, public)
        path = bundle / f"domain-{number}.json"
        path.write_bytes(attestation.canonical(value) + b"\n")
        result = subprocess.run(
            [SSH_KEYGEN, "-Y", "sign", "-f", str(key), "-n", attestation.SIGNATURE_NAMESPACE, str(path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        assert result.returncode == 0 and path.with_suffix(".json.sig").is_file()


def sign(path: Path, owner_key: Path, namespace: str = module.SIGNATURE_NAMESPACE) -> Path:
    signature = path.with_suffix(path.suffix + ".sig")
    if signature.exists():
        signature.unlink()
    result = subprocess.run(
        [SSH_KEYGEN, "-Y", "sign", "-f", str(owner_key), "-n", namespace, str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    assert result.returncode == 0 and signature.is_file()
    return signature


def rewrite_digest(value: dict) -> None:
    value.pop("content_sha256", None)
    value["content_sha256"] = module.challenge_digest(value)


def rejected_envelope(base: dict, anchor: dict, mutate, now: datetime) -> None:  # noqa: ANN001
    candidate = copy.deepcopy(base)
    mutate(candidate)
    rewrite_digest(candidate)
    try:
        module.validate_envelope(candidate, anchor, contract, proposal, schema, SOURCE_COMMIT, now)
    except module.SafeFailure:
        return
    raise AssertionError("unsafe countersignature envelope mutation admitted")


SSH_KEYGEN = shutil.which("ssh-keygen")
assert SSH_KEYGEN is not None
_collection, _attestation, _contract, _proposal, schema = module.load_inputs()
with tempfile.TemporaryDirectory(prefix="t22-a1-set-countersignature-kat-") as directory:
    private_root = Path(directory).resolve()
    owner_key = private_root / "owner"
    wrong_owner_key = private_root / "wrong-owner"
    domain_keys = [private_root / f"domain-key-{number}" for number in (1, 2, 3)]
    for key in (owner_key, wrong_owner_key, *domain_keys):
        subprocess.run([SSH_KEYGEN, "-q", "-t", "ed25519", "-N", "", "-C", "T22_A1_SYNTHETIC_ONLY", "-f", str(key)], check=True)
    anchor = collection.build_anchor(Path(str(owner_key) + ".pub"), proposal, proposal["proposal_sha256"])
    anchor_path = private_root / "owner-anchor.json"
    anchor_path.write_bytes(collection.canonical(anchor) + b"\n")
    anchor_path.chmod(0o600)
    collection.ANCHOR_PATH = anchor_path
    bundle = private_root / "bundle"
    write_bundle(bundle, domain_keys)
    artifact_root = private_root / "artifacts-valid"
    issued = NOW + timedelta(minutes=1)
    challenge = module.build_challenge(
        anchor, contract, proposal, bundle, SOURCE_COMMIT, artifact_root, issued, 1800,
    )
    artifact_root.mkdir(mode=0o700)
    artifact_root.chmod(0o700)
    challenge_path = private_root / "set-countersignature.json"
    challenge_path.write_bytes(module.canonical(challenge) + b"\n")
    owner_signature = sign(challenge_path, owner_key)
    receipt = module.admit(
        challenge_path, owner_signature, bundle, SOURCE_COMMIT, issued + timedelta(seconds=1),
    )
    assert receipt["status"] == "THREE_DOMAIN_INPUT_SET_OWNER_COUNTERSIGNED_ADMITTED_NON_EXECUTING"
    assert receipt["attestation_set_sha256"] == challenge["verified_set"]["attestation_set_sha256"]
    assert receipt["owner_countersignature_verified"] is True
    assert receipt["all_domain_attestations_current"] is True
    assert receipt["all_domain_signatures_verified"] is True
    assert receipt["all_domain_distinctness_checks_passed"] is True
    assert receipt["raw_identity_values_embedded"] is False
    assert receipt["credentials_accessed"] is False and receipt["network_accessed"] is False
    assert receipt["external_hosts_contacted"] == receipt["services_started"] == receipt["faults_injected"] == 0
    assert receipt["execution_authorized"] is False and receipt["production_admissible"] is False
    unsigned_receipt = dict(receipt)
    claimed_receipt_sha256 = unsigned_receipt.pop("content_sha256")
    assert claimed_receipt_sha256 == module.digest(module.ADMISSION_RECEIPT_DOMAIN, unsigned_receipt)
    output = artifact_root / "admissions" / "owner-countersigned-attestation-set.json"
    assert output.read_bytes() == module.canonical(receipt) + b"\n"
    assert output.stat().st_mode & 0o077 == 0
    receipt_raw = output.read_bytes()
    for number in (1, 2, 3):
        value = json.loads((bundle / f"domain-{number}.json").read_text())
        assert value["host_identity"]["machine_id_sha256"].encode() not in receipt_raw
        assert value["host_identity"]["hardware_identity_sha256"].encode() not in receipt_raw

    receipt_mutations = (
        lambda x: x.update(status="EXECUTION_AUTHORIZED"),
        lambda x: x.update(source_commit="b" * 40),
        lambda x: x.update(admission_contract_sha256=digest("other-contract")),
        lambda x: x.update(owner_decision_proposal_sha256=digest("other-proposal")),
        lambda x: x["packet_bindings"].pop(),
        lambda x: x["signature_bindings"][0].update(signature_sha256="0" * 64),
        lambda x: x["set_validation"].update(distinct_hardware_identity_count=2),
        lambda x: x.update(owner_countersignature_verified=False),
        lambda x: x.update(all_domain_attestations_current=False),
        lambda x: x.update(all_domain_signatures_verified=False),
        lambda x: x.update(all_domain_distinctness_checks_passed=False),
        lambda x: x.update(raw_identity_values_embedded=True),
        lambda x: x.update(credentials_accessed=True),
        lambda x: x.update(network_accessed=True),
        lambda x: x.update(services_started=1),
        lambda x: x.update(execution_authorized=True),
        lambda x: x.update(production_admissible=True),
        lambda x: x.update(unexpected="field"),
    )
    for mutation in receipt_mutations:
        candidate = copy.deepcopy(receipt)
        mutation(candidate)
        candidate.pop("content_sha256", None)
        candidate["content_sha256"] = module.digest(module.ADMISSION_RECEIPT_DOMAIN, candidate)
        try:
            module.validate_admission_receipt(candidate, SOURCE_COMMIT, contract, proposal, issued + timedelta(seconds=2))
        except module.SafeFailure:
            continue
        raise AssertionError("unsafe admitted-set receipt mutation accepted")
    try:
        module.validate_admission_receipt(
            receipt, SOURCE_COMMIT, contract, proposal,
            module.parse_time(receipt["earliest_attestation_expires_at"], "E_TEST_TIME") + timedelta(seconds=1),
        )
    except module.SafeFailure as error:
        assert str(error) == "E_ADMITTED_SET_RECEIPT_NOT_CURRENT"
    else:
        raise AssertionError("expired admitted-set receipt accepted")

    try:
        module.reserve(artifact_root, challenge, SOURCE_COMMIT, issued + timedelta(seconds=2))
    except module.SafeFailure as error:
        assert str(error) == "E_COUNTERSIGNATURE_OUTPUT_EXISTS"
    else:
        raise AssertionError("countersignature replay reservation admitted")

    envelope_mutations = (
        lambda x: x.update(schema="other"),
        lambda x: x.update(packet_kind="EXECUTE"),
        lambda x: x.update(decision="AUTHORIZE_EXECUTION"),
        lambda x: x["hashing_contract"].update(self_hash_field_excluded=False),
        lambda x: x["owner_binding"].update(owner_public_key_sha256=digest("other-owner")),
        lambda x: x["owner_binding"].update(signature_namespace="agent-bridge-t22-a1-owner-v1"),
        lambda x: x["bindings"].update(source_commit="b" * 40),
        lambda x: x["bindings"].update(owner_decision_proposal_sha256=digest("other-proposal")),
        lambda x: x["bindings"].update(admission_contract_sha256=digest("other-contract")),
        lambda x: x["bindings"].update(domain_attestation_schema_sha256=digest("other-attestation-schema")),
        lambda x: x["bindings"].update(attestation_set_countersignature_schema_sha256=digest("other-schema")),
        lambda x: x["verified_set"]["packet_bindings"].pop(),
        lambda x: x["verified_set"]["signature_bindings"][1].update(domain_id="domain-1"),
        lambda x: x["verified_set"]["set_validation"].update(domain_count=2),
        lambda x: x["artifact_scope"].update(private_artifact_root=str(ROOT)),
        lambda x: x["artifact_scope"].update(admitted_set_receipt_output_path=str(artifact_root / "other.json")),
        lambda x: x["artifact_scope"].update(repository_output_allowed=True),
        lambda x: x["countersignature_authority"].update(maximum_lifetime_seconds=3601),
        lambda x: x["countersignature_authority"].update(expires_at=module.utc_text(issued + timedelta(seconds=10))),
        lambda x: x["countersignature_authority"]["allowed_after_signature"].append("NETWORK"),
        lambda x: x["countersignature_authority"]["forbidden"].remove("NETWORK_OR_EXTERNAL_HOST_CONNECTION"),
        lambda x: x["claims"].update(countersignature_is_execution_authority=True),
        lambda x: x["claims"].update(host_power_loss_proved=True),
        lambda x: x["claims"].update(site_power_network_independence_proved=True),
        lambda x: x["claims"].update(external_anti_rollback_proved=True),
        lambda x: x["claims"].update(production_admissible=True),
        lambda x: x.update(unexpected="field"),
    )
    for mutation in envelope_mutations:
        rejected_envelope(challenge, anchor, mutation, issued + timedelta(seconds=1))
    rejected_envelope(challenge, anchor, lambda x: None, issued + timedelta(hours=2))

    wrong_signature_root = private_root / "artifacts-wrong-signature"
    wrong_signature_challenge = module.build_challenge(
        anchor, contract, proposal, bundle, SOURCE_COMMIT, wrong_signature_root, issued, 1800,
    )
    wrong_signature_path = private_root / "wrong-signature-challenge.json"
    wrong_signature_path.write_bytes(module.canonical(wrong_signature_challenge) + b"\n")
    wrong_signature = sign(wrong_signature_path, wrong_owner_key)
    bundle_files = {path.resolve() for path in bundle.iterdir()}
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path.resolve(strict=False) in bundle_files:
            raise AssertionError("private bundle read before owner signature verification")
        return original_read_bytes(path)

    Path.read_bytes = guarded_read_bytes
    try:
        try:
            module.admit(wrong_signature_path, wrong_signature, bundle, SOURCE_COMMIT, issued + timedelta(seconds=1))
        except module.SafeFailure as error:
            assert str(error) == "E_COUNTERSIGNATURE_OWNER_SIGNATURE_INVALID"
        else:
            raise AssertionError("wrong owner signature admitted")
    finally:
        Path.read_bytes = original_read_bytes

    namespace_root = private_root / "artifacts-wrong-namespace"
    namespace_challenge = module.build_challenge(
        anchor, contract, proposal, bundle, SOURCE_COMMIT, namespace_root, issued, 1800,
    )
    namespace_path = private_root / "wrong-namespace-challenge.json"
    namespace_path.write_bytes(module.canonical(namespace_challenge) + b"\n")
    namespace_signature = sign(namespace_path, owner_key, "wrong-namespace")
    try:
        module.admit(namespace_path, namespace_signature, bundle, SOURCE_COMMIT, issued + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_COUNTERSIGNATURE_OWNER_SIGNATURE_INVALID"
    else:
        raise AssertionError("wrong countersignature namespace admitted")

    mismatch_root = private_root / "artifacts-mismatch"
    mismatch_challenge = module.build_challenge(
        anchor, contract, proposal, bundle, SOURCE_COMMIT, mismatch_root, issued, 1800,
    )
    mismatch_root.mkdir(mode=0o700)
    mismatch_root.chmod(0o700)
    mismatch_challenge["verified_set"]["attestation_set_sha256"] = digest("other-set")
    rewrite_digest(mismatch_challenge)
    mismatch_path = private_root / "mismatch-challenge.json"
    mismatch_path.write_bytes(module.canonical(mismatch_challenge) + b"\n")
    mismatch_signature = sign(mismatch_path, owner_key)
    try:
        module.admit(mismatch_path, mismatch_signature, bundle, SOURCE_COMMIT, issued + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_COUNTERSIGNATURE_REVERIFIED_SET_MISMATCH"
    else:
        raise AssertionError("owner-signed but bundle-mismatched set admitted")
    mismatch_terminal = json.loads((mismatch_root / "attestation-set-countersignature-uses" / f"{mismatch_challenge['content_sha256']}.terminal.json").read_text())
    assert mismatch_terminal["private_bundle_read"] is True
    assert mismatch_terminal["automatic_retry_allowed"] is False

    ready_status = module.status()
    assert ready_status["status"] == "BLOCKED_EXACT_PRIVATE_THREE_DOMAIN_BUNDLE_AND_OWNER_COUNTERSIGNATURE_REQUIRED"
    assert ready_status["owner_trust_anchor_present"] is True and ready_status["owner_trust_anchor_valid"] is True
    assert ready_status["private_bundle_read"] is False and ready_status["network_accessed"] is False

status = module.status()
assert status["status"] == "BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_REQUIRED"
assert status["owner_trust_anchor_present"] is False and status["owner_trust_anchor_valid"] is False
assert status["private_bundle_read"] is False and status["stable_host_identity_source_read"] is False
assert status["credentials_accessed"] is False and status["network_accessed"] is False
assert status["external_hosts_contacted"] == status["services_started"] == status["faults_injected"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

negative_count = len(envelope_mutations) + len(receipt_mutations) + 1 + 1 + 4
print("t22_a1_attestation_set_countersignature_check\tpass")
print(f"directed_negative_test_count\t{negative_count}")
print("real_private_bundles_read\t0")
print("stable_host_identity_sources_read\tfalse")
print("credentials_accessed\tfalse")
print("network_accessed\tfalse")
print("external_hosts_contacted\t0")
print("services_started\t0")
print("faults_injected\t0")
