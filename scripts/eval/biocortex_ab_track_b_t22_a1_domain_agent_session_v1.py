"""Offline signed-message session core for T22-A1 domain agents.

This module validates bounded request/response pairs and lifecycle transitions.
It does not read runtime credential manifests, open sockets, start listeners,
execute commands, start services, or inject faults.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_private_runtime_contracts_v1.py"
CHALLENGE_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_collection_challenge_v1.py"
MAX_MESSAGE_BYTES = 64 * 1024
MAX_SIGNATURE_BYTES = 64 * 1024
REQUEST_NAMESPACE = "agent-bridge-t22-a1-coordinator-message-v1"
RESPONSE_NAMESPACE = "agent-bridge-t22-a1-domain-message-v1"


class SafeFailure(RuntimeError):
    """Stable non-secret rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SafeFailure(code)


def load_module(name: str, source: Path):
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_runtime_module():
    return load_module("t22a1_runtime_for_agent_session", RUNTIME_SOURCE)


def load_challenge_module():
    return load_module("t22a1_challenge_for_agent_session", CHALLENGE_SOURCE)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def foreign_call(function, *arguments, **keywords):  # noqa: ANN001, ANN002, ANN003
    try:
        return function(*arguments, **keywords)
    except RuntimeError as error:
        raise SafeFailure(str(error)) from error


def read_canonical_message(path: Path) -> tuple[dict, bytes]:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "E_AGENT_MESSAGE_FILE")
    metadata = path.stat()
    require(0 < metadata.st_size <= MAX_MESSAGE_BYTES, "E_AGENT_MESSAGE_FILE")
    raw = path.read_bytes()
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "E_AGENT_MESSAGE_FRAMING")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SafeFailure("E_AGENT_MESSAGE_JSON") from error
    require(raw == canonical(value) + b"\n", "E_AGENT_MESSAGE_NOT_CANONICAL")
    return value, raw


def canonical_public_key(path: Path) -> tuple[bytes, str]:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "E_AGENT_PUBLIC_KEY_FILE")
    challenge = load_challenge_module()
    key = foreign_call(challenge.canonical_public_key_bytes, path.read_bytes())
    return key, hashlib.sha256(key).hexdigest()


def verify_signature(raw: bytes, signature_path: Path, public_key: bytes, principal: str, namespace: str) -> str:
    require(signature_path.is_absolute() and signature_path.is_file() and not signature_path.is_symlink(), "E_AGENT_SIGNATURE_FILE")
    signature = signature_path.read_bytes()
    require(0 < len(signature) <= MAX_SIGNATURE_BYTES, "E_AGENT_SIGNATURE_FILE")
    ssh_keygen = shutil.which("ssh-keygen")
    require(ssh_keygen is not None, "E_SSH_KEYGEN_MISSING")
    with tempfile.TemporaryDirectory(prefix="t22-a1-agent-message-verify-") as directory:
        allowed = Path(directory) / "allowed_signers"
        allowed.write_bytes(principal.encode() + b" " + public_key)
        allowed.chmod(0o600)
        result = subprocess.run(
            [ssh_keygen, "-Y", "verify", "-f", str(allowed), "-I", principal,
             "-n", namespace, "-s", str(signature_path)],
            input=raw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C", "LC_ALL": "C"},
            check=False,
        )
    require(result.returncode == 0, "E_AGENT_MESSAGE_SIGNATURE_INVALID")
    return hashlib.sha256(signature).hexdigest()


