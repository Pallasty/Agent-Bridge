"""Synthetic offline KATs for the T22-A1 domain-agent session core."""
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
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_agent_session_v1.py"
spec = importlib.util.spec_from_file_location("t22a1agentsession", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

runtime = module.load_runtime_module()
SOURCE_COMMIT = "a" * 40
RUN_ID = "t22-a1-20260722T230000.000000z-123456789abc"
EXECUTION_SHA256 = hashlib.sha256(b"synthetic-execution").hexdigest()
ENDPOINT_SHA256 = hashlib.sha256(b"synthetic-endpoints").hexdigest()
CREDENTIAL_SHA256 = hashlib.sha256(b"synthetic-credentials").hexdigest()
NOW = datetime(2026, 7, 22, 23, 0, tzinfo=timezone.utc)


def digest(label: str) -> str:
    return hashlib.sha256(f"T22_A1_SYNTHETIC_AGENT_SESSION_ONLY:{label}".encode()).hexdigest()


def sign(path: Path, private_key: Path, namespace: str) -> Path:
    signature = path.with_suffix(path.suffix + ".sig")
    if signature.exists():
        signature.unlink()
    result = subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(private_key), "-n", namespace, str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    assert result.returncode == 0 and signature.is_file()
    return signature


def rehash(value: dict) -> None:
    value.pop("content_sha256", None)
    value["content_sha256"] = runtime.digest(runtime.MESSAGE_DOMAIN, value)


ssh_keygen = shutil.which("ssh-keygen")
assert ssh_keygen is not None
with tempfile.TemporaryDirectory(prefix="t22-a1-agent-session-kat-") as directory:
    private_root = Path(directory).resolve()
    coordinator_key = private_root / "coordinator"
    wrong_key = private_root / "wrong"
    domain_keys = {domain_id: private_root / domain_id for domain_id in ("domain-1", "domain-2", "domain-3")}
    for key in (coordinator_key, wrong_key, *domain_keys.values()):
        subprocess.run(
            [ssh_keygen, "-q", "-t", "ed25519", "-N", "", "-C", "T22_A1_SYNTHETIC_ONLY", "-f", str(key)],
            check=True,
        )

    def new_session(domain_id: str, fault_target: str = "domain-2") -> module.AgentSession:
        return module.AgentSession(
            domain_id=domain_id,
            fault_target_domain_id=fault_target,
            source_commit=SOURCE_COMMIT,
            run_id=RUN_ID,
            execution_contract_sha256=EXECUTION_SHA256,
            endpoint_manifest_sha256=ENDPOINT_SHA256,
            credential_manifest_sha256=CREDENTIAL_SHA256,
            coordinator_public_key_path=Path(str(coordinator_key) + ".pub"),
            domain_public_key_path=Path(str(domain_keys[domain_id]) + ".pub"),
        )

    pair_counter = 0

    def build_pair(session: module.AgentSession, command: str, result: str = "SUCCEEDED", failure_code=None) -> tuple[dict, Path, Path, dict, Path, Path]:  # noqa: ANN001
        global pair_counter
        pair_counter += 1
        nonce = digest(f"nonce:{session.domain_id}:{pair_counter}")
        payload = digest(f"payload:{session.domain_id}:{command}:{pair_counter}")
        issued = NOW.isoformat().replace("+00:00", "Z")
        expires = (NOW + timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
        request = {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_agent_message.v1",
            "packet_kind": "T22_A1_DOMAIN_AGENT_REQUEST",
            "hashing_contract": {
                "hash_algorithm": "SHA-256",
                "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
                "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/domain-agent-message/v1",
                "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256",
                "self_hash_field": "content_sha256",
                "self_hash_field_excluded": True,
                "detached_signature_covers_complete_canonical_packet": True,
                "cross_field_semantic_validation_required": True,
            },
            "run_id": RUN_ID,
            "source_commit": SOURCE_COMMIT,
            "execution_contract_sha256": EXECUTION_SHA256,
            "private_endpoint_manifest_sha256": ENDPOINT_SHA256,
            "runtime_credential_manifest_sha256": CREDENTIAL_SHA256,
            "domain_id": session.domain_id,
            "direction": "COORDINATOR_TO_DOMAIN",
            "sequence": session.next_sequence,
            "previous_message_sha256": session.previous_message_sha256,
            "nonce_sha256": nonce,
            "issued_at": issued,
            "expires_at": expires,
            "command": command,
            "payload_sha256": payload,
            "result": "REQUESTED",
            "failure_code": None,
            "signature_binding": {
                "signer_role": "COORDINATOR_RUNTIME",
                "signer_public_key_sha256": session.coordinator_public_key_sha256,
                "signature_scheme": "OPENSSH_SSHSIG_ED25519",
                "signature_namespace": module.REQUEST_NAMESPACE,
                "detached_signature_required": True,
                "signature_embedded": False,
            },
            "raw_endpoint_embedded": False,
            "credential_or_secret_embedded": False,
            "arbitrary_command_or_shell_allowed": False,
            "execution_or_production_claim": False,
        }
        rehash(request)
        response = copy.deepcopy(request)
        response.update(
            packet_kind="T22_A1_DOMAIN_AGENT_RESPONSE",
            direction="DOMAIN_TO_COORDINATOR",
            sequence=request["sequence"] + 1,
            previous_message_sha256=request["content_sha256"],
            payload_sha256=digest(f"response-payload:{session.domain_id}:{command}:{pair_counter}"),
            result=result,
            failure_code=failure_code,
        )
        response["signature_binding"] = {
            "signer_role": "DOMAIN_OPERATOR",
            "signer_public_key_sha256": session.domain_public_key_sha256,
            "signature_scheme": "OPENSSH_SSHSIG_ED25519",
            "signature_namespace": module.RESPONSE_NAMESPACE,
            "detached_signature_required": True,
            "signature_embedded": False,
        }
        rehash(response)
        request_path = private_root / f"request-{pair_counter}.json"
        response_path = private_root / f"response-{pair_counter}.json"
        request_path.write_bytes(module.canonical(request) + b"\n")
        response_path.write_bytes(module.canonical(response) + b"\n")
        request_signature = sign(request_path, coordinator_key, module.REQUEST_NAMESPACE)
        response_signature = sign(response_path, domain_keys[session.domain_id], module.RESPONSE_NAMESPACE)
        return request, request_path, request_signature, response, response_path, response_signature

    def accept(session: module.AgentSession, command: str, result: str = "SUCCEEDED", failure_code=None) -> dict:  # noqa: ANN001
        _request, request_path, request_signature, _response, response_path, response_signature = build_pair(
            session, command, result, failure_code,
        )
        receipt = session.accept_pair(
            request_path, request_signature, response_path, response_signature,
            NOW + timedelta(seconds=1),
        )
        assert receipt["command_executed_by_session_core"] is False
        assert receipt["network_accessed"] is False and receipt["listener_started"] is False
        assert receipt["service_process_started"] is False and receipt["fault_injected"] is False
        assert receipt["execution_authorized"] is False and receipt["production_admissible"] is False
        return receipt

    coordinator = new_session("domain-1")
    coordinator_commands = (
        "PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE",
        "EXECUTE_AUTHORIZE_CONSUME", "CREATE_PREFAULT_TRANSIT_SIGNATURE",
        "VERIFY_SURVIVING_QUORUM_AND_STATE", "VERIFY_POSTFAULT_TRANSIT_SIGNATURE",
        "CLEANUP_OWNED_PROCESSES", "TERMINAL_STATUS",
    )
    for command in coordinator_commands:
        accept(coordinator, command)
    assert coordinator.state == "TERMINAL_SUCCEEDED"

    target = new_session("domain-2")
    target_commands = (
        "PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE",
        "STOP_OWNED_SERVICE_SET", "RESTART_OWNED_SERVICE_SET",
        "VERIFY_TARGET_REJOIN", "CLEANUP_OWNED_PROCESSES", "TERMINAL_STATUS",
    )
    for command in target_commands:
        accept(target, command)
    assert target.state == "TERMINAL_SUCCEEDED"

    survivor = new_session("domain-3")
    survivor_commands = (
        "PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE",
        "VERIFY_SURVIVING_QUORUM_AND_STATE", "CLEANUP_OWNED_PROCESSES", "TERMINAL_STATUS",
    )
    for command in survivor_commands:
        accept(survivor, command)
    assert survivor.state == "TERMINAL_SUCCEEDED"

    invalid_transition = new_session("domain-2")
    pair = build_pair(invalid_transition, "STOP_OWNED_SERVICE_SET")
    try:
        invalid_transition.accept_pair(pair[1], pair[2], pair[4], pair[5], NOW + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_AGENT_SESSION_TRANSITION"
    else:
        raise AssertionError("invalid initial state transition admitted")

    wrong_signature_session = new_session("domain-2")
    pair = build_pair(wrong_signature_session, "PREFLIGHT")
    wrong_copy = private_root / "wrong-request-copy.json"
    wrong_copy.write_bytes(pair[1].read_bytes())
    wrong_signature = sign(wrong_copy, wrong_key, module.REQUEST_NAMESPACE)
    try:
        wrong_signature_session.accept_pair(pair[1], wrong_signature, pair[4], pair[5], NOW + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_AGENT_MESSAGE_SIGNATURE_INVALID"
    else:
        raise AssertionError("wrong coordinator signature admitted")

    replay_session = new_session("domain-2")
    replay_pair = build_pair(replay_session, "PREFLIGHT")
    replay_session.accept_pair(replay_pair[1], replay_pair[2], replay_pair[4], replay_pair[5], NOW + timedelta(seconds=1))
    try:
        replay_session.accept_pair(replay_pair[1], replay_pair[2], replay_pair[4], replay_pair[5], NOW + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_AGENT_SESSION_REQUEST_SEQUENCE"
    else:
        raise AssertionError("message pair replay admitted")

    mismatch_session = new_session("domain-3")
    request, request_path, request_signature, response, response_path, _response_signature = build_pair(mismatch_session, "PREFLIGHT")
    response["nonce_sha256"] = digest("different-nonce")
    rehash(response)
    response_path.write_bytes(module.canonical(response) + b"\n")
    response_signature = sign(response_path, domain_keys["domain-3"], module.RESPONSE_NAMESPACE)
    try:
        mismatch_session.accept_pair(request_path, request_signature, response_path, response_signature, NOW + timedelta(seconds=1))
    except module.SafeFailure as error:
        assert str(error) == "E_AGENT_SESSION_NONCE_PAIR"
    else:
        raise AssertionError("request/response nonce mismatch admitted")

    pair_mutations = (
        ("response-command", "response", lambda x: x.update(command="QUERY_CLUSTER_STATE"), "E_AGENT_SESSION_COMMAND_PAIR"),
        ("response-payload-reuse", "response", lambda x: x.update(payload_sha256=request["payload_sha256"]), "E_AGENT_SESSION_RESPONSE_PAYLOAD_REUSE"),
        ("response-sequence", "response", lambda x: x.update(sequence=3), "E_AGENT_SESSION_RESPONSE_SEQUENCE"),
        ("request-previous", "request", lambda x: x.update(previous_message_sha256=digest("wrong-previous")), "E_AGENT_MESSAGE_SCHEMA"),
        ("response-domain", "response", lambda x: x.update(domain_id="domain-3"), "E_AGENT_SESSION_DOMAIN_BINDING"),
        ("request-key-binding", "request", lambda x: x["signature_binding"].update(signer_public_key_sha256=digest("wrong-key-binding")), "E_AGENT_SESSION_COORDINATOR_KEY_BINDING"),
        ("response-previous", "response", lambda x: x.update(previous_message_sha256=digest("wrong-response-previous")), "E_AGENT_SESSION_RESPONSE_CHAIN"),
    )
    for _label, side, mutation, expected_error in pair_mutations:
        pair_session = new_session("domain-2")
        request, request_path, _request_signature, response, response_path, _response_signature = build_pair(pair_session, "PREFLIGHT")
        selected = request if side == "request" else response
        mutation(selected)
        rehash(selected)
        if side == "request":
            response["previous_message_sha256"] = request["content_sha256"]
            rehash(response)
        request_path.write_bytes(module.canonical(request) + b"\n")
        response_path.write_bytes(module.canonical(response) + b"\n")
        request_signature = sign(request_path, coordinator_key, module.REQUEST_NAMESPACE)
        response_signature = sign(response_path, domain_keys["domain-2"], module.RESPONSE_NAMESPACE)
        try:
            pair_session.accept_pair(request_path, request_signature, response_path, response_signature, NOW + timedelta(seconds=1))
        except module.SafeFailure as error:
            assert str(error) == expected_error, (_label, str(error))
        else:
            raise AssertionError(f"unsafe pair mutation admitted: {_label}")

    stale_session = new_session("domain-2")
    stale_pair = build_pair(stale_session, "PREFLIGHT")
    try:
        stale_session.accept_pair(stale_pair[1], stale_pair[2], stale_pair[4], stale_pair[5], NOW + timedelta(minutes=2))
    except module.SafeFailure as error:
        assert str(error) == "E_AGENT_MESSAGE_NOT_CURRENT"
    else:
        raise AssertionError("stale signed message pair admitted")

    wrong_response_session = new_session("domain-2")
    wrong_response_pair = build_pair(wrong_response_session, "PREFLIGHT")
    wrong_response_copy = private_root / "wrong-response-copy.json"
    wrong_response_copy.write_bytes(wrong_response_pair[4].read_bytes())
    wrong_response_signature = sign(wrong_response_copy, wrong_key, module.RESPONSE_NAMESPACE)
    try:
        wrong_response_session.accept_pair(
            wrong_response_pair[1], wrong_response_pair[2],
            wrong_response_pair[4], wrong_response_signature,
            NOW + timedelta(seconds=1),
        )
    except module.SafeFailure as error:
        assert str(error) == "E_AGENT_MESSAGE_SIGNATURE_INVALID"
    else:
        raise AssertionError("wrong domain response signature admitted")

    failed_session = new_session("domain-2")
    failed_receipt = accept(failed_session, "PREFLIGHT", "FAILED", "E_SYNTHETIC")
    assert failed_receipt["state"] == "TERMINAL_FAILED"
    assert failed_receipt["automatic_retry_allowed"] is False
    try:
        accept(failed_session, "PREFLIGHT")
    except module.SafeFailure as error:
        assert str(error) == "E_AGENT_SESSION_TERMINAL"
    else:
        raise AssertionError("failed terminal session admitted retry")

    reused_key_session_args = dict(
        domain_id="domain-3", fault_target_domain_id="domain-2", source_commit=SOURCE_COMMIT,
        run_id=RUN_ID, execution_contract_sha256=EXECUTION_SHA256,
        endpoint_manifest_sha256=ENDPOINT_SHA256, credential_manifest_sha256=CREDENTIAL_SHA256,
        coordinator_public_key_path=Path(str(coordinator_key) + ".pub"),
        domain_public_key_path=Path(str(coordinator_key) + ".pub"),
    )
    try:
        module.AgentSession(**reused_key_session_args)
    except module.SafeFailure as error:
        assert str(error) == "E_AGENT_SESSION_KEY_REUSE"
    else:
        raise AssertionError("coordinator/domain signing key reuse admitted")

status = module.status()
assert status["status"] == "OFFLINE_AGENT_SESSION_CORE_READY_REAL_RUNTIME_INPUTS_AND_OWNER_EXECUTION_SIGNATURE_REQUIRED"
assert status["message_instances_read"] is False
assert status["public_keys_read"] is False and status["private_keys_read"] is False
assert status["credential_manifest_read"] is False and status["credential_files_read"] is False
assert status["network_accessed"] is False and status["listeners_started"] == 0
assert status["commands_executed"] == status["services_started"] == status["faults_injected"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

print("t22_a1_domain_agent_session_check\tpass")
print("valid_signed_transition_pair_count\t25")
print("directed_negative_test_count\t15")
print("real_message_instances_read\t0")
print("real_public_or_private_keys_read\t0")
print("credential_files_read\tfalse")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("commands_executed\t0")
print("services_started\t0")
print("faults_injected\t0")
