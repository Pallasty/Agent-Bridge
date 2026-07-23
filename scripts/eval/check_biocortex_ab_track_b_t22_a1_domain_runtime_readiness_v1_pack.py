"""Synthetic KAT for T22-A1 private domain-runtime readiness contracts."""
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
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_runtime_readiness_v1.py"
spec = importlib.util.spec_from_file_location("t22a1domainreadiness", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

SCHEMA = module.load_schema()
ATTESTATION = module.load_attestation_module()
CONTRACT = json.loads((ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-three-domain-admission-contract-v1.json").read_text())
PROPOSAL = json.loads((ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-owner-decision-proposal-v1.json").read_text())
NOW = datetime.now(timezone.utc).replace(microsecond=0)
SOURCE_COMMIT = "a" * 40
RUN_ID = f"t22-a1-{NOW.strftime('%Y%m%dT%H%M%S')}.000000z-123456789abc"


def sha(label: str) -> str:
    return hashlib.sha256(f"T22_A1_DOMAIN_READINESS_KAT:{label}".encode()).hexdigest()


def utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def attestation(number: int, operator_public_key_sha256: str | None = None) -> dict:
    domain_id = f"domain-{number}"
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_attestation.v1",
        "packet_kind": "T22_A1_HOST_DOMAIN_ATTESTATION",
        "hashing_contract": {
            "hash_algorithm": "SHA-256", "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
            "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/domain-attestation/v1",
            "hash_scope": "ENTIRE_PACKET_EXCEPT_ATTESTATION_SHA256", "self_hash_field": "attestation_sha256",
            "self_hash_field_excluded": True, "detached_signature_covers_complete_canonical_packet": True,
            "cross_field_semantic_validation_required": True, "candidate_reported_matches_authoritative": False,
        },
        "source_commit": SOURCE_COMMIT,
        "domain_id": domain_id,
        "attested_at": utc(NOW - timedelta(minutes=1) + timedelta(seconds=number)),
        "expires_at": utc(NOW + timedelta(hours=2)),
        "host_identity": {
            "hostname": f"synthetic-host-{number}",
            "logical_aliases": [f"synthetic-host-{number}"],
            "operating_system": "MACOS" if number == 2 else "LINUX",
            "kernel_release": "synthetic-kernel",
            "architecture": "AARCH64" if number == 2 else "X86_64",
            "machine_id_sha256": sha(f"machine:{number}"),
            "hardware_identity_sha256": sha(f"hardware:{number}"),
            "boot_id_sha256": sha(f"boot:{number}"),
            "physical_host_asserted": True, "provider_kind": "OWNER_PHYSICAL",
            "provider_identity_sha256": None, "region": None, "zone": None,
            "instance_identity_sha256": None,
        },
        "operator_binding": {
            "operator_role": "T22_A1_DOMAIN_OPERATOR",
            "public_key_sha256": operator_public_key_sha256 or sha(f"operator:{number}"),
            "signature_scheme": "OPENSSH_SSHSIG_ED25519",
            "signature_namespace": ATTESTATION.SIGNATURE_NAMESPACE,
            "private_key_exported": False,
        },
        "network_binding": {
            "transport": "OWNER_MANAGED_PRIVATE_OVERLAY",
            "peer_endpoint_set_sha256": sha("peer-endpoint-set"),
            "acl_policy_receipt_sha256": sha("overlay-acl"),
            "public_listener_allowed": False, "credential_material_embedded": False,
        },
        "workload_readiness": {
            "pinned_tool_receipt_sha256": sha(f"tool-receipt:{number}"),
            "private_data_root_sha256": sha(f"private-root:{number}"),
            "port_set_sha256": sha(f"ports:{number}"),
            "tracked_tree_clean": True, "ambient_credentials_required": False,
        },
        "claims": {
            "candidate_for_distinct_physical_host": True,
            "site_or_power_independence_proved": False,
            "production_admissible": False,
            "attestation_is_execution_authority": False,
        },
    }
    value["attestation_sha256"] = ATTESTATION.domain_digest(ATTESTATION.ATTESTATION_DOMAIN, value)
    return value


ENDPOINT = {
    "content_sha256": sha("endpoint-manifest"),
    "domains": [{
        "domain_id": f"domain-{number}", "overlay_ip": f"100.64.30.{number}",
        "agent_control_port": 29000, "etcd_client_port": 2379,
        "etcd_peer_port": 2380, "openbao_api_port": 8200,
        "openbao_cluster_port": 8201,
    } for number in (1, 2, 3)],
}


def credential(identity: str) -> dict:
    return {
        "certificate_sha256": sha(f"certificate:{identity}"),
        "spki_sha256": sha(f"spki:{identity}"),
    }


CREDENTIAL = {
    "content_sha256": sha("credential-manifest"),
    "ca": {"certificate_sha256": sha("ca-certificate")},
    "coordinator": credential("coordinator"),
    "domains": [credential(f"domain-{number}") for number in (1, 2, 3)],
    "coordinator_runtime_signing_key": {"public_key_sha256": sha("coordinator-runtime")},
}
ADMITTED_SET_RECEIPT_SHA256 = sha("admitted-set")
PREPARATION_TERMINAL_SHA256 = sha("preparation-terminal")


def placed_identity(root: Path, prefix: str, credential_row: dict) -> dict:
    return {
        "certificate_path": str(root / f"{prefix}.crt"),
        "private_key_path": str(root / f"{prefix}.key"),
        "certificate_sha256": credential_row["certificate_sha256"],
        "spki_sha256": credential_row["spki_sha256"],
        "private_key_spki_sha256": credential_row["spki_sha256"],
        "private_key_file_mode": "0600",
        "certificate_private_key_match_verified": True,
    }


def readiness(number: int, operator_public_key_sha256: str | None = None) -> tuple[dict, dict]:
    domain_id = f"domain-{number}"
    packet = attestation(number, operator_public_key_sha256)
    domain_root = Path(f"/private/t22-a1/{RUN_ID}/{domain_id}")
    credentials_root = domain_root / "credentials"
    endpoint = ENDPOINT["domains"][number - 1]
    executables = [{
        "name": name,
        "path": f"/private/tools/{domain_id}/{name}",
        "sha256": sha(f"tool:{number}:{name}"),
        "bytes": 1000 + index,
        "executable_by_owner": True,
        "version_output_sha256": sha(f"version:{number}:{name}"),
    } for index, name in enumerate(module.EXECUTABLE_NAMES)]
    coordinator = None
    if number == 1:
        coordinator = {
            "client_identity": placed_identity(credentials_root, "coordinator", CREDENTIAL["coordinator"]),
            "runtime_public_key_path": str(credentials_root / "coordinator-runtime.pub"),
            "runtime_private_key_path": str(credentials_root / "coordinator-runtime"),
            "runtime_public_key_sha256": CREDENTIAL["coordinator_runtime_signing_key"]["public_key_sha256"],
            "runtime_private_key_file_mode": "0600", "runtime_key_pair_verified": True,
        }
    coordinator_trust = {
        "certificate_path": str(credentials_root / "coordinator.crt"),
        "certificate_sha256": CREDENTIAL["coordinator"]["certificate_sha256"],
        "spki_sha256": CREDENTIAL["coordinator"]["spki_sha256"],
        "runtime_public_key_path": str(credentials_root / "coordinator-runtime.pub"),
        "runtime_public_key_sha256": CREDENTIAL["coordinator_runtime_signing_key"]["public_key_sha256"],
    }
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_runtime_readiness.v1",
        "packet_kind": "T22_A1_PRIVATE_DOMAIN_RUNTIME_READINESS",
        "hashing_contract": {
            "hash_algorithm": "SHA-256", "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
            "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/domain-runtime-readiness/v1",
            "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256", "self_hash_field": "content_sha256",
            "self_hash_field_excluded": True, "detached_domain_signature_covers_complete_canonical_packet": True,
            "cross_field_semantic_validation_required": True,
        },
        "run_id": RUN_ID, "source_commit": SOURCE_COMMIT, "domain_id": domain_id,
        "collected_at": utc(NOW), "expires_at": utc(NOW + timedelta(minutes=30)),
        "bindings": {
            "owner_decision_proposal_sha256": PROPOSAL["proposal_sha256"],
            "admission_contract_sha256": CONTRACT["contract_sha256"],
            "domain_attestation_packet_sha256": packet["attestation_sha256"],
            "owner_countersigned_attestation_set_receipt_sha256": ADMITTED_SET_RECEIPT_SHA256,
            "private_endpoint_manifest_content_sha256": ENDPOINT["content_sha256"],
            "runtime_credential_manifest_content_sha256": CREDENTIAL["content_sha256"],
            "runtime_preparation_terminal_receipt_sha256": PREPARATION_TERMINAL_SHA256,
        },
        "host_binding": {
            "hostname": packet["host_identity"]["hostname"],
            "operating_system": packet["host_identity"]["operating_system"],
            "architecture": packet["host_identity"]["architecture"],
            "machine_id_sha256": packet["host_identity"]["machine_id_sha256"],
            "hardware_identity_sha256": packet["host_identity"]["hardware_identity_sha256"],
            "boot_id_sha256": packet["host_identity"]["boot_id_sha256"],
        },
        "endpoint_binding": {
            "overlay_ip": endpoint["overlay_ip"], "agent_control_port": endpoint["agent_control_port"],
            "etcd_client_port": endpoint["etcd_client_port"], "etcd_peer_port": endpoint["etcd_peer_port"],
            "openbao_api_port": endpoint["openbao_api_port"], "openbao_cluster_port": endpoint["openbao_cluster_port"],
            "port_set_sha256": packet["workload_readiness"]["port_set_sha256"],
            "bind_exact_overlay_ip_only": True, "public_listener_allowed": False,
        },
        "toolchain": {
            "pinned_tool_receipt_path": f"/private/tools/{domain_id}/pinned-tool-receipt.json",
            "pinned_tool_receipt_sha256": packet["workload_readiness"]["pinned_tool_receipt_sha256"],
            "executables": executables, "all_paths_absolute": True,
            "all_hashes_recomputed_locally": True, "ambient_path_lookup_allowed": False,
        },
        "local_paths": {
            "domain_private_root": str(domain_root),
            "private_data_root_sha256": packet["workload_readiness"]["private_data_root_sha256"],
            "etcd_data_dir": str(domain_root / "etcd"), "openbao_data_dir": str(domain_root / "openbao"),
            "owned_logs_dir": str(domain_root / "logs"), "domain_evidence_dir": str(domain_root / "evidence"),
            "execution_reservation_dir": str(domain_root / "execution-reservations"),
            "all_paths_outside_repository": True, "directory_mode": "0700",
        },
        "credential_placement": {
            "mode": "OWNER_MEDIATED_OUT_OF_BAND_EXACT_HASH_PLACEMENT",
            "ca_certificate_path": str(credentials_root / "ca.crt"),
            "ca_certificate_sha256": CREDENTIAL["ca"]["certificate_sha256"],
            "domain_identity": placed_identity(credentials_root, "domain", CREDENTIAL["domains"][number - 1]),
            "domain_operator_public_key_path": str(credentials_root / "domain-operator.pub"),
            "domain_operator_private_key_path": str(credentials_root / "domain-operator"),
            "domain_operator_public_key_sha256": packet["operator_binding"]["public_key_sha256"],
            "domain_operator_private_key_file_mode": "0600",
            "coordinator_trust_material": coordinator_trust,
            "coordinator_material": coordinator,
            "all_paths_local_to_attested_host": True,
            "certificate_chain_eku_san_expiry_verified": True,
            "private_key_redistribution_after_initial_placement_allowed": False,
        },
        "process_policy": {
            "fixed_protocol_command_enum_only": True, "arbitrary_command_or_shell_allowed": False,
            "shell_evaluation_allowed": False, "ambient_credentials_allowed": False,
            "proxy_environment_inherited": False, "host_global_network_mutation_allowed": False,
            "host_reboot_or_power_action_allowed": False, "owned_process_and_run_root_scope_required": True,
        },
        "signature_binding": {
            "signer_role": "T22_A1_DOMAIN_OPERATOR",
            "signer_public_key_sha256": packet["operator_binding"]["public_key_sha256"],
            "signature_scheme": "OPENSSH_SSHSIG_ED25519", "signature_namespace": module.SIGNATURE_NAMESPACE,
            "detached_signature_required": True, "signature_embedded": False,
        },
        "collection_effects": {
            "network_accessed": False, "external_hosts_contacted": 0,
            "listeners_started": 0, "services_started": 0,
            "faults_injected": 0, "spend_usd_cents": 0,
        },
        "claims": {
            "readiness_is_execution_authority": False,
            "credential_placement_proved_for_this_host": True,
            "three_domain_execution_proved": False, "production_admissible": False,
        },
    }
    value["content_sha256"] = module.digest(value)
    return value, packet


def write_and_sign(path: Path, value: dict, private_key: Path, namespace: str) -> None:
    path.write_bytes(module.canonical(value) + b"\n")
    path.chmod(0o600)
    signature = path.with_suffix(path.suffix + ".sig")
    if signature.exists() or signature.is_symlink():
        signature.unlink()
    result = subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(private_key), "-n", namespace, str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    assert result.returncode == 0 and signature.is_file()
    signature.chmod(0o600)


positive: list[tuple[dict, dict]] = []
for number in (1, 2, 3):
    value, packet = readiness(number)
    assert module.validate_readiness(
        value, SCHEMA, SOURCE_COMMIT, RUN_ID, f"domain-{number}", CONTRACT,
        PROPOSAL, packet, ADMITTED_SET_RECEIPT_SHA256, ENDPOINT, CREDENTIAL,
        PREPARATION_TERMINAL_SHA256, NOW + timedelta(seconds=1),
    ) == value
    positive.append((value, packet))


def rejected(base: dict, packet: dict, mutation, domain_id: str = "domain-1", now: datetime | None = None, recalc: bool = True) -> None:  # noqa: ANN001
    candidate = copy.deepcopy(base)
    mutation(candidate)
    if recalc:
        candidate.pop("content_sha256", None)
        candidate["content_sha256"] = module.digest(candidate)
    try:
        module.validate_readiness(
            candidate, SCHEMA, SOURCE_COMMIT, RUN_ID, domain_id, CONTRACT,
            PROPOSAL, packet, ADMITTED_SET_RECEIPT_SHA256, ENDPOINT, CREDENTIAL,
            PREPARATION_TERMINAL_SHA256, now or NOW + timedelta(seconds=1),
        )
    except module.SafeFailure:
        return
    raise AssertionError("unsafe domain runtime readiness mutation admitted")


base, packet = positive[0]
mutations = (
    lambda x: x.update(source_commit="b" * 40),
    lambda x: x.update(domain_id="domain-2"),
    lambda x: x.update(collected_at=utc(NOW - timedelta(minutes=2))),
    lambda x: x.update(expires_at=utc(NOW + timedelta(hours=2))),
    lambda x: x["bindings"].update(owner_decision_proposal_sha256=sha("wrong-proposal")),
    lambda x: x["bindings"].update(admission_contract_sha256=sha("wrong-contract")),
    lambda x: x["bindings"].update(domain_attestation_packet_sha256=sha("wrong-attestation")),
    lambda x: x["bindings"].update(owner_countersigned_attestation_set_receipt_sha256=sha("wrong-set")),
    lambda x: x["bindings"].update(private_endpoint_manifest_content_sha256=sha("wrong-endpoint")),
    lambda x: x["bindings"].update(runtime_credential_manifest_content_sha256=sha("wrong-credential")),
    lambda x: x["bindings"].update(runtime_preparation_terminal_receipt_sha256=sha("wrong-preparation")),
    lambda x: x["host_binding"].update(hostname="other-host"),
    lambda x: x["host_binding"].update(machine_id_sha256=sha("wrong-machine")),
    lambda x: x["endpoint_binding"].update(overlay_ip="100.64.30.2"),
    lambda x: x["endpoint_binding"].update(agent_control_port=29001),
    lambda x: x["endpoint_binding"].update(port_set_sha256=sha("wrong-ports")),
    lambda x: x["endpoint_binding"].update(public_listener_allowed=True),
    lambda x: x["toolchain"].update(pinned_tool_receipt_sha256=sha("wrong-tools")),
    lambda x: x["toolchain"]["executables"].reverse(),
    lambda x: x["toolchain"]["executables"][0].update(path="relative/python3"),
    lambda x: x["toolchain"]["executables"][1].update(path=x["toolchain"]["executables"][0]["path"]),
    lambda x: x["toolchain"]["executables"][1].update(sha256=x["toolchain"]["executables"][0]["sha256"]),
    lambda x: x["toolchain"]["executables"][0].update(path=str(ROOT / "python3")),
    lambda x: x["local_paths"].update(domain_private_root=str(ROOT / "private")),
    lambda x: x["local_paths"].update(private_data_root_sha256=sha("wrong-root")),
    lambda x: x["local_paths"].update(etcd_data_dir="/private/other/etcd"),
    lambda x: x["credential_placement"].update(ca_certificate_sha256=sha("wrong-ca")),
    lambda x: x["credential_placement"]["domain_identity"].update(certificate_sha256=sha("wrong-cert")),
    lambda x: x["credential_placement"]["domain_identity"].update(private_key_spki_sha256=sha("wrong-key")),
    lambda x: x["credential_placement"].update(domain_operator_public_key_sha256=sha("wrong-operator")),
    lambda x: x["credential_placement"].update(domain_operator_private_key_path=x["credential_placement"]["domain_operator_public_key_path"]),
    lambda x: x["credential_placement"]["coordinator_trust_material"].update(certificate_sha256=sha("wrong-coordinator-cert")),
    lambda x: x["credential_placement"]["coordinator_trust_material"].update(runtime_public_key_sha256=sha("wrong-coordinator-runtime")),
    lambda x: x["credential_placement"].update(coordinator_material=None),
    lambda x: x["credential_placement"].update(private_key_redistribution_after_initial_placement_allowed=True),
    lambda x: x["process_policy"].update(arbitrary_command_or_shell_allowed=True),
    lambda x: x["process_policy"].update(proxy_environment_inherited=True),
    lambda x: x["signature_binding"].update(signer_public_key_sha256=sha("wrong-signer")),
    lambda x: x["signature_binding"].update(signature_namespace="agent-bridge-t22-a1-domain-message-v1"),
    lambda x: x["collection_effects"].update(network_accessed=True),
    lambda x: x["collection_effects"].update(services_started=1),
    lambda x: x["claims"].update(readiness_is_execution_authority=True),
    lambda x: x["claims"].update(production_admissible=True),
    lambda x: x.update(unexpected="field"),
)
for mutation in mutations:
    rejected(base, packet, mutation)

domain_two, packet_two = positive[1]
rejected(domain_two, packet_two, lambda x: x["credential_placement"].update(coordinator_material=copy.deepcopy(base["credential_placement"]["coordinator_material"])), domain_id="domain-2")
rejected(base, packet, lambda x: x.update(expires_at=utc(NOW + timedelta(seconds=1))), now=NOW + timedelta(seconds=2))
rejected(base, packet, lambda x: x.update(content_sha256=sha("forged-digest")), recalc=False)

ssh_keygen = shutil.which("ssh-keygen")
assert ssh_keygen is not None
bundle_negative_count = 0
with tempfile.TemporaryDirectory(prefix="t22-a1-readiness-set-kat-") as directory:
    root = Path(directory)
    attestation_bundle = root / "attestations"
    readiness_bundle = root / "readiness"
    attestation_bundle.mkdir(mode=0o700)
    readiness_bundle.mkdir(mode=0o700)
    keys: list[Path] = []
    signed_readiness: list[dict] = []
    for number in (1, 2, 3):
        key = root / f"domain-{number}-operator"
        subprocess.run(
            [ssh_keygen, "-q", "-t", "ed25519", "-N", "", "-C", "T22_A1_READINESS_SYNTHETIC_ONLY", "-f", str(key)],
            check=True,
        )
        keys.append(key)
        public_key_path = attestation_bundle / f"domain-{number}.pub"
        shutil.copyfile(str(key) + ".pub", public_key_path)
        operator_sha256 = ATTESTATION.canonical_public_key(public_key_path)[1]
        readiness_value, attestation_value = readiness(number, operator_sha256)
        signed_readiness.append(readiness_value)
        write_and_sign(
            attestation_bundle / f"domain-{number}.json", attestation_value, key,
            ATTESTATION.SIGNATURE_NAMESPACE,
        )
        write_and_sign(
            readiness_bundle / f"domain-{number}.json", readiness_value, key,
            module.SIGNATURE_NAMESPACE,
        )

    def verify_readiness_set(endpoint_manifest: dict = ENDPOINT, now: datetime = NOW + timedelta(seconds=1)) -> dict:
        return module.verify_bundle(
            readiness_bundle.resolve(), attestation_bundle.resolve(), SOURCE_COMMIT, RUN_ID,
            CONTRACT, PROPOSAL, ADMITTED_SET_RECEIPT_SHA256, endpoint_manifest,
            CREDENTIAL, PREPARATION_TERMINAL_SHA256, now,
        )

    def expect_bundle_failure(expected: str, endpoint_manifest: dict = ENDPOINT, now: datetime = NOW + timedelta(seconds=1)) -> None:
        try:
            verify_readiness_set(endpoint_manifest, now)
        except module.SafeFailure as error:
            assert str(error) == expected, (str(error), expected)
            return
        raise AssertionError(f"unsafe readiness bundle admitted: {expected}")

    receipt = verify_readiness_set()
    assert receipt["status"] == "THREE_DOMAIN_RUNTIME_READINESS_SET_VERIFIED_NON_EXECUTING"
    assert [row["domain_id"] for row in receipt["packet_bindings"]] == list(module.DOMAIN_IDS)
    assert [row["domain_id"] for row in receipt["signature_bindings"]] == list(module.DOMAIN_IDS)
    assert receipt["all_three_packets_current"] is True
    assert receipt["all_three_domain_signatures_verified"] is True
    assert receipt["same_attested_domain_keys_reverified"] is True
    assert receipt["credential_files_accessed"] == receipt["external_hosts_contacted"] == 0
    assert receipt["network_accessed"] is False and receipt["execution_authorized"] is False
    assert receipt["production_admissible"] is False
    unsigned_receipt = dict(receipt)
    claimed_receipt_sha256 = unsigned_receipt.pop("content_sha256")
    assert claimed_receipt_sha256 == module.domain_digest(module.READINESS_SET_RECEIPT_DOMAIN, unsigned_receipt)

    unexpected = readiness_bundle / "unexpected"
    unexpected.write_text("synthetic")
    expect_bundle_failure("E_READINESS_BUNDLE_FILE_SET")
    unexpected.unlink()
    bundle_negative_count += 1

    signature_path = readiness_bundle / "domain-1.json.sig"
    signature_raw = signature_path.read_bytes()
    signature_path.unlink()
    expect_bundle_failure("E_READINESS_BUNDLE_FILE_SET")
    signature_path.write_bytes(signature_raw)
    signature_path.chmod(0o600)
    bundle_negative_count += 1

    signature_path.unlink()
    write_and_sign(
        readiness_bundle / "domain-1.json", signed_readiness[0], keys[0],
        "agent-bridge-t22-a1-wrong-readiness-v1",
    )
    expect_bundle_failure("E_READINESS_SIGNATURE_INVALID")
    write_and_sign(
        readiness_bundle / "domain-1.json", signed_readiness[0], keys[0],
        module.SIGNATURE_NAMESPACE,
    )
    bundle_negative_count += 1

    wrong_endpoint = copy.deepcopy(ENDPOINT)
    wrong_endpoint["content_sha256"] = sha("wrong-endpoint-manifest")
    expect_bundle_failure("E_READINESS_EVIDENCE_BINDINGS", wrong_endpoint)
    bundle_negative_count += 1

    domain_one_packet = readiness_bundle / "domain-1.json"
    domain_two_packet = readiness_bundle / "domain-2.json"
    domain_one_signature = readiness_bundle / "domain-1.json.sig"
    domain_two_signature = readiness_bundle / "domain-2.json.sig"
    one_raw, two_raw = domain_one_packet.read_bytes(), domain_two_packet.read_bytes()
    one_sig, two_sig = domain_one_signature.read_bytes(), domain_two_signature.read_bytes()
    domain_one_packet.write_bytes(two_raw)
    domain_two_packet.write_bytes(one_raw)
    domain_one_signature.write_bytes(two_sig)
    domain_two_signature.write_bytes(one_sig)
    for path in (domain_one_packet, domain_two_packet, domain_one_signature, domain_two_signature):
        path.chmod(0o600)
    expect_bundle_failure("E_READINESS_RUN_BINDING")
    domain_one_packet.write_bytes(one_raw)
    domain_two_packet.write_bytes(two_raw)
    domain_one_signature.write_bytes(one_sig)
    domain_two_signature.write_bytes(two_sig)
    for path in (domain_one_packet, domain_two_packet, domain_one_signature, domain_two_signature):
        path.chmod(0o600)
    bundle_negative_count += 1

    domain_one_public_key = attestation_bundle / "domain-1.pub"
    public_key_raw = domain_one_public_key.read_bytes()
    domain_one_public_key.write_bytes((attestation_bundle / "domain-2.pub").read_bytes())
    expect_bundle_failure("E_DOMAIN_PUBLIC_KEY_BINDING")
    domain_one_public_key.write_bytes(public_key_raw)
    bundle_negative_count += 1

    spread_packet = copy.deepcopy(signed_readiness[2])
    spread_packet["collected_at"] = utc(NOW + timedelta(minutes=6))
    spread_packet["expires_at"] = utc(NOW + timedelta(minutes=36))
    spread_packet.pop("content_sha256")
    spread_packet["content_sha256"] = module.digest(spread_packet)
    write_and_sign(
        readiness_bundle / "domain-3.json", spread_packet, keys[2], module.SIGNATURE_NAMESPACE,
    )
    expect_bundle_failure("E_READINESS_SET_CLOCK_SPREAD", now=NOW + timedelta(minutes=7))
    write_and_sign(
        readiness_bundle / "domain-3.json", signed_readiness[2], keys[2], module.SIGNATURE_NAMESPACE,
    )
    bundle_negative_count += 1

status = module.status()
assert status["status"] == "OFFLINE_DOMAIN_RUNTIME_READINESS_CONTRACT_AND_SET_VERIFIER_READY_REAL_PACKET_COLLECTION_BLOCKED"
assert status["real_packet_instances_read"] == status["real_tool_or_credential_files_read"] == 0
assert status["real_host_identifiers_read"] is False and status["network_accessed"] is False
assert status["external_hosts_contacted"] == status["listeners_started"] == status["services_started"] == status["faults_injected"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

negative_count = len(mutations) + 3 + bundle_negative_count
print("t22_a1_domain_runtime_readiness_check\tpass")
print("synthetic_valid_domain_packet_count\t3")
print("synthetic_valid_signed_readiness_set_count\t1")
print(f"directed_negative_test_count\t{negative_count}")
print("real_packet_instances_read\t0")
print("real_host_identifiers_read\tfalse")
print("real_tool_or_credential_files_read\t0")
print("network_accessed\tfalse")
print("external_hosts_contacted\t0")
print("listeners_started\t0")
print("services_started\t0")
print("faults_injected\t0")
print("production_admissible\tfalse")
