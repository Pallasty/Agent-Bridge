"""Final owner-signed, single-use T22-A1 execution admission bridge.

Generation revalidates already-authorized private evidence but reads no
credential file. Admission verifies the exact owner signature first, reserves
the authorization once, and only then reads and cryptographically verifies the
contract-bound credential files. This module never opens a socket, starts a
listener or service, injects a fault, contacts a provider, or spends money.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
COUNTERSIGNATURE_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_attestation_set_countersignature_v1.py"
RUNTIME_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_private_runtime_contracts_v1.py"
PREPARATION_AUTHORIZATION_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_runtime_preparation_authorization_v1.py"
MATERIAL_PREPARER_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_runtime_material_preparer_v1.py"
READINESS_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_runtime_readiness_v1.py"
SCHEMA_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a1-distributed-execution-contract-schema-v1.json"
EXPECTED_SCHEMA_SHA256 = "f1738c7b4d4eb7749739a0f73ca599bab2577a40c62681527f78b24a28655426"
EXECUTION_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/distributed-execution-contract/v1\0"
ADMISSION_RECEIPT_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/execution-admission-receipt/v1\0"
TERMINAL_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/execution-admission-terminal/v1\0"
SIGNATURE_NAMESPACE = "agent-bridge-t22-a1-owner-v1"
MAX_JSON_BYTES = 256 * 1024
MAX_SIGNATURE_BYTES = 64 * 1024
SOURCE_ARTIFACT_SET_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/source-artifact-set/v1\0"
READINESS_SET_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-runtime-readiness-set/v1\0"
SOURCE_ARTIFACT_PATHS = (
    ("source_bound_runner", "scripts/eval/biocortex_ab_track_b_t22_a1_source_bound_runner_v1.py"),
    ("domain_workload_plan", "scripts/eval/biocortex_ab_track_b_t22_a1_domain_workload_plan_v1.py"),
    ("domain_agent_session", "scripts/eval/biocortex_ab_track_b_t22_a1_domain_agent_session_v1.py"),
    ("domain_executor_core", "scripts/eval/biocortex_ab_track_b_t22_a1_domain_executor_core_v1.py"),
    ("live_local_backend", "scripts/eval/biocortex_ab_track_b_t22_a1_live_local_backend_v1.py"),
    ("authenticated_domain_lane", "scripts/eval/biocortex_ab_track_b_t22_a1_authenticated_domain_lane_v1.py"),
    ("mtls_transport", "scripts/eval/biocortex_ab_track_b_t22_a1_mtls_transport_v1.py"),
    ("evidence_compiler", "scripts/eval/biocortex_ab_track_b_t22_a1_evidence_compiler_v1.py"),
    ("evidence_writer", "scripts/eval/biocortex_ab_track_b_t22_a1_evidence_writer_v1.py"),
    ("execution_consumer", "scripts/eval/biocortex_ab_track_b_t22_a1_execution_consumer_v1.py"),
)
# This may become True only in the final reviewed source commit after exact
# coordinator/domain launch binding, three real readiness packets, placement
# proof, and the complete lane/backend/evidence activation audit. Synthetic
# KATs opt in explicitly.
EXECUTION_ACTIVATION_READY = False


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def foreign_call(function, *arguments, **keywords):  # noqa: ANN001, ANN002, ANN003
    try:
        return function(*arguments, **keywords)
    except RuntimeError as error:
        raise SafeFailure(str(error)) from error


def load_module(name: str, source: Path):
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_countersignature_module():
    return load_module("t22a1_set_for_execution_authorization", COUNTERSIGNATURE_SOURCE)


def load_runtime_module():
    return load_module("t22a1_runtime_for_execution_authorization", RUNTIME_SOURCE)


def load_preparation_authorization_module():
    return load_module("t22a1_preparation_for_execution_authorization", PREPARATION_AUTHORIZATION_SOURCE)


def load_material_preparer_module():
    return load_module("t22a1_material_for_execution_authorization", MATERIAL_PREPARER_SOURCE)


def load_readiness_module():
    return load_module("t22a1_readiness_for_execution_authorization", READINESS_SOURCE)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(domain: bytes, value: object) -> str:
    return hashlib.sha256(domain + canonical(value)).hexdigest()


def utc_text(value: datetime) -> str:
    require(value.tzinfo is not None and value.utcoffset().total_seconds() == 0, "E_EXECUTION_TIMEZONE")
    return value.isoformat().replace("+00:00", "Z")


def parse_time(value: str, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise SafeFailure(code) from error
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0, code)
    return parsed


def contract_digest(value: dict) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return digest(EXECUTION_DOMAIN, unsigned)


def collect_source_artifacts() -> tuple[list[dict], str]:
    rows: list[dict] = []
    for name, relative_path in SOURCE_ARTIFACT_PATHS:
        path = ROOT / relative_path
        require(path.is_file() and not path.is_symlink(), "E_EXECUTION_SOURCE_ARTIFACT_FILE")
        rows.append({
            "name": name, "path": relative_path,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    require(len({row["name"] for row in rows}) == len(rows) and len({row["path"] for row in rows}) == len(rows), "E_EXECUTION_SOURCE_ARTIFACT_SET")
    return rows, digest(SOURCE_ARTIFACT_SET_DOMAIN, rows)


def load_inputs() -> tuple[object, object, object, object, object, object, dict, dict, dict]:
    countersignature = load_countersignature_module()
    collection, attestation, contract, proposal, _set_schema = countersignature.load_inputs()
    runtime = load_runtime_module()
    preparation = load_preparation_authorization_module()
    material = load_material_preparer_module()
    raw = SCHEMA_PATH.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == EXPECTED_SCHEMA_SHA256, "E_EXECUTION_SCHEMA_DIGEST")
    try:
        schema = json.loads(raw)
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        raise SafeFailure("E_EXECUTION_SCHEMA_INVALID") from error
    preflight = collection.load_preflight_module()
    require(preflight.EXPECTED_EXECUTION_SCHEMA_SHA256 == EXPECTED_SCHEMA_SHA256, "E_EXECUTION_SCHEMA_PREFLIGHT_BINDING")
    require(preflight.EXPECTED_CREDENTIAL_MANIFEST_SCHEMA_SHA256 == runtime.EXPECTED_CREDENTIAL_SCHEMA_SHA256, "E_EXECUTION_CREDENTIAL_SCHEMA_BINDING")
    return countersignature, collection, attestation, runtime, preparation, material, contract, proposal, schema


def read_canonical_json(path: Path, code: str, private: bool = True) -> tuple[dict, bytes]:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), f"{code}_FILE")
    metadata = path.stat()
    require(stat.S_ISREG(metadata.st_mode) and 0 < metadata.st_size <= MAX_JSON_BYTES, f"{code}_FILE")
    if private:
        require(metadata.st_mode & 0o077 == 0, f"{code}_PERMISSIONS")
    raw = path.read_bytes()
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, f"{code}_FRAMING")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SafeFailure(f"{code}_JSON") from error
    require(raw == canonical(value) + b"\n", f"{code}_NOT_CANONICAL")
    require(isinstance(value, dict), f"{code}_SHAPE")
    return value, raw


def path_outside_repository(path: Path) -> bool:
    if not path.is_absolute():
        return False
    resolved = path.resolve(strict=False)
    repository = ROOT.resolve()
    return repository not in (resolved, *resolved.parents) and resolved not in repository.parents


def validate_artifact_scope(scope: dict, run_id: str) -> Path:
    root = Path(scope["private_artifact_root"])
    output = Path(scope["execution_admission_receipt_output_path"])
    evidence = Path(scope["run_evidence_root"])
    require(path_outside_repository(root), "E_EXECUTION_ARTIFACT_ROOT")
    resolved = root.resolve(strict=False)
    require(output.resolve(strict=False) == resolved / "admissions" / "final-execution-admission.json", "E_EXECUTION_ADMISSION_OUTPUT_PATH")
    require(evidence.resolve(strict=False) == resolved / "runs" / run_id, "E_EXECUTION_EVIDENCE_ROOT")
    return resolved


def validate_execution_contract(
    value: object,
    schema: dict,
    contract: dict,
    proposal: dict,
    expected_source_commit: str,
    now: datetime,
) -> dict:
    require(now.tzinfo is not None and now.utcoffset().total_seconds() == 0, "E_EXECUTION_VALIDATION_TIME")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    require(not list(validator.iter_errors(value)), "E_EXECUTION_CONTRACT_SCHEMA")
    assert isinstance(value, dict)
    require(value["source_commit"] == expected_source_commit, "E_EXECUTION_SOURCE_BINDING")
    issued = parse_time(value["issued_at"], "E_EXECUTION_ISSUED_AT")
    expires = parse_time(value["expires_at"], "E_EXECUTION_EXPIRES_AT")
    maximum = value["authorization"]["maximum_runtime_seconds"]
    require(issued <= now < expires and 0 < (expires - issued).total_seconds() <= maximum <= 14400, "E_EXECUTION_NOT_CURRENT")
    validate_artifact_scope(value["artifact_scope"], value["run_id"])
    countersignature = load_countersignature_module()
    collection = countersignature.load_collection_module()
    preflight = collection.load_preflight_module()
    admission = value["admission_bindings"]
    require(admission["admission_contract_sha256"] == contract["contract_sha256"], "E_EXECUTION_ADMISSION_CONTRACT")
    require(admission["owner_decision_proposal_sha256"] == proposal["proposal_sha256"], "E_EXECUTION_PROPOSAL")
    require(admission["domain_attestation_schema_sha256"] == preflight.EXPECTED_SCHEMA_SHA256, "E_EXECUTION_ATTESTATION_SCHEMA")
    private = value["private_runtime"]
    require(private["private_endpoint_manifest_schema_sha256"] == preflight.EXPECTED_ENDPOINT_MANIFEST_SCHEMA_SHA256, "E_EXECUTION_ENDPOINT_SCHEMA")
    require(private["runtime_credential_manifest_schema_sha256"] == preflight.EXPECTED_CREDENTIAL_MANIFEST_SCHEMA_SHA256, "E_EXECUTION_CREDENTIAL_SCHEMA")
    require(private["domain_agent_message_schema_sha256"] == preflight.EXPECTED_AGENT_MESSAGE_SCHEMA_SHA256, "E_EXECUTION_AGENT_SCHEMA")
    runtime_admission = value["runtime_admission"]
    require(runtime_admission["domain_runtime_readiness_schema_sha256"] == preflight.EXPECTED_DOMAIN_RUNTIME_READINESS_SCHEMA_SHA256, "E_EXECUTION_READINESS_SCHEMA")
    require(
        [row["domain_id"] for row in runtime_admission["packet_bindings"]] == ["domain-1", "domain-2", "domain-3"]
        and [row["domain_id"] for row in runtime_admission["signature_bindings"]] == ["domain-1", "domain-2", "domain-3"],
        "E_EXECUTION_READINESS_ORDER",
    )
    readiness_payload = {
        "source_commit": value["source_commit"], "run_id": value["run_id"],
        "attestation_set_sha256": admission["exact_three_domain_attestation_packet_set_sha256"],
        "owner_countersigned_attestation_set_receipt_sha256": admission["owner_countersigned_attestation_set_receipt_sha256"],
        "private_endpoint_manifest_content_sha256": private["private_endpoint_manifest_content_sha256"],
        "runtime_credential_manifest_content_sha256": private["runtime_credential_manifest_content_sha256"],
        "runtime_preparation_terminal_receipt_sha256": private["runtime_preparation_terminal_receipt_sha256"],
        "packets": runtime_admission["packet_bindings"],
        "signatures": runtime_admission["signature_bindings"],
    }
    require(runtime_admission["runtime_readiness_set_sha256"] == digest(READINESS_SET_DOMAIN, readiness_payload), "E_EXECUTION_READINESS_SET_BINDING")
    expected_sources, expected_source_set_sha256 = collect_source_artifacts()
    require(
        runtime_admission["source_artifacts"] == expected_sources
        and runtime_admission["source_artifact_set_sha256"] == expected_source_set_sha256,
        "E_EXECUTION_SOURCE_ARTIFACT_BINDING",
    )
    require(expires <= parse_time(runtime_admission["earliest_runtime_readiness_expires_at"], "E_EXECUTION_READINESS_EXPIRY"), "E_EXECUTION_READINESS_EXPIRY")
    evidence = value["evidence_contract"]
    require(evidence["distributed_event_schema_sha256"] == preflight.EXPECTED_EVENT_SCHEMA_SHA256, "E_EXECUTION_EVENT_SCHEMA")
    require(evidence["terminal_evidence_schema_sha256"] == preflight.EXPECTED_TERMINAL_SCHEMA_SHA256, "E_EXECUTION_TERMINAL_SCHEMA")
    require(value["content_sha256"] == contract_digest(value), "E_EXECUTION_CONTRACT_DIGEST")
    return value


def validate_material_terminal(value: dict, source_commit: str, run_id: str, now: datetime, material) -> dict:  # noqa: ANN001
    required = {
        "schema", "status", "failure_code", "run_id", "source_commit",
        "challenge_content_sha256", "owner_signature_sha256",
        "exact_three_domain_attestation_set_sha256",
        "owner_countersigned_attestation_set_receipt_sha256",
        "private_endpoint_manifest_content_sha256",
        "runtime_credential_manifest_content_sha256",
        "coordinator_runtime_public_key_sha256", "openssl_executable_sha256",
        "ssh_keygen_executable_sha256", "certificate_count",
        "retained_private_key_count", "private_ca_signing_key_retained",
        "certificate_chain_key_eku_expiry_and_endpoint_bindings_verified",
        "private_endpoint_manifest_instance_read", "raw_endpoint_values_in_receipt",
        "private_key_material_in_manifest_or_receipt",
        "ambient_or_preexisting_credentials_accessed", "network_accessed",
        "external_hosts_contacted", "listeners_started", "services_started",
        "faults_injected", "spend_usd_cents", "automatic_retry_allowed",
        "execution_authorized", "production_admissible", "completed_at",
        "content_sha256",
    }
    require(set(value) == required, "E_RUNTIME_PREPARATION_TERMINAL_SHAPE")
    require(value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.runtime_preparation_terminal.v1", "E_RUNTIME_PREPARATION_TERMINAL_SCHEMA")
    require(value["status"] == "PASS_T22_A1_ZERO_NETWORK_PRIVATE_RUNTIME_MATERIAL_PREPARATION" and value["failure_code"] is None, "E_RUNTIME_PREPARATION_TERMINAL_STATUS")
    require(value["source_commit"] == source_commit and value["run_id"] == run_id, "E_RUNTIME_PREPARATION_TERMINAL_RUN")
    require(value["certificate_count"] == value["retained_private_key_count"] == 5, "E_RUNTIME_PREPARATION_TERMINAL_COUNTS")
    require(value["private_ca_signing_key_retained"] is False and value["certificate_chain_key_eku_expiry_and_endpoint_bindings_verified"] is True, "E_RUNTIME_PREPARATION_TERMINAL_CRYPTO")
    require(value["private_endpoint_manifest_instance_read"] is True and value["raw_endpoint_values_in_receipt"] is False, "E_RUNTIME_PREPARATION_TERMINAL_ENDPOINT")
    require(value["private_key_material_in_manifest_or_receipt"] is False and value["ambient_or_preexisting_credentials_accessed"] is False, "E_RUNTIME_PREPARATION_TERMINAL_SECRET")
    require(value["network_accessed"] is False and value["external_hosts_contacted"] == 0 and value["listeners_started"] == 0, "E_RUNTIME_PREPARATION_TERMINAL_NETWORK")
    require(value["services_started"] == value["faults_injected"] == value["spend_usd_cents"] == 0, "E_RUNTIME_PREPARATION_TERMINAL_SIDE_EFFECT")
    require(value["automatic_retry_allowed"] is False and value["execution_authorized"] is False and value["production_admissible"] is False, "E_RUNTIME_PREPARATION_TERMINAL_CLAIMS")
    require(parse_time(value["completed_at"], "E_RUNTIME_PREPARATION_COMPLETED_AT") <= now, "E_RUNTIME_PREPARATION_TERMINAL_FUTURE")
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256")
    require(claimed == material.terminal_digest(unsigned), "E_RUNTIME_PREPARATION_TERMINAL_DIGEST")
    return value


def validate_set_evidence(
    admitted_receipt_path: Path,
    countersignature_path: Path,
    countersignature_signature_path: Path,
    bundle: Path,
    source_commit: str,
    now: datetime,
) -> tuple[dict, dict, list[dict], str]:
    countersignature, collection, attestation, _runtime, _preparation, _material, contract, proposal, _execution_schema = load_inputs()
    set_schema = countersignature.load_inputs()[-1]
    receipt = countersignature.parse_admission_receipt(admitted_receipt_path, source_commit, contract, proposal, now)
    challenge, raw = countersignature.parse_canonical_challenge(countersignature_path)
    anchor = json.loads(collection.ANCHOR_PATH.read_text())
    public_key = foreign_call(collection.validate_anchor, anchor, proposal)
    admitted_at = parse_time(receipt["admitted_at"], "E_ADMITTED_SET_RECEIPT_TIME")
    countersignature.validate_envelope(challenge, anchor, contract, proposal, set_schema, source_commit, admitted_at)
    signature_sha256 = countersignature.verify_owner_signature(raw, countersignature_signature_path, public_key)
    require(receipt["attestation_set_countersignature_content_sha256"] == challenge["content_sha256"], "E_EXECUTION_SET_COUNTERSIGNATURE_BINDING")
    require(receipt["owner_signature_sha256"] == signature_sha256, "E_EXECUTION_SET_SIGNATURE_BINDING")
    require(
        receipt["countersignature_bundle_verification_receipt_sha256"]
        == challenge["verified_set"]["bundle_verification_receipt_sha256"],
        "E_EXECUTION_SET_ORIGINAL_VERIFICATION_BINDING",
    )
    require(countersignature.stable_verified_set(challenge["verified_set"]) == countersignature.stable_verified_set({
        "attestation_set_sha256": receipt["attestation_set_sha256"],
        "earliest_attestation_expires_at": receipt["earliest_attestation_expires_at"],
        "packet_bindings": receipt["packet_bindings"],
        "signature_bindings": receipt["signature_bindings"],
        "set_validation": receipt["set_validation"],
    }), "E_EXECUTION_SET_RECEIPT_BINDING")
    verification = attestation.verify_bundle(bundle, source_commit, now)
    require(countersignature.stable_verified_set(countersignature.verified_set_from_receipt(verification)) == countersignature.stable_verified_set({
        "attestation_set_sha256": receipt["attestation_set_sha256"],
        "earliest_attestation_expires_at": receipt["earliest_attestation_expires_at"],
        "packet_bindings": receipt["packet_bindings"],
        "signature_bindings": receipt["signature_bindings"],
        "set_validation": receipt["set_validation"],
    }), "E_EXECUTION_SET_REVERIFICATION_BINDING")
    packets = [attestation.parse_canonical_packet(bundle / f"domain-{number}.json")[0] for number in (1, 2, 3)]
    return receipt, verification, packets, signature_sha256


def validate_runtime_preparation_evidence(
    preparation_challenge_path: Path,
    preparation_signature_path: Path,
    preparation_terminal_path: Path,
    endpoint_manifest_path: Path,
    credential_manifest_path: Path,
    source_commit: str,
    now: datetime,
    expected_set_sha256: str,
    expected_admitted_set_receipt_sha256: str,
) -> tuple[dict, dict, dict, dict, str]:
    _counter, collection, _attestation, runtime, preparation, material, contract, proposal, _schema = load_inputs()
    terminal, _terminal_raw = read_canonical_json(preparation_terminal_path, "E_RUNTIME_PREPARATION_TERMINAL")
    run_id = terminal.get("run_id")
    require(isinstance(run_id, str), "E_RUNTIME_PREPARATION_TERMINAL_RUN")
    validate_material_terminal(terminal, source_commit, run_id, now, material)
    challenge, raw = preparation.parse_canonical_challenge(preparation_challenge_path)
    anchor = json.loads(collection.ANCHOR_PATH.read_text())
    public_key = foreign_call(collection.validate_anchor, anchor, proposal)
    completed_at = parse_time(terminal["completed_at"], "E_RUNTIME_PREPARATION_COMPLETED_AT")
    preparation.validate_challenge(
        challenge, anchor, contract, proposal, json.loads(preparation.SCHEMA_PATH.read_text()),
        source_commit, expected_set_sha256, expected_admitted_set_receipt_sha256,
        challenge["bindings"]["private_endpoint_manifest_content_sha256"], completed_at,
    )
    signature_sha256 = preparation.verify_signature(raw, preparation_signature_path, public_key)
    require(terminal["challenge_content_sha256"] == challenge["content_sha256"], "E_EXECUTION_PREPARATION_CHALLENGE_BINDING")
    require(terminal["owner_signature_sha256"] == signature_sha256, "E_EXECUTION_PREPARATION_SIGNATURE_BINDING")
    require(terminal["exact_three_domain_attestation_set_sha256"] == expected_set_sha256, "E_EXECUTION_PREPARATION_SET_BINDING")
    require(terminal["owner_countersigned_attestation_set_receipt_sha256"] == expected_admitted_set_receipt_sha256, "E_EXECUTION_PREPARATION_ADMITTED_SET_BINDING")
    require(
        terminal["openssl_executable_sha256"] == challenge["target"]["openssl_executable_sha256"]
        and terminal["ssh_keygen_executable_sha256"] == challenge["target"]["ssh_keygen_executable_sha256"],
        "E_EXECUTION_PREPARATION_TOOL_BINDING",
    )
    endpoint, _endpoint_raw = read_canonical_json(endpoint_manifest_path, "E_ENDPOINT_MANIFEST")
    endpoint_schema, credential_schema, _message_schema = runtime.load_schemas()
    runtime.validate_endpoint_manifest(endpoint, endpoint_schema, source_commit, run_id)
    require(endpoint["content_sha256"] == terminal["private_endpoint_manifest_content_sha256"] == challenge["bindings"]["private_endpoint_manifest_content_sha256"], "E_EXECUTION_ENDPOINT_BINDING")
    credential, _credential_raw = read_canonical_json(credential_manifest_path, "E_CREDENTIAL_MANIFEST")
    planned_expiry = parse_time(challenge["target"]["planned_execution_expires_at"], "E_PREPARATION_PLANNED_EXPIRY")
    runtime.validate_credential_manifest(credential, credential_schema, source_commit, run_id, endpoint["content_sha256"], planned_expiry)
    require(credential["content_sha256"] == terminal["runtime_credential_manifest_content_sha256"], "E_EXECUTION_CREDENTIAL_BINDING")
    require(credential["coordinator_runtime_signing_key"]["public_key_sha256"] == terminal["coordinator_runtime_public_key_sha256"], "E_EXECUTION_COORDINATOR_KEY_BINDING")
    require(Path(challenge["target"]["private_endpoint_manifest_path"]).resolve(strict=False) == endpoint_manifest_path.resolve(strict=True), "E_EXECUTION_ENDPOINT_PATH_BINDING")
    require(Path(challenge["target"]["runtime_credential_manifest_output_path"]).resolve(strict=False) == credential_manifest_path.resolve(strict=True), "E_EXECUTION_CREDENTIAL_PATH_BINDING")
    return challenge, terminal, endpoint, credential, signature_sha256


def validate_budget_against_packets(budget: dict, packets: list[dict]) -> None:
    cloud = [packet for packet in packets if packet["host_identity"]["provider_kind"] == "CLOUD_VM"]
    if budget["mode"] == "THREE_OWNER_PHYSICAL_HOSTS_ZERO_SPEND":
        require(not cloud and budget["maximum_spend_usd_cents"] == 0, "E_EXECUTION_BUDGET_DOMAIN_MODE")
        return
    require(len(cloud) == 1 and budget["maximum_spend_usd_cents"] > 0, "E_EXECUTION_BUDGET_DOMAIN_MODE")
    host = cloud[0]["host_identity"]
    require(budget["region"] == host["region"] and budget["zone"] == host["zone"], "E_EXECUTION_CLOUD_LOCATION_BINDING")


def validate_runtime_readiness_evidence(
    readiness_bundle: Path,
    attestation_bundle: Path,
    source_commit: str,
    run_id: str,
    contract: dict,
    proposal: dict,
    admitted_set_receipt_sha256: str,
    endpoint: dict,
    credential: dict,
    preparation_terminal_sha256: str,
    now: datetime,
) -> dict:
    readiness = load_readiness_module()
    try:
        receipt = readiness.verify_bundle(
            readiness_bundle, attestation_bundle, source_commit, run_id,
            contract, proposal, admitted_set_receipt_sha256, endpoint,
            credential, preparation_terminal_sha256, now,
        )
    except RuntimeError as error:
        raise SafeFailure(str(error)) from error
    require(
        receipt["status"] == "THREE_DOMAIN_RUNTIME_READINESS_SET_VERIFIED_NON_EXECUTING"
        and receipt["source_commit"] == source_commit and receipt["run_id"] == run_id
        and receipt["owner_countersigned_attestation_set_receipt_sha256"] == admitted_set_receipt_sha256
        and receipt["private_endpoint_manifest_content_sha256"] == endpoint["content_sha256"]
        and receipt["runtime_credential_manifest_content_sha256"] == credential["content_sha256"]
        and receipt["runtime_preparation_terminal_receipt_sha256"] == preparation_terminal_sha256,
        "E_EXECUTION_READINESS_BINDING",
    )
    return receipt


def build_execution_contract(
    anchor: dict,
    contract: dict,
    proposal: dict,
    schema: dict,
    source_commit: str,
    issued_at: datetime,
    maximum_runtime_seconds: int,
    artifact_root: Path,
    fault_target_domain: str,
    budget: dict,
    admitted_receipt: dict,
    packets: list[dict],
    set_signature_sha256: str,
    preparation_challenge: dict,
    preparation_terminal: dict,
    endpoint: dict,
    credential: dict,
    preparation_signature_sha256: str,
    readiness_receipt: dict,
) -> dict:
    countersignature = load_countersignature_module()
    collection = countersignature.load_collection_module()
    foreign_call(collection.validate_anchor, anchor, proposal)
    require(0 < maximum_runtime_seconds <= 14400, "E_EXECUTION_MAXIMUM_RUNTIME")
    require(fault_target_domain in {"domain-2", "domain-3"}, "E_EXECUTION_FAULT_TARGET")
    validate_budget_against_packets(budget, packets)
    run_id = preparation_challenge["target"]["run_id"]
    planned_expiry = parse_time(preparation_challenge["target"]["planned_execution_expires_at"], "E_EXECUTION_PLANNED_EXPIRY")
    attestation_expiry = parse_time(admitted_receipt["earliest_attestation_expires_at"], "E_EXECUTION_ATTESTATION_EXPIRY")
    readiness_expiry = parse_time(readiness_receipt["earliest_readiness_expires_at"], "E_EXECUTION_READINESS_EXPIRY")
    expires = min(issued_at + timedelta(seconds=maximum_runtime_seconds), planned_expiry, attestation_expiry, readiness_expiry)
    require(issued_at < expires, "E_EXECUTION_EXPIRY_WINDOW")
    packet_by_id = {packet["domain_id"]: packet for packet in packets}
    require([domain["hostname"] for domain in endpoint["domains"]] == [packet_by_id[f"domain-{number}"]["host_identity"]["hostname"] for number in (1, 2, 3)], "E_EXECUTION_ENDPOINT_HOST_BINDING")
    packet_hash = {row["domain_id"]: row["attestation_sha256"] for row in admitted_receipt["packet_bindings"]}
    signatures = {row["domain_id"]: row for row in admitted_receipt["signature_bindings"]}
    preflight = collection.load_preflight_module()
    source_artifacts, source_artifact_set_sha256 = collect_source_artifacts()
    root = artifact_root.resolve(strict=False)
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.distributed_execution_contract.v1",
        "packet_kind": "T22_A1_H_FINAL_UNSIGNED_EXECUTION_CONTRACT",
        "hashing_contract": {
            "hash_algorithm": "SHA-256",
            "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
            "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/distributed-execution-contract/v1",
            "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256",
            "self_hash_field": "content_sha256",
            "self_hash_field_excluded": True,
            "detached_owner_signature_covers_complete_canonical_packet": True,
            "cross_field_semantic_validation_required": True,
        },
        "run_id": run_id,
        "source_commit": source_commit,
        "issued_at": utc_text(issued_at),
        "expires_at": utc_text(expires),
        "authorization": {
            "owner_id": "pallasting", "owner_role": "PROJECT_OWNER",
            "signature_scheme": "OPENSSH_SSHSIG_ED25519", "signature_namespace": SIGNATURE_NAMESPACE,
            "verified_unexpired_owner_signature_required": True,
            "exact_source_commit_required": True, "clean_tracked_tree_required": True,
            "one_run_per_authorization_content_sha256": True,
            "maximum_runtime_seconds": maximum_runtime_seconds, "automatic_retry_allowed": False,
        },
        "artifact_scope": {
            "private_artifact_root": str(root),
            "execution_admission_receipt_output_path": str(root / "admissions" / "final-execution-admission.json"),
            "run_evidence_root": str(root / "runs" / run_id),
            "repository_output_allowed": False, "directory_mode": "0700", "file_mode": "0600",
        },
        "admission_bindings": {
            "admission_contract_sha256": contract["contract_sha256"],
            "owner_decision_proposal_sha256": proposal["proposal_sha256"],
            "domain_attestation_schema_sha256": preflight.EXPECTED_SCHEMA_SHA256,
            "exact_three_domain_attestation_packet_set_sha256": admitted_receipt["attestation_set_sha256"],
            "attestation_set_countersignature_content_sha256": admitted_receipt["attestation_set_countersignature_content_sha256"],
            "owner_attestation_set_countersignature_signature_sha256": set_signature_sha256,
            "owner_countersigned_attestation_set_receipt_sha256": admitted_receipt["content_sha256"],
            "admission_bundle_reverification_receipt_sha256": admitted_receipt["admission_bundle_reverification_receipt_sha256"],
            "domain_bindings": [{
                "domain_id": domain_id,
                "attestation_packet_sha256": packet_hash[domain_id],
                "attestation_signature_sha256": signatures[domain_id]["signature_sha256"],
                "domain_public_key_sha256": signatures[domain_id]["public_key_sha256"],
            } for domain_id in ("domain-1", "domain-2", "domain-3")],
            "all_domain_attestation_signatures_verified": True,
            "all_domain_attestations_current": True,
            "all_domain_distinctness_checks_passed": True,
            "owner_countersignature_over_exact_packet_set_verified": True,
        },
        "budget": budget,
        "network": {
            "transport": "OWNER_MANAGED_PRIVATE_OVERLAY",
            "peer_endpoint_set_sha256": admitted_receipt["set_validation"]["peer_endpoint_set_sha256"],
            "acl_policy_receipt_sha256": admitted_receipt["set_validation"]["acl_policy_receipt_sha256"],
            "raw_endpoints_embedded": False, "overlay_credentials_embedded": False,
            "public_listeners_allowed": False, "host_global_firewall_or_route_mutation_allowed": False,
            "runner_provisions_or_joins_overlay": False,
        },
        "private_runtime": {
            "private_endpoint_manifest_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-private-endpoint-manifest-schema-v1.json",
            "private_endpoint_manifest_schema_sha256": preflight.EXPECTED_ENDPOINT_MANIFEST_SCHEMA_SHA256,
            "private_endpoint_manifest_content_sha256": endpoint["content_sha256"],
            "runtime_credential_manifest_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-runtime-credential-manifest-schema-v1.json",
            "runtime_credential_manifest_schema_sha256": preflight.EXPECTED_CREDENTIAL_MANIFEST_SCHEMA_SHA256,
            "runtime_credential_manifest_content_sha256": credential["content_sha256"],
            "runtime_preparation_challenge_content_sha256": preparation_challenge["content_sha256"],
            "runtime_preparation_owner_signature_sha256": preparation_signature_sha256,
            "runtime_preparation_terminal_receipt_sha256": preparation_terminal["content_sha256"],
            "runtime_preparation_verified_zero_network": True,
            "credential_verifier_openssl_executable_path": preparation_challenge["target"]["openssl_executable_path"],
            "credential_verifier_openssl_executable_sha256": preparation_terminal["openssl_executable_sha256"],
            "credential_verifier_ssh_keygen_executable_path": preparation_challenge["target"]["ssh_keygen_executable_path"],
            "credential_verifier_ssh_keygen_executable_sha256": preparation_terminal["ssh_keygen_executable_sha256"],
            "domain_agent_message_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-domain-agent-message-schema-v1.json",
            "domain_agent_message_schema_sha256": preflight.EXPECTED_AGENT_MESSAGE_SCHEMA_SHA256,
            "coordinator_runtime_public_key_sha256": preparation_terminal["coordinator_runtime_public_key_sha256"],
            "mutual_tls_required": True, "certificate_and_key_verification_required": True,
            "credentials_read_only_after_owner_signature": True, "domain_message_signatures_required": True,
            "agent_listeners_bind_exact_overlay_ip_only": True, "arbitrary_remote_shell_allowed": False,
            "raw_endpoint_or_credential_manifest_in_repository_or_receipts_allowed": False,
        },
        "runtime_admission": {
            "domain_runtime_readiness_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-domain-runtime-readiness-schema-v1.json",
            "domain_runtime_readiness_schema_sha256": preflight.EXPECTED_DOMAIN_RUNTIME_READINESS_SCHEMA_SHA256,
            "runtime_readiness_set_sha256": readiness_receipt["runtime_readiness_set_sha256"],
            "earliest_runtime_readiness_expires_at": readiness_receipt["earliest_readiness_expires_at"],
            "packet_bindings": readiness_receipt["packet_bindings"],
            "signature_bindings": readiness_receipt["signature_bindings"],
            "source_artifacts": source_artifacts,
            "source_artifact_set_sha256": source_artifact_set_sha256,
            "all_three_runtime_readiness_packets_current": True,
            "all_three_runtime_readiness_signatures_verified": True,
            "source_artifacts_rehashed_from_clean_source_commit": True,
            "live_runner_activation_required": True,
        },
        "topology": {
            "domains": [
                {"domain_id": "domain-1", "role": "COORDINATOR_VOTER", "etcd_member": "etcd-1", "openbao_member": "bao-1", "owned_process_count": 2},
                {"domain_id": "domain-2", "role": "PARTICIPANT_VOTER", "etcd_member": "etcd-2", "openbao_member": "bao-2", "owned_process_count": 2},
                {"domain_id": "domain-3", "role": "PARTICIPANT_VOTER", "etcd_member": "etcd-3", "openbao_member": "bao-3", "owned_process_count": 2},
            ],
            "etcd_voter_count": 3, "openbao_voter_count": 3,
            "coordinator_domain_id": "domain-1", "production_or_customer_data_allowed": False,
        },
        "fault": {
            "id": "ONE_DOMAIN_ALL_OWNED_CLUSTER_SERVICES_STOP_AND_RESTART",
            "target_domain_id": fault_target_domain,
            "target_selection": "OBSERVED_NON_COORDINATOR_VOTER_DOMAIN",
            "allowed_actions": ["OWNED_PROCESS_STOP", "OWNED_PROCESS_KILL_AFTER_TIMEOUT", "OWNED_PROCESS_RESTART"],
            "forbidden_actions": ["HOST_REBOOT", "HOST_POWER_OFF", "HOST_GLOBAL_IPTABLES_OR_TC", "BLOCK_DEVICE_MUTATION", "PROVIDER_INSTANCE_STOP"],
            "required_observation": "SURVIVING_TWO_DOMAINS_RETAIN_QUORUM_AND_VERIFY_PREFAULT_STATE_THEN_STOPPED_DOMAIN_REJOINS",
        },
        "evidence_contract": {
            "distributed_event_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-distributed-event-schema-v1.json",
            "distributed_event_schema_sha256": preflight.EXPECTED_EVENT_SCHEMA_SHA256,
            "terminal_evidence_schema_path": "docs/design/fixtures/biocortex-ab-track-b-t22-a1-terminal-evidence-schema-v1.json",
            "terminal_evidence_schema_sha256": preflight.EXPECTED_TERMINAL_SCHEMA_SHA256,
            "coordinator_hash_chain_required": True, "source_domain_detached_signatures_required": True,
            "per_domain_cleanup_receipts_required": True, "exact_secret_value_scan_required": True,
            "raw_credentials_endpoints_or_bootstrap_secrets_allowed": False,
        },
        "claims": {
            "maximum_success_claim": "THREE_DISTINCT_PHYSICAL_HOST_PLACEMENT_AND_ONE_HOST_SCOPED_OWNED_SERVICE_SET_LOSS_RECOVERY_NONPRODUCTION",
            "host_power_loss_proved": False, "site_power_network_independence_proved": False,
            "storage_device_durability_proved": False, "provider_durability_proved": False,
            "external_anti_rollback_proved": False, "production_admissible": False,
            "t22_a1_r_authorized": False,
        },
    }
    value["content_sha256"] = contract_digest(value)
    validate_execution_contract(value, schema, contract, proposal, source_commit, issued_at)
    return value


def verify_owner_signature(raw: bytes, signature_path: Path, public_key: bytes) -> str:
    require(signature_path.is_absolute() and signature_path.is_file() and not signature_path.is_symlink(), "E_EXECUTION_SIGNATURE_FILE")
    signature = signature_path.read_bytes()
    require(0 < len(signature) <= MAX_SIGNATURE_BYTES, "E_EXECUTION_SIGNATURE_FILE")
    ssh_keygen = shutil.which("ssh-keygen")
    require(ssh_keygen is not None, "E_SSH_KEYGEN_MISSING")
    with tempfile.TemporaryDirectory(prefix="t22-a1-execution-signature-") as directory:
        allowed = Path(directory) / "allowed_signers"
        allowed.write_bytes(b"pallasting " + public_key)
        allowed.chmod(0o600)
        result = subprocess.run(
            [ssh_keygen, "-Y", "verify", "-f", str(allowed), "-I", "pallasting", "-n", SIGNATURE_NAMESPACE, "-s", str(signature_path)],
            input=raw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C", "LC_ALL": "C"}, check=False,
        )
    require(result.returncode == 0, "E_EXECUTION_OWNER_SIGNATURE_INVALID")
    return hashlib.sha256(signature).hexdigest()


def ensure_private_directory(path: Path, create: bool) -> None:
    require(path.is_absolute() and not path.is_symlink(), "E_EXECUTION_PRIVATE_DIRECTORY")
    if not path.exists() and create:
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
        path.chmod(0o700)
    require(path.is_dir() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0, "E_EXECUTION_PRIVATE_DIRECTORY")


def write_exclusive(path: Path, raw: bytes) -> None:
    require(path.is_absolute() and not path.exists() and not path.is_symlink(), "E_EXECUTION_OUTPUT_EXISTS")
    ensure_private_directory(path.parent, create=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def reserve(root: Path, execution: dict, source_commit: str, now: datetime) -> Path:
    ensure_private_directory(root, create=False)
    uses = root / "final-execution-authorization-uses"
    ensure_private_directory(uses, create=True)
    reservation = uses / f"{execution['content_sha256']}.reserved.json"
    write_exclusive(reservation, canonical({
        "schema": "agent_bridge.biocortex.track_b.t22_a1.execution_authorization_reservation.v1",
        "status": "FINAL_OWNER_EXECUTION_AUTHORIZATION_RESERVED_SINGLE_ADMISSION",
        "run_id": execution["run_id"], "source_commit": source_commit,
        "execution_contract_sha256": execution["content_sha256"], "reserved_at": utc_text(now),
        "automatic_retry_allowed": False, "network_accessed": False,
        "services_started": 0, "faults_injected": 0, "production_admissible": False,
    }) + b"\n")
    return uses / f"{execution['content_sha256']}.terminal.json"


def verify_runtime_credential_files(execution: dict, endpoint: dict, credential: dict, material) -> dict:  # noqa: ANN001
    private = execution["private_runtime"]
    openssl = material.validate_tool(private["credential_verifier_openssl_executable_path"], private["credential_verifier_openssl_executable_sha256"], "E_EXECUTION_OPENSSL_BINDING")
    ssh_keygen = material.validate_tool(private["credential_verifier_ssh_keygen_executable_path"], private["credential_verifier_ssh_keygen_executable_sha256"], "E_EXECUTION_SSH_KEYGEN_BINDING")
    root = Path(execution["artifact_scope"]["private_artifact_root"])
    credentials_root = root / "credentials"
    ensure_private_directory(credentials_root, create=False)
    require({path.name for path in credentials_root.iterdir()} == material.EXPECTED_MATERIAL_NAMES, "E_EXECUTION_CREDENTIAL_FILE_SET")
    require(all(path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0 for path in credentials_root.iterdir()), "E_EXECUTION_CREDENTIAL_FILE_PERMISSIONS")
    exact_paths = {
        credential["ca"]["certificate_path"]: credentials_root / "ca.crt",
        credential["coordinator"]["certificate_path"]: credentials_root / "coordinator.crt",
        credential["coordinator"]["private_key_path"]: credentials_root / "coordinator.key",
        credential["coordinator_runtime_signing_key"]["public_key_path"]: credentials_root / "coordinator-runtime.pub",
        credential["coordinator_runtime_signing_key"]["private_key_path"]: credentials_root / "coordinator-runtime",
    }
    for number, row in enumerate(credential["domains"], 1):
        exact_paths[row["certificate_path"]] = credentials_root / f"domain-{number}.crt"
        exact_paths[row["private_key_path"]] = credentials_root / f"domain-{number}.key"
    require(all(Path(text).resolve(strict=True) == expected.resolve(strict=True) for text, expected in exact_paths.items()), "E_EXECUTION_CREDENTIAL_EXACT_PATH")
    ca = credentials_root / "ca.crt"
    require(material.sha256_file(ca, material.MAX_PRIVATE_JSON_BYTES, "E_CA_CERTIFICATE_FILE") == credential["ca"]["certificate_sha256"], "E_EXECUTION_CA_DIGEST")
    material.run_tool(openssl, ["verify", "-CAfile", str(ca), str(ca)], "E_EXECUTION_CA_SELF_VERIFY")
    ca_spki = hashlib.sha256(material.certificate_spki(openssl, ca)).hexdigest()
    require(ca_spki == credential["ca"]["spki_sha256"], "E_EXECUTION_CA_SPKI")
    endpoint_by_id = {row["domain_id"]: row for row in endpoint["domains"]}
    rows = [("coordinator", credential["coordinator"], None), *[(f"domain-{number}", credential["domains"][number - 1], endpoint_by_id[f"domain-{number}"]["overlay_ip"]) for number in (1, 2, 3)]]
    expiry = parse_time(execution["expires_at"], "E_EXECUTION_EXPIRES_AT")
    require(material.certificate_not_after(openssl, ca) >= expiry, "E_EXECUTION_CA_EXPIRY")
    for identity, row, overlay_ip in rows:
        observed = material.validate_leaf_certificate(
            openssl, ca, credentials_root / f"{identity}.crt", credentials_root / f"{identity}.key",
            row["extended_key_usage"], expiry, overlay_ip,
        )
        require(observed == {"certificate_sha256": row["certificate_sha256"], "spki_sha256": row["spki_sha256"], "not_after": row["not_after"]}, "E_EXECUTION_LEAF_BINDING")
    runtime_public = credentials_root / "coordinator-runtime.pub"
    runtime_private = credentials_root / "coordinator-runtime"
    public_raw = runtime_public.read_bytes()
    fields = public_raw.strip().split()
    require(len(fields) == 2 and fields[0] == b"ssh-ed25519" and public_raw == b" ".join(fields) + b"\n", "E_EXECUTION_RUNTIME_PUBLIC_KEY")
    require(hashlib.sha256(public_raw).hexdigest() == credential["coordinator_runtime_signing_key"]["public_key_sha256"] == private["coordinator_runtime_public_key_sha256"], "E_EXECUTION_RUNTIME_PUBLIC_KEY_BINDING")
    derived = material.run_tool(ssh_keygen, ["-y", "-f", str(runtime_private)], "E_EXECUTION_RUNTIME_PRIVATE_KEY")
    require(derived.strip().split()[:2] == fields, "E_EXECUTION_RUNTIME_KEY_MISMATCH")
    return {"certificate_count": 5, "private_key_count": 5, "all_credential_files_verified": True}


def write_terminal(path: Path, body: dict) -> dict:
    value = dict(body)
    value["content_sha256"] = digest(TERMINAL_DOMAIN, value)
    write_exclusive(path, canonical(value) + b"\n")
    return value


def validate_admission_receipt(value: object, execution: dict, now: datetime) -> dict:
    required = {
        "schema", "status", "run_id", "source_commit",
        "execution_contract_sha256", "owner_execution_signature_sha256",
        "owner_countersigned_attestation_set_receipt_sha256",
        "runtime_preparation_terminal_receipt_sha256",
        "private_endpoint_manifest_content_sha256",
        "runtime_credential_manifest_content_sha256",
        "coordinator_runtime_public_key_sha256",
        "runtime_readiness_set_verification_receipt_sha256",
        "runtime_readiness_set_sha256",
        "source_artifact_set_sha256",
        "all_three_domain_attestations_reverified_current",
        "all_three_runtime_readiness_packets_reverified_current",
        "all_three_runtime_readiness_signatures_reverified",
        "source_artifacts_rehashed_from_clean_source_commit",
        "owner_set_countersignature_reverified",
        "owner_runtime_preparation_signature_reverified",
        "owner_execution_signature_verified",
        "credential_files_read_only_after_owner_execution_signature",
        "certificate_count", "private_key_count", "all_credential_files_verified",
        "one_execution_per_admission_receipt", "automatic_retry_allowed",
        "raw_endpoint_or_credential_values_in_receipt", "network_accessed",
        "external_hosts_contacted", "listeners_started", "services_started",
        "faults_injected", "spend_usd_cents", "execution_authorized",
        "production_admissible", "expires_at", "admitted_at", "content_sha256",
    }
    require(isinstance(value, dict) and set(value) == required, "E_EXECUTION_ADMISSION_RECEIPT_SHAPE")
    assert isinstance(value, dict)
    require(value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.execution_admission_receipt.v1", "E_EXECUTION_ADMISSION_RECEIPT_SCHEMA")
    require(value["status"] == "AUTHORIZED_T22_A1_EXACT_OWNER_SIGNED_NONPRODUCTION_EXECUTION_ADMISSION", "E_EXECUTION_ADMISSION_RECEIPT_STATUS")
    require(value["run_id"] == execution["run_id"] and value["source_commit"] == execution["source_commit"], "E_EXECUTION_ADMISSION_RECEIPT_RUN")
    require(value["execution_contract_sha256"] == execution["content_sha256"], "E_EXECUTION_ADMISSION_RECEIPT_CONTRACT")
    attestation = load_countersignature_module().load_attestation_module()
    for field in (
        "owner_execution_signature_sha256", "owner_countersigned_attestation_set_receipt_sha256",
        "runtime_preparation_terminal_receipt_sha256", "private_endpoint_manifest_content_sha256",
        "runtime_credential_manifest_content_sha256", "coordinator_runtime_public_key_sha256",
        "runtime_readiness_set_verification_receipt_sha256", "source_artifact_set_sha256",
        "runtime_readiness_set_sha256",
    ):
        require(attestation.is_sha256(value[field]), "E_EXECUTION_ADMISSION_RECEIPT_DIGEST")
    require(all(value[field] is True for field in (
        "all_three_domain_attestations_reverified_current", "owner_set_countersignature_reverified",
        "all_three_runtime_readiness_packets_reverified_current",
        "all_three_runtime_readiness_signatures_reverified",
        "source_artifacts_rehashed_from_clean_source_commit",
        "owner_runtime_preparation_signature_reverified", "owner_execution_signature_verified",
        "credential_files_read_only_after_owner_execution_signature", "all_credential_files_verified",
        "one_execution_per_admission_receipt", "execution_authorized",
    )), "E_EXECUTION_ADMISSION_RECEIPT_VERIFICATION")
    require(
        value["runtime_readiness_set_sha256"] == execution["runtime_admission"]["runtime_readiness_set_sha256"]
        and value["source_artifact_set_sha256"] == execution["runtime_admission"]["source_artifact_set_sha256"],
        "E_EXECUTION_ADMISSION_RECEIPT_RUNTIME_BINDING",
    )
    require(value["certificate_count"] == value["private_key_count"] == 5, "E_EXECUTION_ADMISSION_RECEIPT_COUNTS")
    require(value["automatic_retry_allowed"] is False and value["raw_endpoint_or_credential_values_in_receipt"] is False, "E_EXECUTION_ADMISSION_RECEIPT_BOUNDARY")
    require(value["network_accessed"] is False and value["external_hosts_contacted"] == value["listeners_started"] == 0, "E_EXECUTION_ADMISSION_RECEIPT_NETWORK")
    require(value["services_started"] == value["faults_injected"] == value["spend_usd_cents"] == 0, "E_EXECUTION_ADMISSION_RECEIPT_SIDE_EFFECT")
    require(value["production_admissible"] is False, "E_EXECUTION_ADMISSION_RECEIPT_CLAIMS")
    admitted = parse_time(value["admitted_at"], "E_EXECUTION_ADMISSION_RECEIPT_TIME")
    expires = parse_time(value["expires_at"], "E_EXECUTION_ADMISSION_RECEIPT_EXPIRY")
    require(value["expires_at"] == execution["expires_at"] and admitted <= now < expires, "E_EXECUTION_ADMISSION_RECEIPT_NOT_CURRENT")
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256")
    require(claimed == digest(ADMISSION_RECEIPT_DOMAIN, unsigned), "E_EXECUTION_ADMISSION_RECEIPT_DIGEST")
    return value


def parse_admission_receipt(path: Path, execution: dict, now: datetime) -> dict:
    value, _raw = read_canonical_json(path, "E_EXECUTION_ADMISSION_RECEIPT")
    return validate_admission_receipt(value, execution, now)


def admit(
    execution_contract_path: Path,
    owner_signature_path: Path,
    source_commit: str,
    now: datetime,
    admitted_receipt_path: Path,
    countersignature_path: Path,
    countersignature_signature_path: Path,
    bundle: Path,
    preparation_challenge_path: Path,
    preparation_signature_path: Path,
    preparation_terminal_path: Path,
    endpoint_manifest_path: Path,
    credential_manifest_path: Path,
    readiness_bundle: Path,
) -> dict:
    require(EXECUTION_ACTIVATION_READY, "E_EXECUTION_ACTIVATION_NOT_READY")
    countersignature, collection, _attestation, runtime, _preparation, material, contract, proposal, schema = load_inputs()
    anchor = json.loads(collection.ANCHOR_PATH.read_text())
    public_key = foreign_call(collection.validate_anchor, anchor, proposal)
    execution, raw = read_canonical_json(execution_contract_path, "E_EXECUTION_CONTRACT")
    validate_execution_contract(execution, schema, contract, proposal, source_commit, now)
    owner_signature_sha256 = verify_owner_signature(raw, owner_signature_path, public_key)
    root = validate_artifact_scope(execution["artifact_scope"], execution["run_id"])
    output = Path(execution["artifact_scope"]["execution_admission_receipt_output_path"])
    require(not output.exists() and not output.is_symlink(), "E_EXECUTION_ADMISSION_OUTPUT_EXISTS")
    terminal_path = reserve(root, execution, source_commit, now)
    private_inputs_read = False
    credential_files_read = False
    output_written = False
    try:
        private_inputs_read = True
        admitted, _verification, packets, set_signature_sha256 = validate_set_evidence(
            admitted_receipt_path, countersignature_path, countersignature_signature_path,
            bundle, source_commit, now,
        )
        challenge, preparation_terminal, endpoint, credential, preparation_signature_sha256 = validate_runtime_preparation_evidence(
            preparation_challenge_path, preparation_signature_path, preparation_terminal_path,
            endpoint_manifest_path, credential_manifest_path, source_commit, now,
            admitted["attestation_set_sha256"], admitted["content_sha256"],
        )
        readiness_receipt = validate_runtime_readiness_evidence(
            readiness_bundle, bundle, source_commit, challenge["target"]["run_id"],
            contract, proposal, admitted["content_sha256"], endpoint, credential,
            preparation_terminal["content_sha256"], now,
        )
        expected = build_execution_contract(
            anchor, contract, proposal, schema, source_commit,
            parse_time(execution["issued_at"], "E_EXECUTION_ISSUED_AT"),
            execution["authorization"]["maximum_runtime_seconds"], root,
            execution["fault"]["target_domain_id"], execution["budget"], admitted,
            packets, set_signature_sha256, challenge,
            preparation_terminal, endpoint, credential, preparation_signature_sha256,
            readiness_receipt,
        )
        require(execution == expected, "E_EXECUTION_REBUILT_CONTRACT_MISMATCH")
        credential_files_read = True
        credential_verification = verify_runtime_credential_files(execution, endpoint, credential, material)
        receipt = {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.execution_admission_receipt.v1",
            "status": "AUTHORIZED_T22_A1_EXACT_OWNER_SIGNED_NONPRODUCTION_EXECUTION_ADMISSION",
            "run_id": execution["run_id"], "source_commit": source_commit,
            "execution_contract_sha256": execution["content_sha256"],
            "owner_execution_signature_sha256": owner_signature_sha256,
            "owner_countersigned_attestation_set_receipt_sha256": admitted["content_sha256"],
            "runtime_preparation_terminal_receipt_sha256": preparation_terminal["content_sha256"],
            "private_endpoint_manifest_content_sha256": endpoint["content_sha256"],
            "runtime_credential_manifest_content_sha256": credential["content_sha256"],
            "coordinator_runtime_public_key_sha256": execution["private_runtime"]["coordinator_runtime_public_key_sha256"],
            "runtime_readiness_set_verification_receipt_sha256": readiness_receipt["content_sha256"],
            "runtime_readiness_set_sha256": readiness_receipt["runtime_readiness_set_sha256"],
            "source_artifact_set_sha256": execution["runtime_admission"]["source_artifact_set_sha256"],
            "all_three_domain_attestations_reverified_current": True,
            "all_three_runtime_readiness_packets_reverified_current": True,
            "all_three_runtime_readiness_signatures_reverified": True,
            "source_artifacts_rehashed_from_clean_source_commit": True,
            "owner_set_countersignature_reverified": True,
            "owner_runtime_preparation_signature_reverified": True,
            "owner_execution_signature_verified": True,
            "credential_files_read_only_after_owner_execution_signature": True,
            **credential_verification,
            "one_execution_per_admission_receipt": True,
            "automatic_retry_allowed": False,
            "raw_endpoint_or_credential_values_in_receipt": False,
            "network_accessed": False, "external_hosts_contacted": 0,
            "listeners_started": 0, "services_started": 0, "faults_injected": 0,
            "spend_usd_cents": 0, "execution_authorized": True,
            "production_admissible": False, "expires_at": execution["expires_at"],
            "admitted_at": utc_text(now),
        }
        receipt["content_sha256"] = digest(ADMISSION_RECEIPT_DOMAIN, receipt)
        validate_admission_receipt(receipt, execution, now)
        write_exclusive(output, canonical(receipt) + b"\n")
        output_written = True
        write_terminal(terminal_path, {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.execution_admission_terminal.v1",
            "status": "PASS_T22_A1_FINAL_EXECUTION_ADMISSION_ZERO_NETWORK",
            "failure_code": None, "run_id": execution["run_id"], "source_commit": source_commit,
            "execution_contract_sha256": execution["content_sha256"],
            "execution_admission_receipt_sha256": receipt["content_sha256"],
            "owner_execution_signature_verified": True,
            "private_inputs_read_after_owner_signature": True,
            "credential_files_read_after_owner_signature": True,
            "network_accessed": False, "services_started": 0, "faults_injected": 0,
            "automatic_retry_allowed": False, "production_admissible": False,
            "completed_at": utc_text(now),
        })
        return receipt
    except (RuntimeError, OSError) as error:
        failure_code = str(error) if isinstance(error, RuntimeError) else "E_EXECUTION_ADMISSION_LOCAL_IO"
        if output_written and output.is_file() and not output.is_symlink():
            output.unlink()
        if not terminal_path.exists():
            write_terminal(terminal_path, {
                "schema": "agent_bridge.biocortex.track_b.t22_a1.execution_admission_terminal.v1",
                "status": "FAIL_T22_A1_FINAL_EXECUTION_ADMISSION_NO_RETRY",
                "failure_code": failure_code, "run_id": execution["run_id"], "source_commit": source_commit,
                "execution_contract_sha256": execution["content_sha256"],
                "owner_execution_signature_verified": True,
                "private_inputs_read_after_owner_signature": private_inputs_read,
                "credential_files_read_after_owner_signature": credential_files_read,
                "network_accessed": False, "services_started": 0, "faults_injected": 0,
                "automatic_retry_allowed": False, "production_admissible": False,
                "completed_at": utc_text(now),
            })
        raise SafeFailure(failure_code) from error


def require_clean_tracked_tree() -> str:
    for arguments in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        result = subprocess.run(arguments, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        require(result.returncode == 0, "E_EXECUTION_TRACKED_TREE_DIRTY")
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    source_commit = result.stdout.strip()
    require(result.returncode == 0 and len(source_commit) == 40 and all(character in "0123456789abcdef" for character in source_commit), "E_EXECUTION_SOURCE_COMMIT")
    return source_commit


def status() -> dict:
    countersignature, collection, _attestation, _runtime, _preparation, _material, _contract, proposal, _schema = load_inputs()
    present = collection.ANCHOR_PATH.is_file() and not collection.ANCHOR_PATH.is_symlink()
    valid = False
    if present:
        try:
            collection.validate_anchor(json.loads(collection.ANCHOR_PATH.read_text()), proposal)
            valid = True
        except (RuntimeError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            valid = False
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.execution_authorization_status.v0",
        "status": "BLOCKED_T22_A1_RUNNER_HOST_READINESS_AND_CREDENTIAL_PLACEMENT_REQUIRED" if not EXECUTION_ACTIVATION_READY else (
            "BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_REQUIRED" if not present else (
                "BLOCKED_FINAL_PRIVATE_EVIDENCE_AND_EXACT_OWNER_EXECUTION_SIGNATURE_REQUIRED" if valid
                else "BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_INVALID"
            )
        ),
        "execution_activation_ready": EXECUTION_ACTIVATION_READY,
        "owner_trust_anchor_present": present, "owner_trust_anchor_valid": valid,
        "private_evidence_read": False, "credential_files_read": False,
        "network_accessed": False, "external_hosts_contacted": 0,
        "listeners_started": 0, "services_started": 0, "faults_injected": 0,
        "spend_usd_cents": 0, "execution_authorized": False,
        "production_admissible": False,
    }


def budget_from_arguments(arguments) -> dict:  # noqa: ANN001
    if arguments.budget_mode == "THREE_OWNER_PHYSICAL_HOSTS_ZERO_SPEND":
        require(
            arguments.provider is None and arguments.region is None
            and arguments.zone is None and arguments.instance_type is None
            and arguments.maximum_spend_usd_cents == 0,
            "E_EXECUTION_PHYSICAL_BUDGET_ARGUMENTS",
        )
        return {
            "mode": arguments.budget_mode, "provider": None, "region": None,
            "zone": None, "instance_type": None, "maximum_spend_usd_cents": 0,
        }
    require(
        all(isinstance(value, str) and value for value in (
            arguments.provider, arguments.region, arguments.zone, arguments.instance_type,
        )) and isinstance(arguments.maximum_spend_usd_cents, int)
        and 0 < arguments.maximum_spend_usd_cents <= 100000,
        "E_EXECUTION_CLOUD_BUDGET_ARGUMENTS",
    )
    return {
        "mode": arguments.budget_mode, "provider": arguments.provider,
        "region": arguments.region, "zone": arguments.zone,
        "instance_type": arguments.instance_type,
        "maximum_spend_usd_cents": arguments.maximum_spend_usd_cents,
    }


def add_private_evidence_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--admitted-attestation-set-receipt", type=Path, required=True)
    parser.add_argument("--attestation-set-countersignature", type=Path, required=True)
    parser.add_argument("--attestation-set-countersignature-signature", type=Path, required=True)
    parser.add_argument("--attestation-bundle", type=Path, required=True)
    parser.add_argument("--runtime-preparation-challenge", type=Path, required=True)
    parser.add_argument("--runtime-preparation-signature", type=Path, required=True)
    parser.add_argument("--runtime-preparation-terminal", type=Path, required=True)
    parser.add_argument("--private-endpoint-manifest", type=Path, required=True)
    parser.add_argument("--runtime-credential-manifest", type=Path, required=True)
    parser.add_argument("--runtime-readiness-bundle", type=Path, required=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    generate = commands.add_parser("generate")
    add_private_evidence_arguments(generate)
    generate.add_argument("--artifact-root", type=Path, required=True)
    generate.add_argument("--fault-target-domain", choices=("domain-2", "domain-3"), required=True)
    generate.add_argument("--maximum-runtime-seconds", type=int, default=14400)
    generate.add_argument(
        "--budget-mode",
        choices=("THREE_OWNER_PHYSICAL_HOSTS_ZERO_SPEND", "EXACT_OWNER_AUTHORIZED_CLOUD_VM"),
        required=True,
    )
    generate.add_argument("--provider")
    generate.add_argument("--region")
    generate.add_argument("--zone")
    generate.add_argument("--instance-type")
    generate.add_argument("--maximum-spend-usd-cents", type=int, required=True)
    generate.add_argument("--out", type=Path, required=True)
    admission_parser = commands.add_parser("admit")
    add_private_evidence_arguments(admission_parser)
    admission_parser.add_argument("--execution-contract", type=Path, required=True)
    admission_parser.add_argument("--owner-execution-signature", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "status":
        print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
        return
    countersignature, collection, _attestation, _runtime, _preparation, _material, contract, proposal, schema = load_inputs()
    require(collection.ANCHOR_PATH.is_file() and not collection.ANCHOR_PATH.is_symlink(), "E_OWNER_ANCHOR_REQUIRED")
    try:
        anchor = json.loads(collection.ANCHOR_PATH.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SafeFailure("E_OWNER_ANCHOR_FILE") from error
    foreign_call(collection.validate_anchor, anchor, proposal)
    source_commit = require_clean_tracked_tree()
    now = datetime.now(timezone.utc)
    if arguments.command == "generate":
        require(EXECUTION_ACTIVATION_READY, "E_EXECUTION_ACTIVATION_NOT_READY")
        admitted, _verification, packets, set_signature_sha256 = validate_set_evidence(
            arguments.admitted_attestation_set_receipt.resolve(strict=True),
            arguments.attestation_set_countersignature.resolve(strict=True),
            arguments.attestation_set_countersignature_signature.resolve(strict=True),
            arguments.attestation_bundle.resolve(strict=True), source_commit, now,
        )
        challenge, terminal, endpoint, credential, preparation_signature_sha256 = validate_runtime_preparation_evidence(
            arguments.runtime_preparation_challenge.resolve(strict=True),
            arguments.runtime_preparation_signature.resolve(strict=True),
            arguments.runtime_preparation_terminal.resolve(strict=True),
            arguments.private_endpoint_manifest.resolve(strict=True),
            arguments.runtime_credential_manifest.resolve(strict=True),
            source_commit, now, admitted["attestation_set_sha256"], admitted["content_sha256"],
        )
        readiness_receipt = validate_runtime_readiness_evidence(
            arguments.runtime_readiness_bundle.resolve(strict=True),
            arguments.attestation_bundle.resolve(strict=True), source_commit,
            challenge["target"]["run_id"], contract, proposal,
            admitted["content_sha256"], endpoint, credential,
            terminal["content_sha256"], now,
        )
        artifact_root = arguments.artifact_root.resolve(strict=True)
        require(
            artifact_root == Path(challenge["target"]["private_artifact_root"]).resolve(strict=True),
            "E_EXECUTION_ARTIFACT_PREPARATION_BINDING",
        )
        execution = build_execution_contract(
            anchor, contract, proposal, schema, source_commit, now,
            arguments.maximum_runtime_seconds, artifact_root,
            arguments.fault_target_domain, budget_from_arguments(arguments), admitted,
            packets, set_signature_sha256, challenge, terminal,
            endpoint, credential, preparation_signature_sha256,
            readiness_receipt,
        )
        expected_output = artifact_root / "authorizations" / "final-execution-contract.json"
        require(arguments.out.is_absolute() and arguments.out.resolve(strict=False) == expected_output, "E_EXECUTION_CONTRACT_OUTPUT_PATH")
        write_exclusive(arguments.out, canonical(execution) + b"\n")
        print(json.dumps({
            "status": "FINAL_EXECUTION_CONTRACT_GENERATED_AWAITING_EXACT_OWNER_SIGNATURE",
            "execution_contract_path": str(arguments.out),
            "content_sha256": execution["content_sha256"],
            "expires_at": execution["expires_at"],
            "signature_namespace": SIGNATURE_NAMESPACE,
            "credential_files_read": False, "network_accessed": False,
            "execution_authorized": False, "production_admissible": False,
        }, sort_keys=True, separators=(",", ":")))
        return
    receipt = admit(
        arguments.execution_contract.resolve(strict=True),
        arguments.owner_execution_signature.resolve(strict=True), source_commit, now,
        arguments.admitted_attestation_set_receipt.resolve(strict=True),
        arguments.attestation_set_countersignature.resolve(strict=True),
        arguments.attestation_set_countersignature_signature.resolve(strict=True),
        arguments.attestation_bundle.resolve(strict=True),
        arguments.runtime_preparation_challenge.resolve(strict=True),
        arguments.runtime_preparation_signature.resolve(strict=True),
        arguments.runtime_preparation_terminal.resolve(strict=True),
        arguments.private_endpoint_manifest.resolve(strict=True),
        arguments.runtime_credential_manifest.resolve(strict=True),
        arguments.runtime_readiness_bundle.resolve(strict=True),
    )
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except SafeFailure as error:
        print(json.dumps({"status": "BLOCKED_FAIL_CLOSED", "failure_code": str(error)}, sort_keys=True, separators=(",", ":")))
        sys.exit(1)
