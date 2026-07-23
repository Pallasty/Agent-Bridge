"""Exact non-production coordinator/domain launch binding for T22-A1.

Both roles independently verify the final owner signature and execution-
admission receipt before reading host-local runtime inputs.  Each domain then
reserves its exact admission before opening one listener.  The coordinator
uses the existing consumer reservation and loads endpoints, readiness packets,
public peer material and credentials only inside the post-reservation runner
callback.  All live activation constants remain closed in committed source.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import ssl
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
CONSUMER_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_execution_consumer_v1.py"
RUNTIME_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_private_runtime_contracts_v1.py"
READINESS_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_runtime_readiness_v1.py"
PLAN_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_workload_plan_v1.py"
RUNNER_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_source_bound_runner_v1.py"
LANE_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_authenticated_domain_lane_v1.py"
FINALIZER_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_exact_evidence_finalizer_v1.py"
DOMAIN_IDS = ("domain-1", "domain-2", "domain-3")
MAX_JSON_BYTES = 256 * 1024
EXACT_LAUNCH_BINDING_ACTIVATION_READY = False
_MODULES: dict[str, object] = {}


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


def load_module(key: str, source: Path):
    if key not in _MODULES:
        spec = importlib.util.spec_from_file_location(f"t22a1_{key}_for_exact_launch", source)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _MODULES[key] = module
    return _MODULES[key]


def load_consumer_module():
    return load_module("consumer", CONSUMER_SOURCE)


def load_runtime_module():
    return load_module("runtime", RUNTIME_SOURCE)


def load_readiness_module():
    return load_module("readiness", READINESS_SOURCE)


def load_plan_module():
    return load_module("plan", PLAN_SOURCE)


def load_runner_module():
    return load_module("runner", RUNNER_SOURCE)


def load_lane_module():
    return load_module("lane", LANE_SOURCE)


def load_finalizer_module():
    return load_module("finalizer", FINALIZER_SOURCE)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def is_sha256(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and value != "0" * 64
        and all(character in "0123456789abcdef" for character in value)
    )


def utc_text(value: datetime) -> str:
    require(value.tzinfo is not None and value.utcoffset().total_seconds() == 0, "E_EXACT_LAUNCH_TIMEZONE")
    return value.isoformat().replace("+00:00", "Z")


def ensure_private_directory(path: Path, create: bool = False) -> None:
    require(path.is_absolute() and not path.is_symlink(), "E_EXACT_LAUNCH_PRIVATE_DIRECTORY")
    if create and not path.exists():
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
        path.chmod(0o700)
    require(
        path.is_dir() and not path.is_symlink()
        and path.stat().st_uid == os.geteuid()
        and stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
        "E_EXACT_LAUNCH_PRIVATE_DIRECTORY",
    )


def write_exclusive(path: Path, value: dict) -> None:
    require(path.is_absolute() and not path.exists() and not path.is_symlink(), "E_EXACT_LAUNCH_RESERVATION_EXISTS")
    ensure_private_directory(path.parent)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def require_activation_chain(role: str) -> None:
    require(EXACT_LAUNCH_BINDING_ACTIVATION_READY, "E_EXACT_LAUNCH_ACTIVATION_NOT_READY")
    require(role in {"COORDINATOR", "DOMAIN_AGENT"}, "E_EXACT_LAUNCH_ROLE")
    runner = load_runner_module()
    lane = load_lane_module()
    finalizer = load_finalizer_module()
    transport = lane.load_transport_module()
    executor = lane.load_executor_module()
    backend = lane.load_backend_module()
    compiler = finalizer.load_compiler_module()
    writer = finalizer.load_writer_module()
    require(
        runner.RUNNER_ACTIVATION_READY
        and lane.AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY
        and transport.TRANSPORT_ACTIVATION_READY
        and transport.SOCKET_ADAPTER_ACTIVATION_READY
        and executor.EXECUTOR_ACTIVATION_READY
        and backend.LIVE_LOCAL_BACKEND_ACTIVATION_READY
        and finalizer.EXACT_EVIDENCE_FINALIZER_ACTIVATION_READY
        and compiler.EVIDENCE_ACTIVATION_READY
        and writer.EVIDENCE_WRITER_ACTIVATION_READY,
        "E_EXACT_LAUNCH_COMPONENT_ACTIVATION_NOT_READY",
    )


def current_clean_source_commit() -> str:
    for arguments in (("git", "diff", "--quiet"), ("git", "diff", "--cached", "--quiet")):
        result = subprocess.run(arguments, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        require(result.returncode == 0, "E_EXACT_LAUNCH_TRACKED_TREE_DIRTY")
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    value = result.stdout.strip()
    require(result.returncode == 0 and len(value) == 40 and all(character in "0123456789abcdef" for character in value), "E_EXACT_LAUNCH_SOURCE_COMMIT")
    return value


def authorize_role(
    execution_contract_path: Path,
    owner_signature_path: Path,
    admission_receipt_path: Path,
    source_commit: str,
    now: datetime,
) -> tuple[dict, dict, str]:
    require(EXACT_LAUNCH_BINDING_ACTIVATION_READY, "E_EXACT_LAUNCH_ACTIVATION_NOT_READY")
    consumer = load_consumer_module()
    return foreign_call(
        consumer.verify_execution_authorization,
        execution_contract_path, owner_signature_path, admission_receipt_path,
        source_commit, now,
    )


def read_endpoint_manifest(path: Path, execution: dict) -> dict:
    consumer = load_consumer_module()
    execution_module = consumer.load_execution_module()
    endpoint, _raw = foreign_call(execution_module.read_canonical_json, path, "E_EXACT_LAUNCH_ENDPOINT")
    runtime = load_runtime_module()
    endpoint_schema, _credential_schema, _message_schema = runtime.load_schemas()
    foreign_call(
        runtime.validate_endpoint_manifest,
        endpoint, endpoint_schema, execution["source_commit"], execution["run_id"],
    )
    require(
        endpoint["content_sha256"] == execution["private_runtime"]["private_endpoint_manifest_content_sha256"],
        "E_EXACT_LAUNCH_ENDPOINT_BINDING",
    )
    return endpoint


def validate_readiness_launch_binding(
    packet: dict,
    packet_raw: bytes,
    signature_path: Path,
    public_key_path: Path,
    domain_id: str,
    execution: dict,
    endpoint: dict,
    now: datetime,
) -> dict:
    require(domain_id in DOMAIN_IDS, "E_EXACT_LAUNCH_DOMAIN")
    require(now.tzinfo is not None and now.utcoffset().total_seconds() == 0, "E_EXACT_LAUNCH_TIMEZONE")
    runtime_admission = execution.get("runtime_admission", {})
    packet_bindings = {row["domain_id"]: row for row in runtime_admission.get("packet_bindings", [])}
    signature_bindings = {row["domain_id"]: row for row in runtime_admission.get("signature_bindings", [])}
    admission_bindings = {row["domain_id"]: row for row in execution.get("admission_bindings", {}).get("domain_bindings", [])}
    require(
        set(packet_bindings) == set(signature_bindings) == set(admission_bindings) == set(DOMAIN_IDS),
        "E_EXACT_LAUNCH_READINESS_SET",
    )
    required = {
        "source_commit", "run_id", "domain_id", "content_sha256", "collected_at", "expires_at",
        "bindings", "endpoint_binding", "local_paths", "credential_placement", "signature_binding",
    }
    require(isinstance(packet, dict) and required <= set(packet), "E_EXACT_LAUNCH_READINESS_SHAPE")
    readiness = load_readiness_module()
    unsigned = dict(packet)
    claimed = unsigned.pop("content_sha256")
    require(
        is_sha256(claimed) and claimed == readiness.digest(unsigned)
        and packet_raw == readiness.canonical(packet) + b"\n",
        "E_EXACT_LAUNCH_READINESS_DIGEST",
    )
    require(
        packet["source_commit"] == execution["source_commit"]
        and packet["run_id"] == execution["run_id"]
        and packet["domain_id"] == domain_id
        and claimed == packet_bindings[domain_id]["readiness_packet_sha256"],
        "E_EXACT_LAUNCH_READINESS_BINDING",
    )
    expiry = foreign_call(readiness.parse_time, packet["expires_at"], "E_EXACT_LAUNCH_READINESS_EXPIRY")
    execution_expiry = foreign_call(readiness.parse_time, execution["expires_at"], "E_EXACT_LAUNCH_EXECUTION_EXPIRY")
    require(now < execution_expiry <= expiry, "E_EXACT_LAUNCH_READINESS_CURRENT")
    endpoint_rows = {row["domain_id"]: row for row in endpoint.get("domains", [])}
    require(set(endpoint_rows) == set(DOMAIN_IDS), "E_EXACT_LAUNCH_ENDPOINT_SET")
    expected_endpoint = endpoint_rows[domain_id]
    require(
        all(packet["endpoint_binding"].get(key) == expected_endpoint[key] for key in (
            "overlay_ip", "agent_control_port", "etcd_client_port", "etcd_peer_port",
            "openbao_api_port", "openbao_cluster_port",
        )),
        "E_EXACT_LAUNCH_READINESS_ENDPOINT",
    )
    bindings = packet["bindings"]
    require(
        bindings.get("domain_attestation_packet_sha256") == admission_bindings[domain_id]["attestation_packet_sha256"]
        and bindings.get("private_endpoint_manifest_content_sha256") == endpoint["content_sha256"]
        and bindings.get("runtime_credential_manifest_content_sha256") == execution["private_runtime"]["runtime_credential_manifest_content_sha256"],
        "E_EXACT_LAUNCH_READINESS_UPSTREAM",
    )
    expected_public_key_sha256 = admission_bindings[domain_id]["domain_public_key_sha256"]
    require(
        packet["signature_binding"].get("signer_public_key_sha256") == expected_public_key_sha256,
        "E_EXACT_LAUNCH_READINESS_KEY",
    )
    require(
        signature_path.is_absolute() and signature_path.is_file() and not signature_path.is_symlink(),
        "E_EXACT_LAUNCH_READINESS_SIGNATURE_FILE",
    )
    signature_metadata = signature_path.stat()
    require(
        stat.S_ISREG(signature_metadata.st_mode) and signature_metadata.st_uid == os.geteuid()
        and signature_metadata.st_mode & 0o077 == 0
        and 0 < signature_metadata.st_size <= 64 * 1024,
        "E_EXACT_LAUNCH_READINESS_SIGNATURE_FILE",
    )
    signature_raw = signature_path.read_bytes()
    tool_rows = {row.get("name"): row for row in packet.get("toolchain", {}).get("executables", [])}
    require("ssh-keygen" in tool_rows, "E_EXACT_LAUNCH_READINESS_TOOL")
    tool_row = tool_rows["ssh-keygen"]
    sshsig = load_lane_module().SshSigTool(tool_row.get("path"), tool_row.get("sha256"))
    public_key = foreign_call(sshsig.read_public_key, public_key_path, expected_public_key_sha256)
    signature = {
        "public_key_sha256": expected_public_key_sha256,
        "signature_sha256": foreign_call(
            sshsig.verify, packet_raw, signature_raw, public_key,
            domain_id, readiness.SIGNATURE_NAMESPACE,
        ),
    }
    require(
        signature["signature_sha256"] == signature_bindings[domain_id]["signature_sha256"]
        and signature["public_key_sha256"] == signature_bindings[domain_id]["public_key_sha256"],
        "E_EXACT_LAUNCH_READINESS_SIGNATURE",
    )
    return packet


def read_readiness_packet(
    packet_path: Path,
    signature_path: Path,
    public_key_path: Path,
    domain_id: str,
    execution: dict,
    endpoint: dict,
    now: datetime,
) -> dict:
    readiness = load_readiness_module()
    packet, packet_raw = foreign_call(readiness.read_canonical_packet, packet_path)
    return validate_readiness_launch_binding(
        packet, packet_raw, signature_path, public_key_path,
        domain_id, execution, endpoint, now,
    )


def reserve_domain_launch(execution: dict, admission: dict, readiness: dict, now: datetime) -> Path:
    root = Path(readiness["local_paths"]["execution_reservation_dir"])
    ensure_private_directory(root)
    stem = admission["content_sha256"]
    reservation = root / f"{stem}.domain-agent.reserved.json"
    terminal = root / f"{stem}.domain-agent.terminal.json"
    write_exclusive(reservation, {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_launch_reservation.v1",
        "status": "EXACT_DOMAIN_AGENT_LAUNCH_RESERVED_SINGLE_USE",
        "domain_id": readiness["domain_id"], "run_id": execution["run_id"],
        "source_commit": execution["source_commit"],
        "execution_contract_sha256": execution["content_sha256"],
        "execution_admission_receipt_sha256": admission["content_sha256"],
        "readiness_packet_sha256": readiness["content_sha256"],
        "reserved_at": utc_text(now), "automatic_retry_allowed": False,
        "production_admissible": False,
    })
    return terminal


def write_domain_terminal(
    terminal_path: Path,
    execution: dict,
    admission: dict,
    readiness: dict,
    status: str,
    failure_code: str | None,
    cleanup: dict,
    now: datetime,
) -> dict:
    value = {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_launch_terminal.v1",
        "status": status, "failure_code": failure_code,
        "domain_id": readiness["domain_id"], "run_id": execution["run_id"],
        "source_commit": execution["source_commit"],
        "execution_contract_sha256": execution["content_sha256"],
        "execution_admission_receipt_sha256": admission["content_sha256"],
        "readiness_packet_sha256": readiness["content_sha256"],
        "all_owned_processes_cleaned": cleanup.get("all_owned_processes_cleaned") is True,
        "all_owned_ports_released": cleanup.get("all_owned_ports_released") is True,
        "automatic_retry_allowed": False, "production_admissible": False,
        "completed_at": utc_text(now),
    }
    write_exclusive(terminal_path, value)
    return value


def serve_domain_agent(
    domain_id: str,
    execution_contract_path: Path,
    owner_signature_path: Path,
    admission_receipt_path: Path,
    endpoint_manifest_path: Path,
    readiness_packet_path: Path,
    readiness_signature_path: Path,
    source_commit: str,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict:
    require_activation_chain("DOMAIN_AGENT")
    now = clock()
    execution, admission, _owner_signature_sha256 = authorize_role(
        execution_contract_path, owner_signature_path, admission_receipt_path,
        source_commit, now,
    )
    endpoint = read_endpoint_manifest(endpoint_manifest_path, execution)
    # The host-local readiness packet itself selects its already-admitted
    # operator public key; no ambient key discovery is permitted.
    readiness_module = load_readiness_module()
    packet, packet_raw = foreign_call(readiness_module.read_canonical_packet, readiness_packet_path)
    public_key_path = Path(packet.get("credential_placement", {}).get("domain_operator_public_key_path", ""))
    readiness = validate_readiness_launch_binding(
        packet, packet_raw, readiness_signature_path, public_key_path,
        domain_id, execution, endpoint, now,
    )
    terminal_path = reserve_domain_launch(execution, admission, readiness, now)
    cleanup = {"all_owned_processes_cleaned": False, "all_owned_ports_released": False}
    failure_code: str | None = None
    succeeded = False
    try:
        lane = load_lane_module()
        plan = foreign_call(load_plan_module().build_plan, execution, endpoint, readiness)
        placement = readiness["credential_placement"]
        coordinator_public_key_path = Path(placement["coordinator_trust_material"]["runtime_public_key_path"])
        domain_public_key_path = Path(placement["domain_operator_public_key_path"])
        domain_private_key_path = Path(placement["domain_operator_private_key_path"])
        core = foreign_call(
            lane.build_live_domain_core,
            plan, execution, endpoint, readiness,
            coordinator_public_key_path, domain_public_key_path,
            domain_private_key_path, clock,
        )
        server = lane.DomainAgentServer(plan, lane.coordinator_route_plan(plan, endpoint), core, clock)
        cleanup = server.serve()
        succeeded = (
            core.session.state == "TERMINAL_SUCCEEDED"
            and cleanup == {"all_owned_processes_cleaned": True, "all_owned_ports_released": True}
        )
        if not succeeded:
            failure_code = "E_EXACT_LAUNCH_DOMAIN_AGENT_FAILED"
    except Exception as error:
        failure_code = str(error) if isinstance(error, RuntimeError) and str(error).startswith("E_") else "E_EXACT_LAUNCH_DOMAIN_AGENT_LOCAL_FAILURE"
    status = "PASS_T22_A1_DOMAIN_AGENT_TERMINAL" if succeeded else "FAIL_T22_A1_DOMAIN_AGENT_NO_RETRY"
    terminal = write_domain_terminal(
        terminal_path, execution, admission, readiness,
        status, failure_code, cleanup, clock(),
    )
    require(succeeded, failure_code or "E_EXACT_LAUNCH_DOMAIN_AGENT_FAILED")
    return terminal


def read_credential_manifest(path: Path, execution: dict) -> dict:
    consumer = load_consumer_module()
    execution_module = consumer.load_execution_module()
    credential, _raw = foreign_call(execution_module.read_canonical_json, path, "E_EXACT_LAUNCH_CREDENTIAL")
    runtime = load_runtime_module()
    _endpoint_schema, credential_schema, _message_schema = runtime.load_schemas()
    foreign_call(
        runtime.validate_credential_manifest,
        credential, credential_schema, execution["source_commit"], execution["run_id"],
        execution["private_runtime"]["private_endpoint_manifest_content_sha256"],
        foreign_call(runtime.parse_time, execution["expires_at"], "E_EXACT_LAUNCH_EXECUTION_EXPIRY"),
    )
    require(
        credential["content_sha256"] == execution["private_runtime"]["runtime_credential_manifest_content_sha256"],
        "E_EXACT_LAUNCH_CREDENTIAL_BINDING",
    )
    return credential


def certificate_der_sha256(path: Path, expected_file_sha256: str) -> str:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "E_EXACT_LAUNCH_PEER_CERTIFICATE")
    metadata = path.stat()
    require(
        stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.geteuid()
        and metadata.st_mode & 0o077 == 0 and 0 < metadata.st_size <= MAX_JSON_BYTES,
        "E_EXACT_LAUNCH_PEER_CERTIFICATE",
    )
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_file_sha256, "E_EXACT_LAUNCH_PEER_CERTIFICATE")
    try:
        der = ssl.PEM_cert_to_DER_cert(raw.decode("ascii"))
    except (UnicodeError, ValueError) as error:
        raise SafeFailure("E_EXACT_LAUNCH_PEER_CERTIFICATE") from error
    require(isinstance(der, bytes) and der, "E_EXACT_LAUNCH_PEER_CERTIFICATE")
    return hashlib.sha256(der).hexdigest()


def coordinator_runner(
    execution: dict,
    admission: dict,
    endpoint_manifest_path: Path,
    readiness_bundle: Path,
    attestation_bundle: Path,
    credential_manifest_path: Path,
    clock: Callable[[], datetime],
) -> dict:
    """Post-consumer-reservation callback; this is the first runtime input read."""
    require_activation_chain("COORDINATOR")
    endpoint = read_endpoint_manifest(endpoint_manifest_path, execution)
    require(readiness_bundle.is_absolute() and readiness_bundle.is_dir() and not readiness_bundle.is_symlink(), "E_EXACT_LAUNCH_READINESS_BUNDLE")
    require(attestation_bundle.is_absolute() and attestation_bundle.is_dir() and not attestation_bundle.is_symlink(), "E_EXACT_LAUNCH_ATTESTATION_BUNDLE")
    ensure_private_directory(readiness_bundle)
    ensure_private_directory(attestation_bundle)
    require(
        {path.name for path in readiness_bundle.iterdir()}
        == {f"{domain_id}{suffix}" for domain_id in DOMAIN_IDS for suffix in (".json", ".json.sig")},
        "E_EXACT_LAUNCH_READINESS_FILE_SET",
    )
    readiness_packets = [
        read_readiness_packet(
            readiness_bundle / f"{domain_id}.json",
            readiness_bundle / f"{domain_id}.json.sig",
            attestation_bundle / f"{domain_id}.pub",
            domain_id, execution, endpoint, clock(),
        )
        for domain_id in DOMAIN_IDS
    ]
    credential = read_credential_manifest(credential_manifest_path, execution)
    expected_domain_der = {
        row["domain_id"]: certificate_der_sha256(Path(row["certificate_path"]), row["certificate_sha256"])
        for row in credential["domains"]
    }
    require(set(expected_domain_der) == set(DOMAIN_IDS), "E_EXACT_LAUNCH_DOMAIN_CERTIFICATE_SET")
    plan_module = load_plan_module()
    coordinator_plan = foreign_call(plan_module.build_plan, execution, endpoint, readiness_packets[0])
    lane_module = load_lane_module()
    bootstrap_store = lane_module.CoordinatorBootstrapStore()
    collector = lane_module.EvidenceCollector(execution["fault"]["target_domain_id"])
    coordinator_material = readiness_packets[0]["credential_placement"]["coordinator_material"]
    require(isinstance(coordinator_material, dict), "E_EXACT_LAUNCH_COORDINATOR_MATERIAL")
    coordinator_public_key_path = Path(coordinator_material["runtime_public_key_path"])
    coordinator_private_key_path = Path(coordinator_material["runtime_private_key_path"])
    domain_public_paths = {
        domain_id: attestation_bundle / f"{domain_id}.pub" for domain_id in DOMAIN_IDS
    }

    def lane_factory(plan: dict, packet: dict):  # noqa: ANN202
        roundtrip = lane_module.PersistentSocketRoundTrip(
            coordinator_plan, plan, expected_domain_der[plan["domain_id"]], clock,
        )
        return lane_module.AuthenticatedDomainLane(
            coordinator_plan, plan, packet,
            coordinator_public_key_path, coordinator_private_key_path,
            domain_public_paths[plan["domain_id"]], roundtrip,
            bootstrap_store, collector, clock,
        )

    finalizer_module = load_finalizer_module()
    finalizer = finalizer_module.ExactEvidenceFinalizer(
        collector, bootstrap_store,
        {domain_id: path.read_bytes() for domain_id, path in domain_public_paths.items()},
        synthetic_only=False,
    )
    return load_runner_module().run_source_bound(
        execution, admission, endpoint, readiness_packets,
        lane_factory, finalizer, clock, False,
    )


def run_coordinator(
    execution_contract_path: Path,
    owner_signature_path: Path,
    admission_receipt_path: Path,
    endpoint_manifest_path: Path,
    readiness_bundle: Path,
    attestation_bundle: Path,
    credential_manifest_path: Path,
    source_commit: str,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict:
    require_activation_chain("COORDINATOR")
    consumer = load_consumer_module()
    now = clock()
    return foreign_call(
        consumer.consume_and_dispatch,
        execution_contract_path, owner_signature_path, admission_receipt_path,
        source_commit, now,
        lambda execution, admission: coordinator_runner(
            execution, admission, endpoint_manifest_path, readiness_bundle,
            attestation_bundle, credential_manifest_path, clock,
        ),
        clock,
    )


def status() -> dict:
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.exact_launch_binding_status.v0",
        "status": "EXACT_NONPRODUCTION_COORDINATOR_AND_DOMAIN_ENTRYPOINTS_PRESENT_ACTIVATION_CLOSED",
        "exact_launch_binding_activation_ready": EXACT_LAUNCH_BINDING_ACTIVATION_READY,
        "roles": ["COORDINATOR", "DOMAIN_AGENT"],
        "owner_signature_verified_independently_per_role": True,
        "admission_verified_before_runtime_input_read": True,
        "domain_reservation_created_before_listener": True,
        "coordinator_runtime_inputs_loaded_only_after_consumer_reservation": True,
        "automatic_retry_allowed": False,
        "real_private_inputs_read": 0, "credential_files_read": 0,
        "network_accessed": False, "listeners_started": 0,
        "processes_started": 0, "faults_injected": 0, "spend_usd_cents": 0,
        "execution_authorized": False, "production_admissible": False,
    }


def add_authorization_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--execution-contract", type=Path, required=True)
    parser.add_argument("--owner-execution-signature", type=Path, required=True)
    parser.add_argument("--execution-admission-receipt", type=Path, required=True)
    parser.add_argument("--private-endpoint-manifest", type=Path, required=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    domain = commands.add_parser("domain-agent")
    add_authorization_arguments(domain)
    domain.add_argument("--domain-id", choices=DOMAIN_IDS, required=True)
    domain.add_argument("--runtime-readiness-packet", type=Path, required=True)
    domain.add_argument("--runtime-readiness-signature", type=Path, required=True)
    coordinator = commands.add_parser("coordinator")
    add_authorization_arguments(coordinator)
    coordinator.add_argument("--runtime-readiness-bundle", type=Path, required=True)
    coordinator.add_argument("--attestation-bundle", type=Path, required=True)
    coordinator.add_argument("--runtime-credential-manifest", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "status":
        print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
        return
    source_commit = current_clean_source_commit()
    if arguments.command == "domain-agent":
        result = serve_domain_agent(
            arguments.domain_id, arguments.execution_contract,
            arguments.owner_execution_signature, arguments.execution_admission_receipt,
            arguments.private_endpoint_manifest, arguments.runtime_readiness_packet,
            arguments.runtime_readiness_signature, source_commit,
        )
    else:
        result = run_coordinator(
            arguments.execution_contract, arguments.owner_execution_signature,
            arguments.execution_admission_receipt, arguments.private_endpoint_manifest,
            arguments.runtime_readiness_bundle, arguments.attestation_bundle,
            arguments.runtime_credential_manifest, source_commit,
        )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except SafeFailure as error:
        print(json.dumps({"status": "BLOCKED_FAIL_CLOSED", "failure_code": str(error)}, sort_keys=True, separators=(",", ":")))
        sys.exit(1)