def next_state(domain_id: str, fault_target_domain_id: str, state: str, command: str) -> str:
    common = {
        ("CREATED", "PREFLIGHT"): "PREFLIGHT_OK",
        ("PREFLIGHT_OK", "START_OWNED_CLUSTER_MEMBERS"): "SERVICES_STARTED",
        ("SERVICES_STARTED", "QUERY_CLUSTER_STATE"): "CLUSTER_READY",
        ("CLEANED", "TERMINAL_STATUS"): "TERMINAL_SUCCEEDED",
    }
    if (state, command) in common:
        return common[(state, command)]
    if domain_id == "domain-1":
        transitions = {
            ("CLUSTER_READY", "EXECUTE_AUTHORIZE_CONSUME"): "WORKLOAD_CONSUMED",
            ("WORKLOAD_CONSUMED", "CREATE_PREFAULT_TRANSIT_SIGNATURE"): "PREFAULT_SIGNATURE_CREATED",
            ("PREFAULT_SIGNATURE_CREATED", "VERIFY_SURVIVING_QUORUM_AND_STATE"): "SURVIVOR_STATE_VERIFIED",
            ("SURVIVOR_STATE_VERIFIED", "VERIFY_POSTFAULT_TRANSIT_SIGNATURE"): "POSTFAULT_SIGNATURE_VERIFIED",
            ("POSTFAULT_SIGNATURE_VERIFIED", "CLEANUP_OWNED_PROCESSES"): "CLEANED",
        }
    elif domain_id == fault_target_domain_id:
        transitions = {
            ("CLUSTER_READY", "STOP_OWNED_SERVICE_SET"): "SERVICE_SET_STOPPED",
            ("SERVICE_SET_STOPPED", "RESTART_OWNED_SERVICE_SET"): "SERVICE_SET_RESTARTED",
            ("SERVICE_SET_RESTARTED", "VERIFY_TARGET_REJOIN"): "TARGET_REJOIN_VERIFIED",
            ("TARGET_REJOIN_VERIFIED", "CLEANUP_OWNED_PROCESSES"): "CLEANED",
        }
    else:
        transitions = {
            ("CLUSTER_READY", "VERIFY_SURVIVING_QUORUM_AND_STATE"): "SURVIVOR_STATE_VERIFIED",
            ("SURVIVOR_STATE_VERIFIED", "CLEANUP_OWNED_PROCESSES"): "CLEANED",
        }
    require((state, command) in transitions, "E_AGENT_SESSION_TRANSITION")
    return transitions[(state, command)]


