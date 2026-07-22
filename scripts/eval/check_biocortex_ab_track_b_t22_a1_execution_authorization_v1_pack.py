"""Full synthetic KAT for final T22-A1 execution authorization admission."""
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
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_execution_authorization_v1.py"
spec = importlib.util.spec_from_file_location("t22a1executionauthorization", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module.EXECUTION_ACTIVATION_READY = True

countersignature = module.load_countersignature_module()
collection = countersignature.load_collection_module()
attestation = countersignature.load_attestation_module()
runtime = module.load_runtime_module()
preparation = module.load_preparation_authorization_module()
material = module.load_material_preparer_module()
_preflight, contract, proposal, _collection_schema = collection.load_committed_inputs()
execution_schema = json.loads(module.SCHEMA_PATH.read_text())
preparation_schema = json.loads(preparation.SCHEMA_PATH.read_text())

# Keep every dynamically loaded dependency on one synthetic trust-anchor view.
module.load_countersignature_module = lambda: countersignature
module.load_runtime_module = lambda: runtime
module.load_preparation_authorization_module = lambda: preparation
module.load_material_preparer_module = lambda: material
module.load_inputs = lambda: (
    countersignature, collection, attestation, runtime, preparation, material,
    contract, proposal, execution_schema,
)
countersignature.load_collection_module = lambda: collection
countersignature.load_attestation_module = lambda: attestation
preparation.load_inputs = lambda: (collection, runtime, contract, proposal, preparation_schema)
material.load_authorization_module = lambda: preparation

NOW = datetime.now(timezone.utc).replace(microsecond=0)
SOURCE_COMMIT = "a" * 40
RUN_ID = f"t22-a1-{NOW.strftime('%Y%m%dT%H%M%S')}.000000z-123456789abc"
SSH_KEYGEN = Path(shutil.which("ssh-keygen") or "").resolve(strict=True)
OPENSSL = Path(shutil.which("openssl") or "").resolve(strict=True)
SSH_KEYGEN_SHA256 = hashlib.sha256(SSH_KEYGEN.read_bytes()).hexdigest()
OPENSSL_SHA256 = hashlib.sha256(OPENSSL.read_bytes()).hexdigest()


def digest(label: str) -> str:
    return hashlib.sha256(f"T22_A1_EXECUTION_AUTHORIZATION_SYNTHETIC:{label}".encode()).hexdigest()


def write_private(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    path.write_bytes(module.canonical(value) + b"\n")
    path.chmod(0o600)


def sign(path: Path, key: Path, namespace: str) -> Path:
    signature = path.with_suffix(path.suffix + ".sig")
    if signature.exists():
        signature.unlink()
    result = subprocess.run(
        [str(SSH_KEYGEN), "-Y", "sign", "-f", str(key), "-n", namespace, str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    assert result.returncode == 0 and signature.is_file()
    signature.chmod(0o600)
    return signature


def domain_packet(number: int, public_key: Path) -> dict:
    issued = NOW + timedelta(seconds=number)
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
        "domain_id": f"domain-{number}", "attested_at": module.utc_text(issued),
        "expires_at": module.utc_text(issued + timedelta(hours=1)), "source_commit": SOURCE_COMMIT,
        "host_identity": {
            "hostname": f"synthetic-host-{number}", "logical_aliases": [f"synthetic-host-{number}"],
            "operating_system": "MACOS" if number == 2 else "LINUX", "kernel_release": "synthetic-kernel",
            "architecture": "AARCH64" if number == 2 else "X86_64",
            "machine_id_sha256": digest(f"machine:{number}"), "hardware_identity_sha256": digest(f"hardware:{number}"),
            "boot_id_sha256": digest(f"boot:{number}"), "physical_host_asserted": True,
            "provider_kind": "OWNER_PHYSICAL", "provider_identity_sha256": None,
            "region": None, "zone": None, "instance_identity_sha256": None,
        },
        "operator_binding": {
            "operator_role": "T22_A1_DOMAIN_OPERATOR",
            "public_key_sha256": attestation.canonical_public_key(public_key)[1],
            "signature_scheme": "OPENSSH_SSHSIG_ED25519", "signature_namespace": attestation.SIGNATURE_NAMESPACE,
            "private_key_exported": False,
        },
        "network_binding": {
            "transport": "OWNER_MANAGED_PRIVATE_OVERLAY", "peer_endpoint_set_sha256": digest("endpoint-set"),
            "acl_policy_receipt_sha256": digest("acl"), "public_listener_allowed": False,
            "credential_material_embedded": False,
        },
        "workload_readiness": {
            "pinned_tool_receipt_sha256": digest(f"tools:{number}"),
            "private_data_root_sha256": digest(f"data:{number}"), "port_set_sha256": digest(f"ports:{number}"),
            "tracked_tree_clean": True, "ambient_credentials_required": False,
        },
        "claims": {
            "candidate_for_distinct_physical_host": True, "site_or_power_independence_proved": False,
            "production_admissible": False, "attestation_is_execution_authority": False,
        },
    }
    value["attestation_sha256"] = attestation.domain_digest(attestation.ATTESTATION_DOMAIN, value)
    return value


def make_bundle(path: Path, keys: list[Path]) -> None:
    path.mkdir(mode=0o700)
    path.chmod(0o700)
    for number, key in enumerate(keys, 1):
        public = path / f"domain-{number}.pub"
        shutil.copyfile(str(key) + ".pub", public)
        public.chmod(0o600)
        packet = domain_packet(number, public)
        packet_path = path / f"domain-{number}.json"
        write_private(packet_path, packet)
        signature = sign(packet_path, key, attestation.SIGNATURE_NAMESPACE)
        assert signature == path / f"domain-{number}.json.sig"


def endpoint_manifest() -> dict:
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.private_endpoint_manifest.v1",
        "packet_kind": "T22_A1_PRIVATE_ENDPOINT_MANIFEST",
        "hashing_contract": {
            "hash_algorithm": "SHA-256", "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
            "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/private-endpoint-manifest/v1",
            "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256", "self_hash_field": "content_sha256",
            "self_hash_field_excluded": True, "cross_field_semantic_validation_required": True,
        },
        "run_id": RUN_ID, "source_commit": SOURCE_COMMIT, "transport": "OWNER_MANAGED_PRIVATE_OVERLAY",
        "acl_policy_receipt_sha256": digest("acl"),
        "domains": [{
            "domain_id": f"domain-{number}", "hostname": f"synthetic-host-{number}",
            "overlay_ip": f"100.64.20.{number}", "agent_control_port": 29000,
            "etcd_client_port": 2379, "etcd_peer_port": 2380,
            "openbao_api_port": 8200, "openbao_cluster_port": 8201,
            "bind_exact_overlay_ip_only": True, "public_listener_allowed": False,
        } for number in (1, 2, 3)],
        "raw_manifest_repository_allowed": False, "public_address_allowed": False,
        "dns_resolution_required": False,
    }
    value["content_sha256"] = runtime.digest(runtime.ENDPOINT_DOMAIN, value)
    return value


def physical_budget() -> dict:
    return {
        "mode": "THREE_OWNER_PHYSICAL_HOSTS_ZERO_SPEND", "provider": None,
        "region": None, "zone": None, "instance_type": None,
        "maximum_spend_usd_cents": 0,
    }


with tempfile.TemporaryDirectory(prefix="t22-a1-execution-authorization-kat-") as directory:
    base = Path(directory).resolve()
    owner_key = base / "owner"
    wrong_owner_key = base / "wrong-owner"
    domain_keys = [base / f"domain-{number}" for number in (1, 2, 3)]
    for key in (owner_key, wrong_owner_key, *domain_keys):
        subprocess.run([str(SSH_KEYGEN), "-q", "-t", "ed25519", "-N", "", "-C", "T22_A1_SYNTHETIC_ONLY", "-f", str(key)], check=True)

    anchor = collection.build_anchor(Path(str(owner_key) + ".pub"), proposal, proposal["proposal_sha256"])
    anchor_path = base / "owner-anchor.json"
    write_private(anchor_path, anchor)
    collection.ANCHOR_PATH = anchor_path

    artifact_root = base / "artifacts"
    artifact_root.mkdir(mode=0o700)
    artifact_root.chmod(0o700)
    bundle = base / "bundle"
    make_bundle(bundle, domain_keys)

    set_challenge = countersignature.build_challenge(
        anchor, contract, proposal, bundle, SOURCE_COMMIT, artifact_root,
        NOW + timedelta(seconds=10), 1800,
    )
    set_challenge_path = artifact_root / "authorizations" / "attestation-set-countersignature.json"
    write_private(set_challenge_path, set_challenge)
    set_signature_path = sign(set_challenge_path, owner_key, countersignature.SIGNATURE_NAMESPACE)
    admitted = countersignature.admit(
        set_challenge_path, set_signature_path, bundle, SOURCE_COMMIT,
        NOW + timedelta(seconds=11),
    )
    admitted_path = artifact_root / "admissions" / "owner-countersigned-attestation-set.json"

    endpoint = endpoint_manifest()
    endpoint_schema, credential_schema, _message_schema = runtime.load_schemas()
    runtime.validate_endpoint_manifest(endpoint, endpoint_schema, SOURCE_COMMIT, RUN_ID)
    endpoint_path = artifact_root / "manifests" / "private-endpoints.json"
    write_private(endpoint_path, endpoint)

    preparation_challenge = preparation.build_challenge(
        anchor, contract, proposal, SOURCE_COMMIT, RUN_ID,
        admitted["attestation_set_sha256"], admitted["content_sha256"],
        endpoint["content_sha256"], artifact_root,
        OPENSSL, OPENSSL_SHA256, SSH_KEYGEN, SSH_KEYGEN_SHA256,
        NOW + timedelta(seconds=12), NOW + timedelta(minutes=50), 1800, 3600,
    )
    preparation_challenge_path = artifact_root / "authorizations" / "runtime-preparation.json"
    write_private(preparation_challenge_path, preparation_challenge)
    preparation_signature_path = sign(preparation_challenge_path, owner_key, preparation.SIGNATURE_NAMESPACE)
    preparation_terminal = material.prepare(
        preparation_challenge_path, preparation_signature_path, SOURCE_COMMIT,
        NOW + timedelta(seconds=13), clock=lambda: NOW + timedelta(seconds=14),
    )
    preparation_terminal_path = artifact_root / "runtime-preparation-uses" / f"{preparation_challenge['content_sha256']}.terminal.json"
    credential_path = artifact_root / "manifests" / "runtime-credentials.json"
    credential = json.loads(credential_path.read_text())
    runtime.validate_credential_manifest(
        credential, credential_schema, SOURCE_COMMIT, RUN_ID,
        endpoint["content_sha256"], NOW + timedelta(minutes=50),
    )

    admitted_checked, _bundle_verification, packets, set_signature_sha256 = module.validate_set_evidence(
        admitted_path, set_challenge_path, set_signature_path, bundle,
        SOURCE_COMMIT, NOW + timedelta(seconds=15),
    )
    prep_checked, prep_terminal_checked, endpoint_checked, credential_checked, prep_signature_sha256 = module.validate_runtime_preparation_evidence(
        preparation_challenge_path, preparation_signature_path, preparation_terminal_path,
        endpoint_path, credential_path, SOURCE_COMMIT, NOW + timedelta(seconds=15),
        admitted["attestation_set_sha256"], admitted["content_sha256"],
    )
    altered_admitted = copy.deepcopy(admitted)
    altered_admitted["countersignature_bundle_verification_receipt_sha256"] = digest("forged-original-verification")
    altered_admitted.pop("content_sha256")
    altered_admitted["content_sha256"] = countersignature.digest(countersignature.ADMISSION_RECEIPT_DOMAIN, altered_admitted)
    altered_admitted_path = base / "altered-admitted-set.json"
    write_private(altered_admitted_path, altered_admitted)
    try:
        module.validate_set_evidence(
            altered_admitted_path, set_challenge_path, set_signature_path,
            bundle, SOURCE_COMMIT, NOW + timedelta(seconds=15),
        )
    except module.SafeFailure as error:
        assert str(error) == "E_EXECUTION_SET_ORIGINAL_VERIFICATION_BINDING"
    else:
        raise AssertionError("forged original bundle-verification binding admitted")

    altered_terminal = copy.deepcopy(preparation_terminal)
    altered_terminal["openssl_executable_sha256"] = digest("forged-openssl")
    altered_terminal.pop("content_sha256")
    altered_terminal["content_sha256"] = material.terminal_digest(altered_terminal)
    altered_terminal_path = base / "altered-runtime-preparation-terminal.json"
    write_private(altered_terminal_path, altered_terminal)
    try:
        module.validate_runtime_preparation_evidence(
            preparation_challenge_path, preparation_signature_path,
            altered_terminal_path, endpoint_path, credential_path,
            SOURCE_COMMIT, NOW + timedelta(seconds=15),
            admitted["attestation_set_sha256"], admitted["content_sha256"],
        )
    except module.SafeFailure as error:
        assert str(error) == "E_EXECUTION_PREPARATION_TOOL_BINDING"
    else:
        raise AssertionError("forged runtime-preparation tool binding admitted")
    execution = module.build_execution_contract(
        anchor, contract, proposal, execution_schema, SOURCE_COMMIT,
        NOW + timedelta(seconds=16), 1200, artifact_root, "domain-2",
        physical_budget(), admitted_checked, packets,
        set_signature_sha256, prep_checked, prep_terminal_checked,
        endpoint_checked, credential_checked, prep_signature_sha256,
    )
    execution_path = artifact_root / "authorizations" / "final-execution-contract.json"
    write_private(execution_path, execution)
    execution_signature_path = sign(execution_path, owner_key, module.SIGNATURE_NAMESPACE)
    receipt = module.admit(
        execution_path, execution_signature_path, SOURCE_COMMIT,
        NOW + timedelta(seconds=17), admitted_path, set_challenge_path,
        set_signature_path, bundle, preparation_challenge_path,
        preparation_signature_path, preparation_terminal_path, endpoint_path,
        credential_path,
    )
    assert receipt["status"] == "AUTHORIZED_T22_A1_EXACT_OWNER_SIGNED_NONPRODUCTION_EXECUTION_ADMISSION"
    assert receipt["execution_contract_sha256"] == execution["content_sha256"]
    assert receipt["owner_execution_signature_verified"] is True
    assert receipt["credential_files_read_only_after_owner_execution_signature"] is True
    assert receipt["certificate_count"] == receipt["private_key_count"] == 5
    assert receipt["all_credential_files_verified"] is True
    assert receipt["one_execution_per_admission_receipt"] is True
    assert receipt["network_accessed"] is False and receipt["external_hosts_contacted"] == 0
    assert receipt["listeners_started"] == receipt["services_started"] == receipt["faults_injected"] == 0
    assert receipt["spend_usd_cents"] == 0 and receipt["production_admissible"] is False
    receipt_path = artifact_root / "admissions" / "final-execution-admission.json"
    assert receipt_path.read_bytes() == module.canonical(receipt) + b"\n"
    assert module.parse_admission_receipt(receipt_path, execution, NOW + timedelta(seconds=17)) == receipt

    # The run CA, not only every leaf, must cover the signed execution window.
    original_certificate_not_after = material.certificate_not_after
    material.certificate_not_after = lambda *_arguments: module.parse_time(
        execution["expires_at"], "E_TEST_EXECUTION_EXPIRY",
    ) - timedelta(seconds=1)
    try:
        try:
            module.verify_runtime_credential_files(execution, endpoint, credential, material)
        except module.SafeFailure as error:
            assert str(error) == "E_EXECUTION_CA_EXPIRY"
        else:
            raise AssertionError("execution admitted with CA expiring before execution")
    finally:
        material.certificate_not_after = original_certificate_not_after

    receipt_mutations = (
        lambda x: x.update(status="PRODUCTION_AUTHORIZED"),
        lambda x: x.update(source_commit="b" * 40),
        lambda x: x.update(execution_contract_sha256=digest("wrong-execution")),
        lambda x: x.update(owner_execution_signature_sha256="0" * 64),
        lambda x: x.update(owner_set_countersignature_reverified=False),
        lambda x: x.update(certificate_count=4),
        lambda x: x.update(automatic_retry_allowed=True),
        lambda x: x.update(raw_endpoint_or_credential_values_in_receipt=True),
        lambda x: x.update(network_accessed=True),
        lambda x: x.update(services_started=1),
        lambda x: x.update(execution_authorized=False),
        lambda x: x.update(production_admissible=True),
        lambda x: x.update(unexpected="field"),
    )
    for mutation in receipt_mutations:
        candidate = copy.deepcopy(receipt)
        mutation(candidate)
        candidate.pop("content_sha256", None)
        candidate["content_sha256"] = module.digest(module.ADMISSION_RECEIPT_DOMAIN, candidate)
        try:
            module.validate_admission_receipt(candidate, execution, NOW + timedelta(seconds=17))
        except module.SafeFailure:
            continue
        raise AssertionError("unsafe execution-admission receipt mutation admitted")
    try:
        module.validate_admission_receipt(
            receipt, execution,
            module.parse_time(receipt["expires_at"], "E_TEST_EXPIRY") + timedelta(seconds=1),
        )
    except module.SafeFailure as error:
        assert str(error) == "E_EXECUTION_ADMISSION_RECEIPT_NOT_CURRENT"
    else:
        raise AssertionError("expired execution-admission receipt admitted")
    receipt_raw = receipt_path.read_bytes()
    assert all(domain["overlay_ip"].encode() not in receipt_raw for domain in endpoint["domains"])
    assert all(str(path).encode() not in receipt_raw for path in (credential_path, endpoint_path, artifact_root / "credentials"))

    def rejected_contract(mutate) -> None:  # noqa: ANN001
        candidate = copy.deepcopy(execution)
        mutate(candidate)
        candidate.pop("content_sha256", None)
        candidate["content_sha256"] = module.contract_digest(candidate)
        try:
            module.validate_execution_contract(
                candidate, execution_schema, contract, proposal, SOURCE_COMMIT,
                NOW + timedelta(seconds=17),
            )
        except module.SafeFailure:
            return
        raise AssertionError("unsafe execution contract mutation admitted")

    contract_mutations = (
        lambda x: x.update(source_commit="b" * 40),
        lambda x: x.update(expires_at=module.utc_text(NOW + timedelta(hours=5))),
        lambda x: x["authorization"].update(automatic_retry_allowed=True),
        lambda x: x["artifact_scope"].update(private_artifact_root=str(ROOT)),
        lambda x: x["artifact_scope"].update(execution_admission_receipt_output_path=str(artifact_root / "other.json")),
        lambda x: x["artifact_scope"].update(run_evidence_root=str(artifact_root / "runs" / "other")),
        lambda x: x["admission_bindings"].update(admission_contract_sha256=digest("wrong-contract")),
        lambda x: x["admission_bindings"].update(owner_decision_proposal_sha256=digest("wrong-proposal")),
        lambda x: x["admission_bindings"].update(domain_attestation_schema_sha256=digest("wrong-schema")),
        lambda x: x["private_runtime"].update(private_endpoint_manifest_schema_sha256=digest("wrong-schema")),
        lambda x: x["private_runtime"].update(runtime_credential_manifest_schema_sha256=digest("wrong-schema")),
        lambda x: x["private_runtime"].update(domain_agent_message_schema_sha256=digest("wrong-schema")),
        lambda x: x["evidence_contract"].update(distributed_event_schema_sha256=digest("wrong-schema")),
        lambda x: x["evidence_contract"].update(terminal_evidence_schema_sha256=digest("wrong-schema")),
        lambda x: x["claims"].update(production_admissible=True),
        lambda x: x.update(unexpected="field"),
    )
    for mutation in contract_mutations:
        rejected_contract(mutation)

    # Replay is rejected before any private input or credential file is read.
    original_read_bytes = Path.read_bytes
    protected = {
        path.resolve() for path in [
            admitted_path, set_challenge_path, *bundle.iterdir(),
            preparation_challenge_path, preparation_terminal_path,
            endpoint_path, credential_path, *(artifact_root / "credentials").iterdir(),
        ]
    }

    def reject_private_read(path: Path) -> bytes:
        if path.resolve(strict=False) in protected:
            raise AssertionError("private evidence read before replay rejection")
        return original_read_bytes(path)

    Path.read_bytes = reject_private_read
    try:
        try:
            module.admit(
                execution_path, execution_signature_path, SOURCE_COMMIT,
                NOW + timedelta(seconds=18), admitted_path, set_challenge_path,
                set_signature_path, bundle, preparation_challenge_path,
                preparation_signature_path, preparation_terminal_path,
                endpoint_path, credential_path,
            )
        except module.SafeFailure as error:
            assert str(error) == "E_EXECUTION_ADMISSION_OUTPUT_EXISTS"
        else:
            raise AssertionError("execution authorization replay admitted")
    finally:
        Path.read_bytes = original_read_bytes

    receipt_path.unlink()
    Path.read_bytes = reject_private_read
    try:
        try:
            module.admit(
                execution_path, execution_signature_path, SOURCE_COMMIT,
                NOW + timedelta(seconds=18), admitted_path, set_challenge_path,
                set_signature_path, bundle, preparation_challenge_path,
                preparation_signature_path, preparation_terminal_path,
                endpoint_path, credential_path,
            )
        except module.SafeFailure as error:
            assert str(error) == "E_EXECUTION_OUTPUT_EXISTS"
        else:
            raise AssertionError("deleted-output execution authorization replay admitted")
    finally:
        Path.read_bytes = original_read_bytes
    write_private(receipt_path, receipt)

    # A wrong final owner signature cannot trigger private-evidence reads.
    wrong_root = base / "wrong-signature-artifacts"
    wrong_root.mkdir(mode=0o700)
    wrong_root.chmod(0o700)
    wrong_execution = copy.deepcopy(execution)
    wrong_execution["artifact_scope"] = {
        "private_artifact_root": str(wrong_root),
        "execution_admission_receipt_output_path": str(wrong_root / "admissions" / "final-execution-admission.json"),
        "run_evidence_root": str(wrong_root / "runs" / RUN_ID),
        "repository_output_allowed": False, "directory_mode": "0700", "file_mode": "0600",
    }
    wrong_execution["content_sha256"] = module.contract_digest(wrong_execution)
    wrong_execution_path = wrong_root / "final-execution-contract.json"
    write_private(wrong_execution_path, wrong_execution)
    wrong_signature_path = sign(wrong_execution_path, wrong_owner_key, module.SIGNATURE_NAMESPACE)
    Path.read_bytes = reject_private_read
    try:
        try:
            module.admit(
                wrong_execution_path, wrong_signature_path, SOURCE_COMMIT,
                NOW + timedelta(seconds=18), admitted_path, set_challenge_path,
                set_signature_path, bundle, preparation_challenge_path,
                preparation_signature_path, preparation_terminal_path,
                endpoint_path, credential_path,
            )
        except module.SafeFailure as error:
            assert str(error) == "E_EXECUTION_OWNER_SIGNATURE_INVALID"
        else:
            raise AssertionError("wrong final owner signature admitted")
    finally:
        Path.read_bytes = original_read_bytes

    # Re-signing a contract bound to a tampered credential file reaches the
    # post-signature verifier, fails terminally, and grants no retry.
    tamper_root = artifact_root
    receipt_path.unlink()
    tampered_execution = copy.deepcopy(execution)
    tampered_execution["fault"]["target_domain_id"] = "domain-3"
    tampered_execution["content_sha256"] = module.contract_digest(tampered_execution)
    tampered_execution_path = tamper_root / "authorizations" / "final-execution-contract-tamper.json"
    write_private(tampered_execution_path, tampered_execution)
    tampered_signature_path = sign(tampered_execution_path, owner_key, module.SIGNATURE_NAMESPACE)
    tampered_private_key = tamper_root / "credentials" / "domain-3.key"
    subprocess.run([
        str(OPENSSL), "genpkey", "-algorithm", "EC",
        "-pkeyopt", "ec_paramgen_curve:P-256", "-out", str(tampered_private_key),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    tampered_private_key.chmod(0o600)
    try:
        module.admit(
            tampered_execution_path, tampered_signature_path, SOURCE_COMMIT,
            NOW + timedelta(seconds=18), admitted_path, set_challenge_path,
            set_signature_path, bundle, preparation_challenge_path,
            preparation_signature_path, preparation_terminal_path,
            endpoint_path, credential_path,
        )
    except module.SafeFailure as error:
        assert str(error) in {"E_CERTIFICATE_KEY_MISMATCH", "E_PRIVATE_KEY_SPKI"}
    else:
        raise AssertionError("tampered credential private key admitted")
    tamper_terminal = json.loads((tamper_root / "final-execution-authorization-uses" / f"{tampered_execution['content_sha256']}.terminal.json").read_text())
    assert tamper_terminal["owner_execution_signature_verified"] is True
    assert tamper_terminal["credential_files_read_after_owner_signature"] is True
    assert tamper_terminal["automatic_retry_allowed"] is False
    assert tamper_terminal["network_accessed"] is False

    ready = module.status()
    assert ready["status"] == "BLOCKED_FINAL_PRIVATE_EVIDENCE_AND_EXACT_OWNER_EXECUTION_SIGNATURE_REQUIRED"
    assert ready["private_evidence_read"] is False and ready["credential_files_read"] is False

    module.EXECUTION_ACTIVATION_READY = False
    try:
        module.admit(
            execution_path, execution_signature_path, SOURCE_COMMIT,
            NOW + timedelta(seconds=18), admitted_path, set_challenge_path,
            set_signature_path, bundle, preparation_challenge_path,
            preparation_signature_path, preparation_terminal_path, endpoint_path,
            credential_path,
        )
    except module.SafeFailure as error:
        assert str(error) == "E_EXECUTION_ACTIVATION_NOT_READY"
    else:
        raise AssertionError("real activation admitted while runner readiness gate was closed")

collection.ANCHOR_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-owner-trust-anchor-v1.json"
blocked = module.status()
assert blocked["status"] == "BLOCKED_T22_A1_RUNNER_HOST_READINESS_AND_CREDENTIAL_PLACEMENT_REQUIRED"
assert blocked["execution_activation_ready"] is False
assert blocked["owner_trust_anchor_present"] is False and blocked["owner_trust_anchor_valid"] is False
assert blocked["private_evidence_read"] is False and blocked["credential_files_read"] is False
assert blocked["network_accessed"] is False and blocked["external_hosts_contacted"] == 0
assert blocked["listeners_started"] == blocked["services_started"] == blocked["faults_injected"] == 0
assert blocked["spend_usd_cents"] == 0 and blocked["execution_authorized"] is False
assert blocked["production_admissible"] is False

negative_count = len(contract_mutations) + len(receipt_mutations) + 9
print("t22_a1_execution_authorization_check\tpass")
print("synthetic_full_chain_success_count\t1")
print(f"directed_negative_test_count\t{negative_count}")
print("real_private_evidence_items_read\t0")
print("real_credential_files_read\t0")
print("synthetic_credential_files_verified\t11")
print("network_accessed\tfalse")
print("external_hosts_contacted\t0")
print("listeners_started\t0")
print("services_started\t0")
print("faults_injected\t0")
print("spend_usd_cents\t0")
print("production_admissible\tfalse")
