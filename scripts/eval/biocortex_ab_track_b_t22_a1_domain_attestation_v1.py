"""Offline verifier for a private T22-A1 three-domain attestation bundle.

`status` never reads host identifiers, packet bundles, keys, credentials, or
network state. `verify-set` validates an already-provided private directory and
detached SSHSIG signatures; it creates no authority and starts no service.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_three_domain_preflight_v1.py"
ATTESTATION_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-attestation/v1\0"
SET_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-attestation-set/v1\0"
SET_RECEIPT_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-attestation-set-verification-receipt/v1\0"
SIGNATURE_NAMESPACE = "agent-bridge-t22-a1-domain-v1"
MAX_PACKET_BYTES = 64 * 1024
MAX_KEY_BYTES = 16 * 1024
MAX_SIGNATURE_BYTES = 64 * 1024
HEX64 = re.compile(r"^[0-9a-f]{64}$")
OID40 = re.compile(r"^[0-9a-f]{40}$")


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def load_preflight_module():
    spec = importlib.util.spec_from_file_location("t22a1_preflight", PREFLIGHT_SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def domain_digest(domain: bytes, value: object) -> str:
    return hashlib.sha256(domain + canonical(value)).hexdigest()


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(HEX64.fullmatch(value)) and value != "0" * 64


def exact_keys(value: object, keys: set[str], code: str) -> dict:
    require(isinstance(value, dict) and set(value) == keys, code)
    return value


def parse_time(value: object, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise SafeFailure(code) from error
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0, code)
    return parsed


def read_bounded_regular(path: Path, maximum: int, code: str) -> bytes:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), code)
    mode = path.stat().st_mode
    require(stat.S_ISREG(mode) and path.stat().st_size <= maximum, code)
    return path.read_bytes()


def parse_canonical_packet(path: Path) -> tuple[dict, bytes]:
    raw = read_bounded_regular(path, MAX_PACKET_BYTES, "E_ATTESTATION_PACKET_FILE")
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "E_ATTESTATION_PACKET_FRAMING")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SafeFailure("E_ATTESTATION_PACKET_JSON") from error
    require(raw == canonical(value) + b"\n", "E_ATTESTATION_PACKET_NOT_CANONICAL")
    return value, raw


def validate_attestation_packet(value: dict, expected_source_commit: str, now: datetime) -> dict:
    require(now.tzinfo is not None and now.utcoffset().total_seconds() == 0, "E_VALIDATION_TIME")
    exact_keys(value, {
        "schema", "packet_kind", "hashing_contract", "domain_id", "attested_at",
        "expires_at", "source_commit", "host_identity", "operator_binding",
        "network_binding", "workload_readiness", "claims", "attestation_sha256",
    }, "E_ATTESTATION_SHAPE")
    require(value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.domain_attestation.v1", "E_ATTESTATION_SCHEMA")
    require(value["packet_kind"] == "T22_A1_HOST_DOMAIN_ATTESTATION", "E_ATTESTATION_KIND")
    require(value["hashing_contract"] == {
        "hash_algorithm": "SHA-256",
        "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
        "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/domain-attestation/v1",
        "hash_scope": "ENTIRE_PACKET_EXCEPT_ATTESTATION_SHA256",
        "self_hash_field": "attestation_sha256",
        "self_hash_field_excluded": True,
        "detached_signature_covers_complete_canonical_packet": True,
        "cross_field_semantic_validation_required": True,
        "candidate_reported_matches_authoritative": False,
    }, "E_ATTESTATION_HASHING_CONTRACT")
    require(value["domain_id"] in {"domain-1", "domain-2", "domain-3"}, "E_ATTESTATION_DOMAIN_ID")
    issued = parse_time(value["attested_at"], "E_ATTESTATION_ISSUED_AT")
    expires = parse_time(value["expires_at"], "E_ATTESTATION_EXPIRES_AT")
    require(issued <= now <= expires, "E_ATTESTATION_NOT_CURRENT")
    require(0 < (expires - issued).total_seconds() <= 14400, "E_ATTESTATION_LIFETIME")
    require((now - issued).total_seconds() <= 14400, "E_ATTESTATION_TOO_OLD")
    require(isinstance(expected_source_commit, str) and OID40.fullmatch(expected_source_commit), "E_EXPECTED_SOURCE_COMMIT")
    require(value["source_commit"] == expected_source_commit, "E_ATTESTATION_SOURCE_BINDING")

    host = exact_keys(value["host_identity"], {
        "hostname", "logical_aliases", "operating_system", "kernel_release",
        "architecture", "machine_id_sha256", "hardware_identity_sha256",
        "boot_id_sha256", "physical_host_asserted", "provider_kind",
        "provider_identity_sha256", "region", "zone", "instance_identity_sha256",
    }, "E_ATTESTATION_HOST_SHAPE")
    require(isinstance(host["hostname"], str) and 1 <= len(host["hostname"]) <= 255, "E_ATTESTATION_HOSTNAME")
    aliases = host["logical_aliases"]
    require(isinstance(aliases, list) and 1 <= len(aliases) <= 8, "E_ATTESTATION_ALIASES")
    require(all(isinstance(alias, str) and 1 <= len(alias) <= 64 for alias in aliases), "E_ATTESTATION_ALIASES")
    require(aliases == sorted(set(aliases)) and host["hostname"] in aliases, "E_ATTESTATION_ALIASES")
    require(host["operating_system"] in {"LINUX", "MACOS"}, "E_ATTESTATION_OS")
    require(isinstance(host["kernel_release"], str) and 1 <= len(host["kernel_release"]) <= 128, "E_ATTESTATION_KERNEL")
    require(host["architecture"] in {"X86_64", "AARCH64"}, "E_ATTESTATION_ARCH")
    for field in ("machine_id_sha256", "hardware_identity_sha256", "boot_id_sha256"):
        require(is_sha256(host[field]), f"E_ATTESTATION_{field.upper()}")
    require(host["physical_host_asserted"] is True, "E_ATTESTATION_PHYSICAL_HOST")
    require(host["provider_kind"] in {"OWNER_PHYSICAL", "CLOUD_VM"}, "E_ATTESTATION_PROVIDER_KIND")
    if host["provider_kind"] == "OWNER_PHYSICAL":
        require(all(host[field] is None for field in ("provider_identity_sha256", "region", "zone", "instance_identity_sha256")), "E_ATTESTATION_OWNER_PHYSICAL_FIELDS")
    else:
        require(is_sha256(host["provider_identity_sha256"]), "E_ATTESTATION_PROVIDER_IDENTITY")
        require(is_sha256(host["instance_identity_sha256"]), "E_ATTESTATION_INSTANCE_IDENTITY")
        require(isinstance(host["region"], str) and 1 <= len(host["region"]) <= 128, "E_ATTESTATION_REGION")
        require(isinstance(host["zone"], str) and 1 <= len(host["zone"]) <= 128, "E_ATTESTATION_ZONE")

    operator = exact_keys(value["operator_binding"], {
        "operator_role", "public_key_sha256", "signature_scheme",
        "signature_namespace", "private_key_exported",
    }, "E_ATTESTATION_OPERATOR_SHAPE")
    require(operator == {
        "operator_role": "T22_A1_DOMAIN_OPERATOR",
        "public_key_sha256": operator["public_key_sha256"],
        "signature_scheme": "OPENSSH_SSHSIG_ED25519",
        "signature_namespace": SIGNATURE_NAMESPACE,
        "private_key_exported": False,
    } and is_sha256(operator["public_key_sha256"]), "E_ATTESTATION_OPERATOR_BINDING")

    network = exact_keys(value["network_binding"], {
        "transport", "peer_endpoint_set_sha256", "acl_policy_receipt_sha256",
        "public_listener_allowed", "credential_material_embedded",
    }, "E_ATTESTATION_NETWORK_SHAPE")
    require(network["transport"] == "OWNER_MANAGED_PRIVATE_OVERLAY", "E_ATTESTATION_TRANSPORT")
    require(is_sha256(network["peer_endpoint_set_sha256"]) and is_sha256(network["acl_policy_receipt_sha256"]), "E_ATTESTATION_NETWORK_DIGEST")
    require(network["public_listener_allowed"] is False, "E_ATTESTATION_PUBLIC_LISTENER")
    require(network["credential_material_embedded"] is False, "E_ATTESTATION_EMBEDDED_CREDENTIAL")

    workload = exact_keys(value["workload_readiness"], {
        "pinned_tool_receipt_sha256", "private_data_root_sha256", "port_set_sha256",
        "tracked_tree_clean", "ambient_credentials_required",
    }, "E_ATTESTATION_WORKLOAD_SHAPE")
    require(all(is_sha256(workload[field]) for field in ("pinned_tool_receipt_sha256", "private_data_root_sha256", "port_set_sha256")), "E_ATTESTATION_WORKLOAD_DIGEST")
    require(workload["tracked_tree_clean"] is True, "E_ATTESTATION_TRACKED_TREE")
    require(workload["ambient_credentials_required"] is False, "E_ATTESTATION_AMBIENT_CREDENTIAL")
    require(value["claims"] == {
        "candidate_for_distinct_physical_host": True,
        "site_or_power_independence_proved": False,
        "production_admissible": False,
        "attestation_is_execution_authority": False,
    }, "E_ATTESTATION_CLAIMS")
    unsigned = dict(value)
    claimed = unsigned.pop("attestation_sha256", None)
    require(is_sha256(claimed) and claimed == domain_digest(ATTESTATION_DOMAIN, unsigned), "E_ATTESTATION_DIGEST")
    return value


def canonical_public_key(path: Path) -> tuple[bytes, str]:
    raw = read_bounded_regular(path, MAX_KEY_BYTES, "E_DOMAIN_PUBLIC_KEY_FILE")
    try:
        fields = raw.decode("ascii").strip().split()
    except UnicodeDecodeError as error:
        raise SafeFailure("E_DOMAIN_PUBLIC_KEY_FORMAT") from error
    require(len(fields) >= 2 and fields[0] == "ssh-ed25519", "E_DOMAIN_PUBLIC_KEY_FORMAT")
    canonical_key = f"{fields[0]} {fields[1]}\n".encode()
    return canonical_key, hashlib.sha256(canonical_key).hexdigest()


def verify_detached_signature(packet_raw: bytes, signature_path: Path, public_key_path: Path, domain_id: str, expected_public_key_sha256: str) -> dict:
    signature = read_bounded_regular(signature_path, MAX_SIGNATURE_BYTES, "E_DOMAIN_SIGNATURE_FILE")
    public_key, public_key_sha256 = canonical_public_key(public_key_path)
    require(public_key_sha256 == expected_public_key_sha256, "E_DOMAIN_PUBLIC_KEY_BINDING")
    ssh_keygen = shutil.which("ssh-keygen")
    require(ssh_keygen is not None, "E_SSH_KEYGEN_MISSING")
    with tempfile.TemporaryDirectory(prefix="t22-a1-verify-") as directory:
        allowed = Path(directory) / "allowed_signers"
        allowed.write_bytes(domain_id.encode() + b" " + public_key)
        allowed.chmod(0o600)
        result = subprocess.run(
            [ssh_keygen, "-Y", "verify", "-f", str(allowed), "-I", domain_id,
             "-n", SIGNATURE_NAMESPACE, "-s", str(signature_path)],
            input=packet_raw,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C", "LC_ALL": "C"},
            check=False,
        )
    require(result.returncode == 0, "E_DOMAIN_SIGNATURE_INVALID")
    return {
        "public_key_sha256": public_key_sha256,
        "signature_sha256": hashlib.sha256(signature).hexdigest(),
    }


def validate_attestation_set(packets: list[dict], contract: dict) -> dict:
    require(len(packets) == 3, "E_ATTESTATION_SET_CARDINALITY")
    require({packet["domain_id"] for packet in packets} == {"domain-1", "domain-2", "domain-3"}, "E_ATTESTATION_SET_DOMAIN_IDS")
    for field in ("machine_id_sha256", "hardware_identity_sha256"):
        require(len({packet["host_identity"][field] for packet in packets}) == 3, f"E_ATTESTATION_SET_DUPLICATE_{field.upper()}")
    require(len({packet["host_identity"]["hostname"] for packet in packets}) == 3, "E_ATTESTATION_SET_DUPLICATE_HOSTNAME")
    require(len({packet["operator_binding"]["public_key_sha256"] for packet in packets}) == 3, "E_ATTESTATION_SET_DUPLICATE_SIGNING_KEY")
    alias_sets = [set(packet["host_identity"]["logical_aliases"]) for packet in packets]
    for index, aliases in enumerate(alias_sets):
        for other in alias_sets[index + 1:]:
            require(aliases.isdisjoint(other), "E_ATTESTATION_SET_ALIAS_OVERLAP")
    for equivalence_class in contract["domain_admission"]["known_alias_equivalence_classes"]:
        membership = [bool(set(equivalence_class) & aliases) for aliases in alias_sets]
        require(sum(membership) <= 1, "E_ATTESTATION_SET_KNOWN_ALIAS_SPLIT")
    require(len({packet["network_binding"]["peer_endpoint_set_sha256"] for packet in packets}) == 1, "E_ATTESTATION_SET_ENDPOINT_BINDING")
    require(len({packet["network_binding"]["acl_policy_receipt_sha256"] for packet in packets}) == 1, "E_ATTESTATION_SET_ACL_BINDING")
    issued = [parse_time(packet["attested_at"], "E_ATTESTATION_ISSUED_AT") for packet in packets]
    spread = int((max(issued) - min(issued)).total_seconds())
    require(spread <= contract["evidence"]["maximum_attestation_time_spread_seconds"], "E_ATTESTATION_SET_CLOCK_SPREAD")
    return {
        "domain_count": 3,
        "distinct_machine_identity_count": 3,
        "distinct_hardware_identity_count": 3,
        "distinct_hostname_count": 3,
        "distinct_domain_signing_key_count": 3,
        "maximum_attestation_time_spread_seconds": spread,
        "peer_endpoint_set_sha256": packets[0]["network_binding"]["peer_endpoint_set_sha256"],
        "acl_policy_receipt_sha256": packets[0]["network_binding"]["acl_policy_receipt_sha256"],
    }


def verify_bundle(bundle: Path, source_commit: str, now: datetime) -> dict:
    require(bundle.is_absolute() and bundle.is_dir() and not bundle.is_symlink(), "E_ATTESTATION_BUNDLE_DIRECTORY")
    require(bundle.stat().st_mode & 0o077 == 0, "E_ATTESTATION_BUNDLE_PERMISSIONS")
    expected_names = {
        f"{domain_id}{suffix}"
        for domain_id in ("domain-1", "domain-2", "domain-3")
        for suffix in (".json", ".json.sig", ".pub")
    }
    require({path.name for path in bundle.iterdir()} == expected_names, "E_ATTESTATION_BUNDLE_FILE_SET")
    preflight = load_preflight_module()
    _, contract, _ = preflight.load_and_validate()
    packets: list[dict] = []
    signature_bindings: list[dict] = []
    packet_bindings: list[dict] = []
    for domain_id in ("domain-1", "domain-2", "domain-3"):
        packet_path = bundle / f"{domain_id}.json"
        signature_path = bundle / f"{domain_id}.json.sig"
        public_key_path = bundle / f"{domain_id}.pub"
        packet, packet_raw = parse_canonical_packet(packet_path)
        validate_attestation_packet(packet, source_commit, now)
        require(packet["domain_id"] == domain_id, "E_ATTESTATION_FILENAME_DOMAIN_BINDING")
        signature = verify_detached_signature(
            packet_raw, signature_path, public_key_path, domain_id,
            packet["operator_binding"]["public_key_sha256"],
        )
        packets.append(packet)
        signature_bindings.append({"domain_id": domain_id, **signature})
        packet_bindings.append({"domain_id": domain_id, "attestation_sha256": packet["attestation_sha256"]})
    set_validation = validate_attestation_set(packets, contract)
    packet_bindings.sort(key=lambda item: item["domain_id"])
    signature_bindings.sort(key=lambda item: item["domain_id"])
    set_sha256 = domain_digest(SET_DOMAIN, {
        "source_commit": source_commit,
        "packets": packet_bindings,
        "signatures": signature_bindings,
    })
    receipt = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_attestation_set_verification_receipt.v0",
        "status": "THREE_DOMAIN_INPUT_SET_COMPLETE_PENDING_OWNER_COUNTERSIGNATURE_NON_EXECUTING",
        "verified_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_commit": source_commit,
        "attestation_set_sha256": set_sha256,
        "earliest_attestation_expires_at": min(
            parse_time(packet["expires_at"], "E_ATTESTATION_EXPIRES_AT") for packet in packets
        ).astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "packet_bindings": packet_bindings,
        "signature_bindings": signature_bindings,
        "set_validation": set_validation,
        "owner_countersignature_verified": False,
        "execution_authorized": False,
        "credentials_accessed": False,
        "network_accessed": False,
        "services_started": 0,
        "faults_injected": 0,
        "production_admissible": False,
    }
    receipt["content_sha256"] = domain_digest(SET_RECEIPT_DOMAIN, receipt)
    return receipt


def current_source_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    require(result.returncode == 0 and bool(OID40.fullmatch(result.stdout.strip())), "E_SOURCE_COMMIT")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    require(status.returncode == 0 and status.stdout == "", "E_TRACKED_TREE_DIRTY")
    return result.stdout.strip()


def status() -> dict:
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_attestation_verifier_status.v0",
        "status": "BLOCKED_EXACT_THREE_PRIVATE_ATTESTATION_BUNDLE_AND_OWNER_COUNTERSIGNATURE_REQUIRED",
        "stable_host_identity_read": False,
        "private_bundle_read": False,
        "credentials_accessed": False,
        "network_accessed": False,
        "external_hosts_contacted": 0,
        "services_started": 0,
        "faults_injected": 0,
        "execution_authorized": False,
        "production_admissible": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    verify = subparsers.add_parser("verify-set")
    verify.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
        return
    source_commit = current_source_commit()
    receipt = verify_bundle(args.bundle.resolve(strict=True), source_commit, datetime.now(timezone.utc))
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except SafeFailure as error:
        print(json.dumps({"status": "BLOCKED_FAIL_CLOSED", "failure_code": str(error)}, sort_keys=True, separators=(",", ":")))
        sys.exit(1)