@dataclass
class AgentSession:
    domain_id: str
    fault_target_domain_id: str
    source_commit: str
    run_id: str
    execution_contract_sha256: str
    endpoint_manifest_sha256: str
    credential_manifest_sha256: str
    coordinator_public_key_path: Path
    domain_public_key_path: Path
    state: str = "CREATED"
    next_sequence: int = 0
    previous_message_sha256: str = "0" * 64
    seen_nonce_sha256: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        require(self.domain_id in {"domain-1", "domain-2", "domain-3"}, "E_AGENT_SESSION_DOMAIN")
        require(self.fault_target_domain_id in {"domain-2", "domain-3"}, "E_AGENT_SESSION_FAULT_TARGET")
        self.runtime = load_runtime_module()
        _endpoint, _credential, self.message_schema = self.runtime.load_schemas()
        self.coordinator_public_key, self.coordinator_public_key_sha256 = canonical_public_key(self.coordinator_public_key_path)
        self.domain_public_key, self.domain_public_key_sha256 = canonical_public_key(self.domain_public_key_path)
        require(self.coordinator_public_key_sha256 != self.domain_public_key_sha256, "E_AGENT_SESSION_KEY_REUSE")

    def validate_message(self, value: dict, now: datetime) -> None:
        foreign_call(
            self.runtime.validate_agent_message,
            value, self.message_schema, self.source_commit, self.run_id,
            self.execution_contract_sha256, self.endpoint_manifest_sha256,
            self.credential_manifest_sha256, now,
        )

    def accept_pair(
        self,
        request_path: Path,
        request_signature_path: Path,
        response_path: Path,
        response_signature_path: Path,
        now: datetime,
    ) -> dict:
        require(self.state not in {"TERMINAL_SUCCEEDED", "TERMINAL_FAILED"}, "E_AGENT_SESSION_TERMINAL")
        request, request_raw = read_canonical_message(request_path)
        response, response_raw = read_canonical_message(response_path)
        self.validate_message(request, now)
        self.validate_message(response, now)
        require(request["packet_kind"] == "T22_A1_DOMAIN_AGENT_REQUEST", "E_AGENT_SESSION_REQUEST_KIND")
        require(response["packet_kind"] == "T22_A1_DOMAIN_AGENT_RESPONSE", "E_AGENT_SESSION_RESPONSE_KIND")
        require(request["domain_id"] == response["domain_id"] == self.domain_id, "E_AGENT_SESSION_DOMAIN_BINDING")
        require(request["sequence"] == self.next_sequence, "E_AGENT_SESSION_REQUEST_SEQUENCE")
        require(request["previous_message_sha256"] == self.previous_message_sha256, "E_AGENT_SESSION_REQUEST_CHAIN")
        require(response["sequence"] == request["sequence"] + 1, "E_AGENT_SESSION_RESPONSE_SEQUENCE")
        require(response["previous_message_sha256"] == request["content_sha256"], "E_AGENT_SESSION_RESPONSE_CHAIN")
        require(request["nonce_sha256"] == response["nonce_sha256"], "E_AGENT_SESSION_NONCE_PAIR")
        require(request["nonce_sha256"] not in self.seen_nonce_sha256, "E_AGENT_SESSION_NONCE_REPLAY")
        require(request["command"] == response["command"], "E_AGENT_SESSION_COMMAND_PAIR")
        require(request["payload_sha256"] == response["payload_sha256"], "E_AGENT_SESSION_PAYLOAD_PAIR")
        require(request["signature_binding"]["signer_public_key_sha256"] == self.coordinator_public_key_sha256, "E_AGENT_SESSION_COORDINATOR_KEY_BINDING")
        require(response["signature_binding"]["signer_public_key_sha256"] == self.domain_public_key_sha256, "E_AGENT_SESSION_DOMAIN_KEY_BINDING")
        request_signature_sha256 = verify_signature(
            request_raw, request_signature_path, self.coordinator_public_key,
            "coordinator", REQUEST_NAMESPACE,
        )
        response_signature_sha256 = verify_signature(
            response_raw, response_signature_path, self.domain_public_key,
            self.domain_id, RESPONSE_NAMESPACE,
        )
        command = request["command"]
        proposed_state = next_state(self.domain_id, self.fault_target_domain_id, self.state, command)
        self.seen_nonce_sha256.add(request["nonce_sha256"])
        self.next_sequence += 2
        self.previous_message_sha256 = response["content_sha256"]
        if response["result"] == "FAILED":
            self.state = "TERMINAL_FAILED"
            automatic_retry_allowed = False
        else:
            self.state = proposed_state
            automatic_retry_allowed = False
        return {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_agent_session_transition_receipt.v0",
            "domain_id": self.domain_id,
            "command": command,
            "result": response["result"],
            "failure_code": response["failure_code"],
            "state": self.state,
            "request_content_sha256": request["content_sha256"],
            "request_signature_sha256": request_signature_sha256,
            "response_content_sha256": response["content_sha256"],
            "response_signature_sha256": response_signature_sha256,
            "next_sequence": self.next_sequence,
            "previous_message_sha256": self.previous_message_sha256,
            "automatic_retry_allowed": automatic_retry_allowed,
            "command_executed_by_session_core": False,
            "network_accessed": False,
            "listener_started": False,
            "service_process_started": False,
            "fault_injected": False,
            "execution_authorized": False,
            "production_admissible": False,
        }


def status() -> dict:
    runtime = load_runtime_module()
    runtime.load_schemas()
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_agent_session_status.v0",
        "status": "OFFLINE_AGENT_SESSION_CORE_READY_REAL_RUNTIME_INPUTS_AND_OWNER_EXECUTION_SIGNATURE_REQUIRED",
        "message_schema_sha256": runtime.EXPECTED_MESSAGE_SCHEMA_SHA256,
        "message_instances_read": False,
        "public_keys_read": False,
        "private_keys_read": False,
        "credential_manifest_read": False,
        "credential_files_read": False,
        "network_accessed": False,
        "listeners_started": 0,
        "commands_executed": 0,
        "services_started": 0,
        "faults_injected": 0,
        "execution_authorized": False,
        "production_admissible": False,
    }


if __name__ == "__main__":
    print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
