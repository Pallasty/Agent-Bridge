"""Synthetic offline KATs for the T22-A1 domain-attestation verifier."""
from __future__ import annotations

import copy
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

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_attestation_v1.py"
spec = importlib.util.spec_from_file_location("t22a1attestation", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
preflight = module.load_preflight_module()
_, contract, _ = preflight.load_and_validate()
NOW = datetime(2026, 7, 22, 20, 0, tzinfo=timezone.utc)
SOURCE_COMMIT = "a" * 40


def digest(label: str) -> str:
    return hashlib.sha256(f"T22_A1_SYNTHETIC_ONLY:{label}".encode()).hexdigest()


def public_key_sha256(path: Path) -> str:
    return module.canonical_public_key(path)[1]


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
        "attested_at": issued.isoformat().replace("+00:00", "Z"),
        "expires_at": (issued + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "source_commit": SOURCE_COMMIT,
        "host_identity": {
            "hostname": hostname,
            "logical_aliases": aliases,
            "operating_system": "LINUX" if domain_number != 2 else "MACOS",
            "kernel_release": "synthetic-kernel",
            "architecture": "X86_64" if domain_number != 2 else "AARCH64",
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
            "public_key_sha256": public_key_sha256(public_key),
            "signature_scheme": "OPENSSH_SSHSIG_ED25519",
            "signature_namespace": module.SIGNATURE_NAMESPACE,
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
            "private_data_root_sha256": digest(f"data-root:{domain_number}"),
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
    value["attestation_sha256"] = module.domain_digest(module.ATTESTATION_DOMAIN, value)
    return value


def rewrite_and_sign(bundle: Path, domain_number: int, value: dict, key: Path) -> None:
    value = copy.deepcopy(value)
    value.pop("attestation_sha256", None)
    value["attestation_sha256"] = module.domain_digest(module.ATTESTATION_DOMAIN, value)
    path = bundle / f"domain-{domain_number}.json"
    path.write_bytes(module.canonical(value) + b"\n")
    signature = path.with_suffix(path.suffix + ".sig")
    if signature.exists():
        signature.unlink()
    result = subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", module.SIGNATURE_NAMESPACE, str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    assert result.returncode == 0 and signature.is_file()


def rejected_packet(base: dict, mutate) -> None:  # noqa: ANN001
    candidate = copy.deepcopy(base)
    mutate(candidate)
    candidate.pop("attestation_sha256", None)
    candidate["attestation_sha256"] = module.domain_digest(module.ATTESTATION_DOMAIN, candidate)
    try:
        module.validate_attestation_packet(candidate, SOURCE_COMMIT, NOW + timedelta(minutes=1))
    except module.SafeFailure:
        return
    raise AssertionError("unsafe packet mutation admitted after digest recomputation")


def rejected_set(base: list[dict], mutate) -> None:  # noqa: ANN001
    candidate = copy.deepcopy(base)
    mutate(candidate)
    try:
        module.validate_attestation_set(candidate, contract)
    except module.SafeFailure:
        return
    raise AssertionError("unsafe attestation-set mutation admitted")


ssh_keygen = shutil.which("ssh-keygen")
assert ssh_keygen is not None
with tempfile.TemporaryDirectory(prefix="t22-a1-attestation-kat-") as directory:
    bundle = Path(directory)
    bundle.chmod(0o700)
    keys = []
    for number in (1, 2, 3):
        key = bundle.parent / f"{bundle.name}-key-{number}"
        subprocess.run([ssh_keygen, "-q", "-t", "ed25519", "-N", "", "-C", "T22_A1_SYNTHETIC_ONLY", "-f", str(key)], check=True)
        keys.append(key)
        shutil.copyfile(str(key) + ".pub", bundle / f"domain-{number}.pub")
    packets = [packet(number, bundle / f"domain-{number}.pub") for number in (1, 2, 3)]
    for number, (value, key) in enumerate(zip(packets, keys), start=1):
        rewrite_and_sign(bundle, number, value, key)

    receipt = module.verify_bundle(bundle.resolve(), SOURCE_COMMIT, NOW + timedelta(minutes=1))
    assert receipt["status"] == "THREE_DOMAIN_INPUT_SET_COMPLETE_PENDING_OWNER_COUNTERSIGNATURE_NON_EXECUTING"
    assert receipt["set_validation"]["domain_count"] == 3
    assert receipt["set_validation"]["distinct_machine_identity_count"] == 3
    assert receipt["set_validation"]["distinct_hardware_identity_count"] == 3
    assert receipt["set_validation"]["distinct_domain_signing_key_count"] == 3
    assert receipt["owner_countersignature_verified"] is False
    assert receipt["execution_authorized"] is False
    assert receipt["network_accessed"] is False
    unsigned_receipt = dict(receipt)
    claimed_receipt_sha256 = unsigned_receipt.pop("content_sha256")
    assert claimed_receipt_sha256 == module.domain_digest(module.SET_RECEIPT_DOMAIN, unsigned_receipt)
    assert receipt["earliest_attestation_expires_at"] == packets[0]["expires_at"]

    packet_mutations = (
        lambda x: x.update(schema="other"),
        lambda x: x["hashing_contract"].update(candidate_reported_matches_authoritative=True),
        lambda x: x.update(domain_id="domain-4"),
        lambda x: x.update(source_commit="b" * 40),
        lambda x: x["host_identity"].update(logical_aliases=["tb14", "aio2"]),
        lambda x: x["host_identity"].update(physical_host_asserted=False),
        lambda x: x["host_identity"].update(provider_identity_sha256=digest("forbidden-provider")),
        lambda x: x["operator_binding"].update(private_key_exported=True),
        lambda x: x["network_binding"].update(public_listener_allowed=True),
        lambda x: x["network_binding"].update(credential_material_embedded=True),
        lambda x: x["workload_readiness"].update(tracked_tree_clean=False),
        lambda x: x["workload_readiness"].update(ambient_credentials_required=True),
        lambda x: x["claims"].update(site_or_power_independence_proved=True),
        lambda x: x["claims"].update(production_admissible=True),
        lambda x: x["claims"].update(attestation_is_execution_authority=True),
        lambda x: x.update(unexpected="field"),
    )
    for mutation in packet_mutations:
        rejected_packet(packets[0], mutation)

    expired = copy.deepcopy(packets[0])
    expired["expires_at"] = (NOW - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    rejected_packet(expired, lambda x: None)
    long_lived = copy.deepcopy(packets[0])
    long_lived["expires_at"] = (NOW + timedelta(hours=5)).isoformat().replace("+00:00", "Z")
    rejected_packet(long_lived, lambda x: None)

    set_mutations = (
        lambda x: x[1]["host_identity"].update(machine_id_sha256=x[0]["host_identity"]["machine_id_sha256"]),
        lambda x: x[1]["host_identity"].update(hardware_identity_sha256=x[0]["host_identity"]["hardware_identity_sha256"]),
        lambda x: x[1]["host_identity"].update(hostname=x[0]["host_identity"]["hostname"]),
        lambda x: x[1]["operator_binding"].update(public_key_sha256=x[0]["operator_binding"]["public_key_sha256"]),
        lambda x: x[1]["host_identity"].update(logical_aliases=["maxiaodeMac-Pro.local", "tb14"]),
        lambda x: x[1]["host_identity"].update(logical_aliases=["aio2", "maxiaodeMac-Pro.local"]),
        lambda x: x[1]["network_binding"].update(peer_endpoint_set_sha256=digest("other-endpoints")),
        lambda x: x[1]["network_binding"].update(acl_policy_receipt_sha256=digest("other-acl")),
        lambda x: x[2].update(attested_at=(NOW + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")),
        lambda x: x.pop(),
    )
    for mutation in set_mutations:
        rejected_set(packets, mutation)

    packet_raw = (bundle / "domain-1.json").read_bytes()
    try:
        module.verify_detached_signature(
            packet_raw, bundle / "domain-2.json.sig", bundle / "domain-1.pub",
            "domain-1", packets[0]["operator_binding"]["public_key_sha256"],
        )
    except module.SafeFailure as error:
        assert str(error) == "E_DOMAIN_SIGNATURE_INVALID"
    else:
        raise AssertionError("wrong detached signature admitted")

    extra = bundle / "unexpected"
    extra.write_text("synthetic")
    try:
        module.verify_bundle(bundle.resolve(), SOURCE_COMMIT, NOW + timedelta(minutes=1))
    except module.SafeFailure as error:
        assert str(error) == "E_ATTESTATION_BUNDLE_FILE_SET"
    else:
        raise AssertionError("bundle with extra file admitted")
    extra.unlink()

    for key in keys:
        Path(key).unlink()
        Path(str(key) + ".pub").unlink()

status = module.status()
assert status["status"] == "BLOCKED_EXACT_THREE_PRIVATE_ATTESTATION_BUNDLE_AND_OWNER_COUNTERSIGNATURE_REQUIRED"
assert status["stable_host_identity_read"] is False
assert status["private_bundle_read"] is False
assert status["credentials_accessed"] is False
assert status["network_accessed"] is False
assert status["external_hosts_contacted"] == status["services_started"] == status["faults_injected"] == 0
assert status["execution_authorized"] is False
assert status["production_admissible"] is False

negative_count = len(packet_mutations) + 2 + len(set_mutations) + 2
print("t22_a1_domain_attestation_check\tpass")
print(f"directed_negative_test_count\t{negative_count}")
print("real_host_identifiers_read\tfalse")
print("network_accessed\tfalse")
print("credentials_accessed\tfalse")
print("external_hosts_contacted\t0")
print("services_started\t0")
print("real_attestation_items_created\t0")
