"""Authenticated non-production domain lane for the T22-A1 real-lab run.

The lane joins the source-bound scheduler, fixed-command executor, bounded mTLS
transport, and memory-only OpenBao bootstrap exchange.  Every command uses one
fresh, signed, run-bound request/response pair.  There is no generic command,
shell, retry, production, or secret-persistence surface.  All live activation
flags remain closed pending exact runtime material and final owner execution
authorization.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import secrets
import shutil
import socket
import ssl
import stat
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Protocol

ROOT = Path(__file__).resolve().parents[2]
SESSION_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_agent_session_v1.py"
RUNTIME_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_private_runtime_contracts_v1.py"
TRANSPORT_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_mtls_transport_v1.py"
EXECUTOR_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_executor_core_v1.py"
BACKEND_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_live_local_backend_v1.py"
MESSAGE_LIFETIME_SECONDS = 60
AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY = False
HASHING_CONTRACT = {
    "hash_algorithm": "SHA-256",
    "canonicalization": "COMPACT_SORTED_KEYS_UTF8_JSON_NO_FLOAT",
    "digest_domain": "agent-bridge/biocortex/track-b/t22-a1/domain-agent-message/v1",
    "hash_scope": "ENTIRE_PACKET_EXCEPT_CONTENT_SHA256",
    "self_hash_field": "content_sha256",
    "self_hash_field_excluded": True,
    "detached_signature_covers_complete_canonical_packet": True,
    "cross_field_semantic_validation_required": True,
}
REQUEST_PAYLOAD_KEYS = {
    "schema", "run_id", "source_commit", "execution_contract_sha256",
    "domain_workload_plan_sha256", "domain_id", "command", "mode",
    "secret_frame_direction", "secret_frame_sha256",
    "automatic_retry_allowed", "arbitrary_command_or_shell_allowed",
    "production_admissible",
}
FAILURE_PAYLOAD_KEYS = {
    "schema", "run_id", "source_commit", "execution_contract_sha256",
    "domain_workload_plan_sha256", "domain_id", "command", "failure_code",
    "all_owned_processes_cleaned", "all_owned_ports_released",
    "automatic_retry_allowed", "production_admissible",
}
CLEANUP_PAYLOAD_KEYS = {
    "schema", "run_id", "source_commit", "execution_contract_sha256",
    "domain_workload_plan_sha256", "domain_id", "command",
    "all_owned_processes_cleaned", "all_owned_ports_released",
    "automatic_retry_allowed", "production_admissible",
}


class SafeFailure(RuntimeError):
    """Stable non-secret fail-closed rejection."""


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


def load_session_module():
    return load_module("t22a1_session_for_authenticated_lane", SESSION_SOURCE)


def load_runtime_module():
    return load_module("t22a1_runtime_for_authenticated_lane", RUNTIME_SOURCE)


def load_transport_module():
    return load_module("t22a1_transport_for_authenticated_lane", TRANSPORT_SOURCE)


def load_executor_module():
    return load_module("t22a1_executor_for_authenticated_lane", EXECUTOR_SOURCE)


def load_backend_module():
    return load_module("t22a1_backend_for_authenticated_lane", BACKEND_SOURCE)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def canonical_line(value: object) -> bytes:
    return canonical(value) + b"\n"


def is_sha256(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and value != "0" * 64
        and all(character in "0123456789abcdef" for character in value)
    )


def hash_file(path: Path, code: str) -> str:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), code)
    value = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                value.update(chunk)
    except OSError as error:
        raise SafeFailure(code) from error
    return value.hexdigest()


def utc_text(value: datetime) -> str:
    require(value.tzinfo is not None and value.utcoffset().total_seconds() == 0, "E_AUTH_LANE_TIMEZONE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: object, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise SafeFailure(code) from error
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0, code)
    return parsed


def foreign(function, *arguments, **keywords):  # noqa: ANN001, ANN002, ANN003
    try:
        return function(*arguments, **keywords)
    except RuntimeError as error:
        raise SafeFailure(str(error)) from error


def stable_code(error: Exception) -> str:
    value = str(error)
    if (
        isinstance(error, RuntimeError) and value.startswith("E_")
        and all(character in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in value)
    ):
        return value
    return "E_AUTH_LANE_LOCAL_FAILURE"


class SshSigTool:
    """Exact-hash OpenSSH signing tool with no ambient PATH or signer set."""

    def __init__(self, executable_path: str, expected_sha256: str) -> None:
        require(AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY, "E_AUTH_LANE_ACTIVATION_NOT_READY")
        require(isinstance(executable_path, str) and Path(executable_path).is_absolute(), "E_AUTH_LANE_SSH_KEYGEN_FILE")
        self.executable = Path(executable_path)
        require(is_sha256(expected_sha256), "E_AUTH_LANE_SSH_KEYGEN_DIGEST")
        metadata = self.executable.stat() if self.executable.is_file() and not self.executable.is_symlink() else None
        require(
            metadata is not None and stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid in {0, os.geteuid()} and metadata.st_mode & 0o022 == 0
            and os.access(self.executable, os.X_OK)
            and hash_file(self.executable, "E_AUTH_LANE_SSH_KEYGEN_FILE") == expected_sha256,
            "E_AUTH_LANE_SSH_KEYGEN_BINDING",
        )
        self.environment = {"LANG": "C", "LC_ALL": "C"}

    @staticmethod
    def _private_key(path: Path) -> None:
        require(path.is_absolute() and path.is_file() and not path.is_symlink(), "E_AUTH_LANE_PRIVATE_KEY_FILE")
        metadata = path.stat()
        require(
            stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.geteuid()
            and metadata.st_size > 0 and metadata.st_mode & 0o077 == 0,
            "E_AUTH_LANE_PRIVATE_KEY_MODE",
        )

    @staticmethod
    def _canonical_public(path: Path, expected_sha256: str) -> bytes:
        session = load_session_module()
        key, observed = foreign(session.canonical_public_key, path)
        require(observed == expected_sha256, "E_AUTH_LANE_PUBLIC_KEY_BINDING")
        return key

    def validate_key_pair(self, private_key_path: Path, public_key_path: Path, expected_public_sha256: str) -> bytes:
        self._private_key(private_key_path)
        public = self._canonical_public(public_key_path, expected_public_sha256)
        try:
            result = subprocess.run(
                [str(self.executable), "-y", "-f", str(private_key_path)],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                env=self.environment, shell=False, close_fds=True, timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SafeFailure("E_AUTH_LANE_KEY_PAIR_TOOL") from error
        require(result.returncode == 0 and 0 < len(result.stdout) <= 16 * 1024, "E_AUTH_LANE_KEY_PAIR_TOOL")
        with tempfile.TemporaryDirectory(prefix="t22-a1-auth-lane-key-") as directory:
            derived_path = Path(directory) / "derived.pub"
            derived_path.write_bytes(result.stdout.rstrip(b"\r\n") + b"\n")
            derived = self._canonical_public(derived_path, expected_public_sha256)
        require(derived == public, "E_AUTH_LANE_KEY_PAIR_BINDING")
        return public

    def read_public_key(self, public_key_path: Path, expected_public_sha256: str) -> bytes:
        return self._canonical_public(public_key_path, expected_public_sha256)

    def sign(self, raw: bytes, private_key_path: Path, namespace: str) -> bytes:
        self._private_key(private_key_path)
        require(0 < len(raw) <= 64 * 1024 and raw.endswith(b"\n"), "E_AUTH_LANE_SIGN_INPUT")
        with tempfile.TemporaryDirectory(prefix="t22-a1-auth-lane-sign-") as directory:
            message = Path(directory) / "message.json"
            message.write_bytes(raw)
            try:
                result = subprocess.run(
                    [str(self.executable), "-Y", "sign", "-f", str(private_key_path),
                     "-n", namespace, str(message)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env=self.environment, shell=False, close_fds=True, timeout=10, check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise SafeFailure("E_AUTH_LANE_SIGN_TOOL") from error
            signature_path = Path(str(message) + ".sig")
            require(result.returncode == 0 and signature_path.is_file(), "E_AUTH_LANE_SIGN_TOOL")
            signature = signature_path.read_bytes()
        require(0 < len(signature) <= 64 * 1024, "E_AUTH_LANE_SIGNATURE_SIZE")
        return signature

    def verify(self, raw: bytes, signature: bytes, public_key: bytes, principal: str, namespace: str) -> str:
        require(0 < len(raw) <= 64 * 1024 and 0 < len(signature) <= 64 * 1024, "E_AUTH_LANE_VERIFY_INPUT")
        with tempfile.TemporaryDirectory(prefix="t22-a1-auth-lane-verify-") as directory:
            signature_path = Path(directory) / "message.sig"
            allowed_path = Path(directory) / "allowed_signers"
            signature_path.write_bytes(signature)
            allowed_path.write_bytes(principal.encode() + b" " + public_key)
            allowed_path.chmod(0o600)
            try:
                result = subprocess.run(
                    [str(self.executable), "-Y", "verify", "-f", str(allowed_path),
                     "-I", principal, "-n", namespace, "-s", str(signature_path)],
                    input=raw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env=self.environment, shell=False, close_fds=True, timeout=10, check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise SafeFailure("E_AUTH_LANE_VERIFY_TOOL") from error
        require(result.returncode == 0, "E_AUTH_LANE_SIGNATURE_INVALID")
        return hashlib.sha256(signature).hexdigest()


def secret_policy(domain_id: str, fault_target_domain_id: str, command: str) -> str:
    if command == "START_OWNED_CLUSTER_MEMBERS":
        return "DOMAIN_TO_COORDINATOR" if domain_id == "domain-1" else "COORDINATOR_TO_DOMAIN"
    if command == "RESTART_OWNED_SERVICE_SET":
        require(domain_id == fault_target_domain_id, "E_AUTH_LANE_SECRET_POLICY")
        return "COORDINATOR_TO_DOMAIN"
    return "NONE"


def request_payload(plan: dict, command: str, mode: str, secret_frame_sha256: str | None) -> dict:
    require(mode in {"NORMAL", "EMERGENCY_CLEANUP"}, "E_AUTH_LANE_REQUEST_MODE")
    if mode == "EMERGENCY_CLEANUP":
        require(command == "CLEANUP_OWNED_PROCESSES", "E_AUTH_LANE_EMERGENCY_COMMAND")
        direction = "NONE"
        require(secret_frame_sha256 is None, "E_AUTH_LANE_SECRET_UNEXPECTED")
    else:
        direction = secret_policy(plan["domain_id"], plan["role"]["fault_target_domain_id"], command)
        require(
            (direction == "COORDINATOR_TO_DOMAIN" and is_sha256(secret_frame_sha256))
            or (direction != "COORDINATOR_TO_DOMAIN" and secret_frame_sha256 is None),
            "E_AUTH_LANE_SECRET_BINDING",
        )
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_command_request.v1",
        "run_id": plan["run_id"], "source_commit": plan["source_commit"],
        "execution_contract_sha256": plan["bindings"]["execution_contract_sha256"],
        "domain_workload_plan_sha256": plan["content_sha256"],
        "domain_id": plan["domain_id"], "command": command, "mode": mode,
        "secret_frame_direction": direction, "secret_frame_sha256": secret_frame_sha256,
        "automatic_retry_allowed": False, "arbitrary_command_or_shell_allowed": False,
        "production_admissible": False,
    }


def validate_request_payload(value: object, plan: dict, command: str) -> dict:
    require(isinstance(value, dict) and set(value) == REQUEST_PAYLOAD_KEYS, "E_AUTH_LANE_REQUEST_PAYLOAD_SHAPE")
    assert isinstance(value, dict)
    require(value == request_payload(plan, command, value.get("mode"), value.get("secret_frame_sha256")), "E_AUTH_LANE_REQUEST_PAYLOAD_BINDING")
    return value


def _bound_payload(value: dict, plan: dict, code: str) -> None:
    require(
        value.get("run_id") == plan["run_id"] and value.get("source_commit") == plan["source_commit"]
        and value.get("execution_contract_sha256") == plan["bindings"]["execution_contract_sha256"]
        and value.get("domain_workload_plan_sha256") == plan["content_sha256"]
        and value.get("domain_id") == plan["domain_id"],
        code,
    )


def failure_payload(plan: dict, command: str, code: str, cleanup: dict) -> dict:
    require(code.startswith("E_"), "E_AUTH_LANE_FAILURE_CODE")
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_command_failure.v1",
        "run_id": plan["run_id"], "source_commit": plan["source_commit"],
        "execution_contract_sha256": plan["bindings"]["execution_contract_sha256"],
        "domain_workload_plan_sha256": plan["content_sha256"], "domain_id": plan["domain_id"],
        "command": command, "failure_code": code,
        "all_owned_processes_cleaned": cleanup.get("all_owned_processes_cleaned") is True,
        "all_owned_ports_released": cleanup.get("all_owned_ports_released") is True,
        "automatic_retry_allowed": False, "production_admissible": False,
    }


def emergency_cleanup_payload(plan: dict, cleanup: dict) -> dict:
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.emergency_cleanup_receipt.v1",
        "run_id": plan["run_id"], "source_commit": plan["source_commit"],
        "execution_contract_sha256": plan["bindings"]["execution_contract_sha256"],
        "domain_workload_plan_sha256": plan["content_sha256"], "domain_id": plan["domain_id"],
        "command": "CLEANUP_OWNED_PROCESSES",
        "all_owned_processes_cleaned": cleanup.get("all_owned_processes_cleaned") is True,
        "all_owned_ports_released": cleanup.get("all_owned_ports_released") is True,
        "automatic_retry_allowed": False, "production_admissible": False,
    }


def validate_failure_payload(value: object, plan: dict, command: str) -> dict:
    require(isinstance(value, dict) and set(value) == FAILURE_PAYLOAD_KEYS, "E_AUTH_LANE_FAILURE_PAYLOAD_SHAPE")
    assert isinstance(value, dict)
    _bound_payload(value, plan, "E_AUTH_LANE_FAILURE_PAYLOAD_BINDING")
    require(
        value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.domain_command_failure.v1"
        and value["command"] == command and isinstance(value["failure_code"], str)
        and value["failure_code"].startswith("E_")
        and isinstance(value["all_owned_processes_cleaned"], bool)
        and isinstance(value["all_owned_ports_released"], bool)
        and value["automatic_retry_allowed"] is False and value["production_admissible"] is False,
        "E_AUTH_LANE_FAILURE_PAYLOAD_BINDING",
    )
    return value


def validate_cleanup_payload(value: object, plan: dict) -> dict:
    require(isinstance(value, dict) and set(value) == CLEANUP_PAYLOAD_KEYS, "E_AUTH_LANE_CLEANUP_PAYLOAD_SHAPE")
    assert isinstance(value, dict)
    _bound_payload(value, plan, "E_AUTH_LANE_CLEANUP_PAYLOAD_BINDING")
    require(
        value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.emergency_cleanup_receipt.v1"
        and value["command"] == "CLEANUP_OWNED_PROCESSES"
        and value["all_owned_processes_cleaned"] is True
        and value["all_owned_ports_released"] is True
        and value["automatic_retry_allowed"] is False and value["production_admissible"] is False,
        "E_AUTH_LANE_CLEANUP_PAYLOAD_BINDING",
    )
    return value


@dataclass
class PendingRequest:
    message: dict
    payload: dict
    proposed_state: str


@dataclass
class SessionMachine:
    plan: dict
    coordinator_public_key_path: Path
    coordinator_public_key_sha256: str
    domain_public_key_path: Path
    domain_public_key_sha256: str
    sshsig: SshSigTool
    state: str = "CREATED"
    next_sequence: int = 0
    previous_message_sha256: str = "0" * 64
    seen_nonce_sha256: set[str] = field(default_factory=set)
    pending: PendingRequest | None = None

    def __post_init__(self) -> None:
        require(AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY, "E_AUTH_LANE_ACTIVATION_NOT_READY")
        self.runtime = load_runtime_module()
        self.session = load_session_module()
        _endpoint, _credential, self.message_schema = self.runtime.load_schemas()
        self.coordinator_public_key = self.sshsig.read_public_key(
            self.coordinator_public_key_path, self.coordinator_public_key_sha256,
        )
        self.domain_public_key = self.sshsig.read_public_key(
            self.domain_public_key_path, self.domain_public_key_sha256,
        )
        require(self.coordinator_public_key != self.domain_public_key, "E_AUTH_LANE_KEY_REUSE")

    def _validate_message(self, message: dict, now: datetime) -> None:
        foreign(
            self.runtime.validate_agent_message, message, self.message_schema,
            self.plan["source_commit"], self.plan["run_id"],
            self.plan["bindings"]["execution_contract_sha256"],
            self.plan["bindings"]["private_endpoint_manifest_content_sha256"],
            self.plan["bindings"]["runtime_credential_manifest_content_sha256"], now,
        )

    def _message(
        self, *, request: bool, command: str, payload_raw: bytes, nonce_sha256: str,
        sequence: int, previous: str, now: datetime, result: str, failure_code: str | None,
    ) -> dict:
        execution_expires = parse_time(self.plan["limits"]["execution_expires_at"], "E_AUTH_LANE_EXECUTION_EXPIRY")
        expires = min(now + timedelta(seconds=MESSAGE_LIFETIME_SECONDS), execution_expires)
        require(now < expires, "E_AUTH_LANE_MESSAGE_EXPIRY")
        message = {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_agent_message.v1",
            "packet_kind": "T22_A1_DOMAIN_AGENT_REQUEST" if request else "T22_A1_DOMAIN_AGENT_RESPONSE",
            "hashing_contract": HASHING_CONTRACT,
            "run_id": self.plan["run_id"], "source_commit": self.plan["source_commit"],
            "execution_contract_sha256": self.plan["bindings"]["execution_contract_sha256"],
            "private_endpoint_manifest_sha256": self.plan["bindings"]["private_endpoint_manifest_content_sha256"],
            "runtime_credential_manifest_sha256": self.plan["bindings"]["runtime_credential_manifest_content_sha256"],
            "domain_id": self.plan["domain_id"],
            "direction": "COORDINATOR_TO_DOMAIN" if request else "DOMAIN_TO_COORDINATOR",
            "sequence": sequence, "previous_message_sha256": previous,
            "nonce_sha256": nonce_sha256, "issued_at": utc_text(now), "expires_at": utc_text(expires),
            "command": command, "payload_sha256": hashlib.sha256(payload_raw).hexdigest(),
            "result": result, "failure_code": failure_code,
            "signature_binding": {
                "signer_role": "COORDINATOR_RUNTIME" if request else "DOMAIN_OPERATOR",
                "signer_public_key_sha256": self.coordinator_public_key_sha256 if request else self.domain_public_key_sha256,
                "signature_scheme": "OPENSSH_SSHSIG_ED25519",
                "signature_namespace": self.session.REQUEST_NAMESPACE if request else self.session.RESPONSE_NAMESPACE,
                "detached_signature_required": True, "signature_embedded": False,
            },
            "raw_endpoint_embedded": False, "credential_or_secret_embedded": False,
            "arbitrary_command_or_shell_allowed": False, "execution_or_production_claim": False,
        }
        message["content_sha256"] = self.runtime.digest(self.runtime.MESSAGE_DOMAIN, message)
        return message

    def stage_request(self, decoded: dict, now: datetime) -> PendingRequest:
        require(self.pending is None and self.state not in {"TERMINAL_SUCCEEDED", "TERMINAL_FAILED"}, "E_AUTH_LANE_SESSION_BUSY_OR_TERMINAL")
        message, raw = decoded["message"], decoded["message_raw"]
        payload, signature = decoded["payload"], decoded["signature_raw"]
        self._validate_message(message, now)
        require(message["packet_kind"] == "T22_A1_DOMAIN_AGENT_REQUEST", "E_AUTH_LANE_REQUEST_KIND")
        require(message["domain_id"] == self.plan["domain_id"], "E_AUTH_LANE_REQUEST_DOMAIN")
        require(message["sequence"] == self.next_sequence, "E_AUTH_LANE_REQUEST_SEQUENCE")
        require(message["previous_message_sha256"] == self.previous_message_sha256, "E_AUTH_LANE_REQUEST_CHAIN")
        require(message["nonce_sha256"] not in self.seen_nonce_sha256, "E_AUTH_LANE_NONCE_REPLAY")
        require(message["signature_binding"]["signer_public_key_sha256"] == self.coordinator_public_key_sha256, "E_AUTH_LANE_COORDINATOR_KEY")
        self.sshsig.verify(raw, signature, self.coordinator_public_key, "coordinator", self.session.REQUEST_NAMESPACE)
        payload = validate_request_payload(payload, self.plan, message["command"])
        if payload["mode"] == "EMERGENCY_CLEANUP":
            proposed = "TERMINAL_FAILED"
        else:
            proposed = foreign(
                self.session.next_state, self.plan["domain_id"],
                self.plan["role"]["fault_target_domain_id"], self.state, message["command"],
            )
        self.pending = PendingRequest(message=message, payload=payload, proposed_state=proposed)
        return self.pending

    def build_request(
        self, command: str, payload: dict, now: datetime, private_key_path: Path,
    ) -> bytes:
        payload_raw = canonical_line(validate_request_payload(payload, self.plan, command))
        nonce = hashlib.sha256(
            secrets.token_bytes(32) + canonical({
                "run_id": self.plan["run_id"], "domain_id": self.plan["domain_id"],
                "sequence": self.next_sequence, "payload_sha256": hashlib.sha256(payload_raw).hexdigest(),
            })
        ).hexdigest()
        message = self._message(
            request=True, command=command, payload_raw=payload_raw, nonce_sha256=nonce,
            sequence=self.next_sequence, previous=self.previous_message_sha256, now=now,
            result="REQUESTED", failure_code=None,
        )
        raw = canonical_line(message)
        signature = self.sshsig.sign(raw, private_key_path, self.session.REQUEST_NAMESPACE)
        transport = load_transport_module()
        frame = foreign(
            transport.encode_message_frame, "COORDINATOR_TO_DOMAIN", self.plan["domain_id"],
            raw, signature, payload_raw,
        )
        decoded = foreign(
            transport.decode_message_frame, frame, "COORDINATOR_TO_DOMAIN", self.plan["domain_id"],
            self.plan["run_id"], self.plan["source_commit"],
            self.plan["bindings"]["execution_contract_sha256"],
        )
        self.stage_request(decoded, now)
        return frame

    def build_response(
        self, payload: dict, result: str, failure_code: str | None,
        now: datetime, private_key_path: Path,
    ) -> bytes:
        require(self.pending is not None, "E_AUTH_LANE_NO_PENDING_REQUEST")
        payload_raw = canonical_line(payload)
        request = self.pending.message
        require(hashlib.sha256(payload_raw).hexdigest() != request["payload_sha256"], "E_AUTH_LANE_RESPONSE_PAYLOAD_REUSE")
        message = self._message(
            request=False, command=request["command"], payload_raw=payload_raw,
            nonce_sha256=request["nonce_sha256"], sequence=request["sequence"] + 1,
            previous=request["content_sha256"], now=now, result=result, failure_code=failure_code,
        )
        raw = canonical_line(message)
        signature = self.sshsig.sign(raw, private_key_path, self.session.RESPONSE_NAMESPACE)
        transport = load_transport_module()
        return foreign(
            transport.encode_message_frame, "DOMAIN_TO_COORDINATOR", self.plan["domain_id"],
            raw, signature, payload_raw,
        )

    def accept_response(
        self, frame: bytes, now: datetime, payload_validator: Callable[[dict, str, str], dict],
    ) -> dict:
        require(self.pending is not None, "E_AUTH_LANE_NO_PENDING_REQUEST")
        transport = load_transport_module()
        decoded = foreign(
            transport.decode_message_frame, frame, "DOMAIN_TO_COORDINATOR", self.plan["domain_id"],
            self.plan["run_id"], self.plan["source_commit"],
            self.plan["bindings"]["execution_contract_sha256"],
        )
        message, raw = decoded["message"], decoded["message_raw"]
        request = self.pending.message
        self._validate_message(message, now)
        require(message["packet_kind"] == "T22_A1_DOMAIN_AGENT_RESPONSE", "E_AUTH_LANE_RESPONSE_KIND")
        require(message["sequence"] == request["sequence"] + 1, "E_AUTH_LANE_RESPONSE_SEQUENCE")
        require(message["previous_message_sha256"] == request["content_sha256"], "E_AUTH_LANE_RESPONSE_CHAIN")
        require(message["nonce_sha256"] == request["nonce_sha256"], "E_AUTH_LANE_RESPONSE_NONCE")
        require(message["command"] == request["command"], "E_AUTH_LANE_RESPONSE_COMMAND")
        require(message["payload_sha256"] != request["payload_sha256"], "E_AUTH_LANE_RESPONSE_PAYLOAD_REUSE")
        require(message["signature_binding"]["signer_public_key_sha256"] == self.domain_public_key_sha256, "E_AUTH_LANE_DOMAIN_KEY")
        self.sshsig.verify(
            raw, decoded["signature_raw"], self.domain_public_key,
            self.plan["domain_id"], self.session.RESPONSE_NAMESPACE,
        )
        payload = payload_validator(decoded["payload"], message["result"], message["failure_code"])
        self.seen_nonce_sha256.add(request["nonce_sha256"])
        self.next_sequence += 2
        self.previous_message_sha256 = message["content_sha256"]
        self.state = "TERMINAL_FAILED" if message["result"] == "FAILED" else self.pending.proposed_state
        self.pending = None
        return payload


class ServerBootstrapExchange:
    """One-domain, one-run bootstrap frame handoff with explicit zeroization."""

    def __init__(self) -> None:
        require(AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY, "E_AUTH_LANE_ACTIVATION_NOT_READY")
        self.incoming_secret: bytearray | None = None
        self.incoming_frame_sha256: str | None = None
        self.outgoing_frame: bytearray | None = None

    def publish(self, secret: bytearray) -> str:
        require(self.outgoing_frame is None and self.incoming_secret is None, "E_AUTH_LANE_BOOTSTRAP_DUPLICATE")
        transport = load_transport_module()
        frame = foreign(transport.encode_secret_frame, secret)
        self.outgoing_frame = bytearray(frame)
        return hashlib.sha256(frame).hexdigest()

    def install(self, frame: bytes, expected_frame_sha256: str) -> None:
        require(self.incoming_secret is None and self.outgoing_frame is None, "E_AUTH_LANE_BOOTSTRAP_DUPLICATE")
        require(hashlib.sha256(frame).hexdigest() == expected_frame_sha256, "E_AUTH_LANE_BOOTSTRAP_FRAME_BINDING")
        require(len(frame) >= 45, "E_AUTH_LANE_BOOTSTRAP_FRAME")
        transport = load_transport_module()
        secret = foreign(transport.decode_secret_frame, frame, frame[13:45].hex())
        self.incoming_secret = secret
        self.incoming_frame_sha256 = expected_frame_sha256

    def consume(self) -> tuple[bytearray, str]:
        require(self.incoming_secret is not None and is_sha256(self.incoming_frame_sha256), "E_AUTH_LANE_BOOTSTRAP_MISSING")
        secret, frame_sha256 = self.incoming_secret, self.incoming_frame_sha256
        self.incoming_secret = None
        self.incoming_frame_sha256 = None
        assert frame_sha256 is not None
        return secret, frame_sha256

    def take_outgoing(self, expected_frame_sha256: str) -> bytearray:
        require(
            self.outgoing_frame is not None
            and hashlib.sha256(self.outgoing_frame).hexdigest() == expected_frame_sha256,
            "E_AUTH_LANE_BOOTSTRAP_OUTGOING_BINDING",
        )
        frame = self.outgoing_frame
        self.outgoing_frame = None
        return frame

    def clear(self) -> None:
        transport = load_transport_module()
        if self.incoming_secret is not None:
            foreign(transport.zeroize, self.incoming_secret)
            self.incoming_secret = None
        if self.outgoing_frame is not None:
            self.outgoing_frame[:] = b"\0" * len(self.outgoing_frame)
            self.outgoing_frame = None
        self.incoming_frame_sha256 = None


class CoordinatorBootstrapStore:
    """Memory-only coordinator copy used for the two followers and one restart."""

    def __init__(self) -> None:
        require(AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY, "E_AUTH_LANE_ACTIVATION_NOT_READY")
        self.frame: bytearray | None = None
        self.frame_sha256: str | None = None

    def capture(self, frame: bytes, expected_frame_sha256: str) -> None:
        require(self.frame is None, "E_AUTH_LANE_COORDINATOR_BOOTSTRAP_DUPLICATE")
        require(hashlib.sha256(frame).hexdigest() == expected_frame_sha256 and len(frame) >= 45, "E_AUTH_LANE_COORDINATOR_BOOTSTRAP_BINDING")
        transport = load_transport_module()
        secret = foreign(transport.decode_secret_frame, frame, frame[13:45].hex())
        foreign(transport.zeroize, secret)
        self.frame = bytearray(frame)
        self.frame_sha256 = expected_frame_sha256

    def outbound(self) -> tuple[bytes, str]:
        require(self.frame is not None and is_sha256(self.frame_sha256), "E_AUTH_LANE_COORDINATOR_BOOTSTRAP_MISSING")
        require(hashlib.sha256(self.frame).hexdigest() == self.frame_sha256, "E_AUTH_LANE_COORDINATOR_BOOTSTRAP_MUTATED")
        assert self.frame_sha256 is not None
        return bytes(self.frame), self.frame_sha256

    def clear(self) -> None:
        if self.frame is not None:
            self.frame[:] = b"\0" * len(self.frame)
            self.frame = None
        self.frame_sha256 = None


@dataclass
class DomainReply:
    response_frame: bytes
    outgoing_secret_frame: bytearray | None

    def clear_secret(self) -> None:
        if self.outgoing_secret_frame is not None:
            self.outgoing_secret_frame[:] = b"\0" * len(self.outgoing_secret_frame)
            self.outgoing_secret_frame = None


class DomainAgentCore:
    """Authenticated request gate around one already-constructed fixed executor."""

    def __init__(
        self, plan: dict, readiness: dict, executor, backend, exchange: ServerBootstrapExchange,
        coordinator_public_key_path: Path, domain_public_key_path: Path,
        domain_private_key_path: Path, clock: Callable[[], datetime],
    ) -> None:  # noqa: ANN001
        require(AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY, "E_AUTH_LANE_ACTIVATION_NOT_READY")
        placement = readiness.get("credential_placement", {})
        coordinator_sha256 = placement.get("coordinator_trust_material", {}).get("runtime_public_key_sha256")
        domain_sha256 = placement.get("domain_operator_public_key_sha256")
        require(is_sha256(coordinator_sha256) and is_sha256(domain_sha256), "E_AUTH_LANE_READINESS_KEY_BINDING")
        tool = plan.get("tools", {}).get("ssh-keygen", {})
        self.sshsig = SshSigTool(tool.get("path"), tool.get("sha256"))
        self.domain_public_key = self.sshsig.validate_key_pair(
            domain_private_key_path, domain_public_key_path, domain_sha256,
        )
        self.session = SessionMachine(
            plan, coordinator_public_key_path, coordinator_sha256,
            domain_public_key_path, domain_sha256, self.sshsig,
        )
        self.plan, self.executor, self.backend, self.exchange = plan, executor, backend, exchange
        self.domain_private_key_path, self.clock = domain_private_key_path, clock
        self.terminal_cleanup: dict | None = None
        self.prepared_at: datetime | None = None

    def _decode_request(self, frame: bytes, now: datetime) -> PendingRequest:
        transport = load_transport_module()
        decoded = foreign(
            transport.decode_message_frame, frame, "COORDINATOR_TO_DOMAIN", self.plan["domain_id"],
            self.plan["run_id"], self.plan["source_commit"],
            self.plan["bindings"]["execution_contract_sha256"],
        )
        return self.session.stage_request(decoded, now)

    def _cleanup(self) -> dict:
        if self.terminal_cleanup is None:
            try:
                value = self.backend.abort_cleanup()
            except Exception:
                value = {"all_owned_processes_cleaned": False, "all_owned_ports_released": False}
            self.exchange.clear()
            self.terminal_cleanup = {
                "all_owned_processes_cleaned": value.get("all_owned_processes_cleaned") is True,
                "all_owned_ports_released": value.get("all_owned_ports_released") is True,
            }
        return self.terminal_cleanup

    def prepare(self, request_frame: bytes, received_at: datetime) -> PendingRequest:
        pending = self._decode_request(request_frame, received_at)
        self.prepared_at = received_at
        return pending

    def execute_prepared(self, incoming_secret_frame: bytes | None) -> DomainReply:
        require(self.session.pending is not None and self.prepared_at is not None, "E_AUTH_LANE_REQUEST_NOT_PREPARED")
        pending = self.session.pending
        received_at = self.prepared_at
        command, payload = pending.message["command"], pending.payload
        outgoing: bytearray | None = None
        try:
            direction = payload["secret_frame_direction"]
            if direction == "COORDINATOR_TO_DOMAIN":
                require(isinstance(incoming_secret_frame, bytes), "E_AUTH_LANE_BOOTSTRAP_REQUIRED")
                self.exchange.install(incoming_secret_frame, payload["secret_frame_sha256"])
            else:
                require(incoming_secret_frame is None, "E_AUTH_LANE_BOOTSTRAP_UNEXPECTED")
            if payload["mode"] == "EMERGENCY_CLEANUP":
                cleanup = self._cleanup()
                response_payload = emergency_cleanup_payload(self.plan, cleanup)
                validate_cleanup_payload(response_payload, self.plan)
                result, failure_code = "SUCCEEDED", None
            else:
                receipt = self.executor.execute(command, received_at)
                _bound_payload(receipt, self.plan, "E_AUTH_LANE_RECEIPT_BINDING")
                require(
                    receipt.get("command") == command and receipt.get("result") == "SUCCEEDED"
                    and receipt.get("failure_code") is None and is_sha256(receipt.get("content_sha256")),
                    "E_AUTH_LANE_RECEIPT_RESULT",
                )
                observed_secret = receipt.get("observation", {}).get("secret_frame_sha256")
                if direction == "DOMAIN_TO_COORDINATOR":
                    require(is_sha256(observed_secret), "E_AUTH_LANE_BOOTSTRAP_RECEIPT")
                    outgoing = self.exchange.take_outgoing(observed_secret)
                elif direction == "COORDINATOR_TO_DOMAIN":
                    require(observed_secret == payload["secret_frame_sha256"], "E_AUTH_LANE_BOOTSTRAP_RECEIPT")
                response_payload, result, failure_code = receipt, "SUCCEEDED", None
            completed_at = self.clock()
            response = self.session.build_response(
                response_payload, result, failure_code, completed_at, self.domain_private_key_path,
            )
            self.session.accept_response(
                response, completed_at,
                lambda value, observed_result, observed_code: value
                if observed_result == result and observed_code == failure_code else (_ for _ in ()).throw(SafeFailure("E_AUTH_LANE_LOCAL_RESPONSE")),
            )
            self.prepared_at = None
            return DomainReply(response, outgoing)
        except Exception as error:
            if outgoing is not None:
                outgoing[:] = b"\0" * len(outgoing)
            cleanup = self._cleanup()
            code = stable_code(error)
            response_payload = failure_payload(self.plan, command, code, cleanup)
            completed_at = self.clock()
            try:
                response = self.session.build_response(
                    response_payload, "FAILED", code, completed_at, self.domain_private_key_path,
                )
                self.session.accept_response(
                    response, completed_at,
                    lambda value, observed_result, observed_code: validate_failure_payload(value, self.plan, command)
                    if observed_result == "FAILED" and observed_code == code else (_ for _ in ()).throw(SafeFailure("E_AUTH_LANE_LOCAL_FAILURE_RESPONSE")),
                )
                self.prepared_at = None
            except Exception:
                self.session.state = "TERMINAL_FAILED"
                self.session.pending = None
                self.prepared_at = None
                raise SafeFailure(code) from error
            return DomainReply(response, None)

    def handle(self, request_frame: bytes, incoming_secret_frame: bytes | None, received_at: datetime) -> DomainReply:
        self.prepare(request_frame, received_at)
        return self.execute_prepared(incoming_secret_frame)

    def fatal_abort(self) -> dict:
        self.session.state = "TERMINAL_FAILED"
        self.session.pending = None
        self.prepared_at = None
        return self._cleanup()


class RoundTrip(Protocol):
    def exchange(
        self, request_frame: bytes, incoming_secret_frame: bytes | None,
        expect_outgoing_secret: bool,
    ) -> tuple[bytes, bytes | None, datetime]: ...
    def close(self) -> None: ...


def _receive_message_until(tls_socket: ssl.SSLSocket, deadline: datetime, clock: Callable[[], datetime]) -> bytes:
    """Wait across bounded idle timeouts, but never resume a partial frame."""
    transport = load_transport_module()
    header = bytearray()
    while not header:
        require(clock() < deadline, "E_AUTH_LANE_RESPONSE_DEADLINE")
        try:
            chunk = tls_socket.recv(12)
        except (socket.timeout, TimeoutError):
            continue
        except (OSError, ssl.SSLError) as error:
            raise SafeFailure("E_AUTH_LANE_RESPONSE_IO") from error
        require(chunk, "E_AUTH_LANE_RESPONSE_IO")
        header.extend(chunk)
    require(len(header) <= 12, "E_AUTH_LANE_RESPONSE_HEADER")
    while len(header) < 12:
        try:
            chunk = tls_socket.recv(12 - len(header))
        except (OSError, ssl.SSLError) as error:
            raise SafeFailure("E_AUTH_LANE_RESPONSE_HEADER") from error
        require(chunk, "E_AUTH_LANE_RESPONSE_HEADER")
        header.extend(chunk)
    require(bytes(header[:8]) == transport.MESSAGE_MAGIC, "E_AUTH_LANE_RESPONSE_HEADER")
    length = struct.unpack("!I", header[8:12])[0]
    require(0 < length <= transport.MAX_MESSAGE_FRAME_BYTES, "E_AUTH_LANE_RESPONSE_LENGTH")
    body = bytearray()
    while len(body) < length:
        try:
            chunk = tls_socket.recv(length - len(body))
        except (OSError, ssl.SSLError) as error:
            raise SafeFailure("E_AUTH_LANE_RESPONSE_BODY") from error
        require(chunk, "E_AUTH_LANE_RESPONSE_BODY")
        body.extend(chunk)
    return bytes(header + body)


class PersistentSocketRoundTrip:
    """One mutually authenticated connection per domain; commands are never retried."""

    def __init__(
        self, coordinator_plan: dict, domain_plan: dict,
        expected_domain_certificate_der_sha256: str,
        clock: Callable[[], datetime], timeout_seconds: float = 30.0,
    ) -> None:
        require(AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY, "E_AUTH_LANE_ACTIVATION_NOT_READY")
        self.transport = load_transport_module()
        require(
            self.transport.TRANSPORT_ACTIVATION_READY
            and self.transport.SOCKET_ADAPTER_ACTIVATION_READY,
            "E_AUTH_LANE_TRANSPORT_ACTIVATION_NOT_READY",
        )
        self.coordinator_plan, self.domain_plan = coordinator_plan, domain_plan
        self.expected_domain_certificate_der_sha256 = expected_domain_certificate_der_sha256
        self.clock, self.timeout_seconds = clock, timeout_seconds
        self.socket: ssl.SSLSocket | None = None

    def _socket(self) -> ssl.SSLSocket:
        if self.socket is None:
            self.socket = foreign(
                self.transport.connect_coordinator_to_domain,
                self.coordinator_plan, self.domain_plan,
                self.expected_domain_certificate_der_sha256, self.timeout_seconds,
            )
        return self.socket

    def exchange(
        self, request_frame: bytes, incoming_secret_frame: bytes | None,
        expect_outgoing_secret: bool,
    ) -> tuple[bytes, bytes | None, datetime]:
        tls_socket = self._socket()
        try:
            foreign(self.transport.send_message_frame, tls_socket, request_frame)
            if incoming_secret_frame is not None:
                foreign(self.transport.send_secret_frame, tls_socket, incoming_secret_frame)
            response = _receive_message_until(
                tls_socket,
                parse_time(self.domain_plan["limits"]["execution_expires_at"], "E_AUTH_LANE_EXECUTION_EXPIRY"),
                self.clock,
            )
            outgoing = foreign(self.transport.receive_secret_frame, tls_socket) if expect_outgoing_secret else None
            return response, outgoing, self.clock()
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self.socket is not None:
            self.socket.close()
            self.socket = None


class AuthenticatedDomainLane:
    """Source-bound runner lane using strict receipt replay and signed transport."""

    synthetic_only = False

    def __init__(
        self, coordinator_plan: dict, plan: dict, readiness: dict,
        coordinator_public_key_path: Path, coordinator_private_key_path: Path,
        domain_public_key_path: Path, roundtrip: RoundTrip,
        bootstrap_store: CoordinatorBootstrapStore, clock: Callable[[], datetime],
    ) -> None:
        require(AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY, "E_AUTH_LANE_ACTIVATION_NOT_READY")
        transport = load_transport_module()
        foreign(transport.validate_connection_plans, coordinator_plan, plan)
        placement = readiness.get("credential_placement", {})
        coordinator_sha256 = placement.get("coordinator_trust_material", {}).get("runtime_public_key_sha256")
        domain_sha256 = placement.get("domain_operator_public_key_sha256")
        require(is_sha256(coordinator_sha256) and is_sha256(domain_sha256), "E_AUTH_LANE_READINESS_KEY_BINDING")
        tool = coordinator_plan.get("tools", {}).get("ssh-keygen", {})
        sshsig = SshSigTool(tool.get("path"), tool.get("sha256"))
        sshsig.validate_key_pair(coordinator_private_key_path, coordinator_public_key_path, coordinator_sha256)
        self.session = SessionMachine(
            plan, coordinator_public_key_path, coordinator_sha256,
            domain_public_key_path, domain_sha256, sshsig,
        )
        self.domain_id, self.plan = plan["domain_id"], plan
        self.coordinator_private_key_path = coordinator_private_key_path
        self.roundtrip, self.bootstrap_store = roundtrip, bootstrap_store
        self.clock = clock
        self.executor_module = load_executor_module()
        self.receipt_state, self.receipt_previous = "CREATED", "0" * 64
        self.receipt_observations: dict[str, dict] = {}
        self.receipt_spend, self.receipt_sequence = 0, 0
        self.remote_cleanup_confirmed = False

    def _strict_receipt(self, value: dict, command: str) -> dict:
        foreign(
            self.executor_module.validate_receipt, value, self.plan, self.receipt_state,
            self.receipt_sequence, self.receipt_previous, self.receipt_observations,
            self.receipt_spend,
        )
        require(value["command"] == command and value["synthetic_backend"] is False, "E_AUTH_LANE_REAL_RECEIPT")
        self.receipt_state = value["state_after"]
        self.receipt_previous = value["content_sha256"]
        self.receipt_observations[command] = value["observation"]
        self.receipt_spend = value["cumulative_spend_usd_cents"]
        self.receipt_sequence += 1
        return value

    def _response_validator(self, command: str, mode: str):  # noqa: ANN202
        def validate(value: dict, result: str, code: str | None) -> dict:
            if result == "FAILED":
                require(isinstance(code, str), "E_AUTH_LANE_FAILURE_CODE")
                failure = validate_failure_payload(value, self.plan, command)
                require(failure["failure_code"] == code, "E_AUTH_LANE_FAILURE_CODE_BINDING")
                return failure
            require(result == "SUCCEEDED" and code is None, "E_AUTH_LANE_RESPONSE_RESULT")
            if mode == "EMERGENCY_CLEANUP":
                return validate_cleanup_payload(value, self.plan)
            return self._strict_receipt(value, command)
        return validate

    def _exchange(self, command: str, now: datetime, mode: str) -> dict:
        inbound: bytes | None = None
        secret_sha256: str | None = None
        direction = "NONE" if mode == "EMERGENCY_CLEANUP" else secret_policy(
            self.domain_id, self.plan["role"]["fault_target_domain_id"], command,
        )
        if direction == "COORDINATOR_TO_DOMAIN":
            inbound, secret_sha256 = self.bootstrap_store.outbound()
        payload = request_payload(self.plan, command, mode, secret_sha256)
        request = self.session.build_request(command, payload, now, self.coordinator_private_key_path)
        response, outgoing, received_at = self.roundtrip.exchange(
            request, inbound, direction == "DOMAIN_TO_COORDINATOR",
        )
        try:
            value = self.session.accept_response(
                response, received_at, self._response_validator(command, mode),
            )
            if value.get("schema") == "agent_bridge.biocortex.track_b.t22_a1.domain_command_failure.v1":
                self.remote_cleanup_confirmed = (
                    value["all_owned_processes_cleaned"] is True
                    and value["all_owned_ports_released"] is True
                )
                raise SafeFailure(value["failure_code"])
            if direction == "DOMAIN_TO_COORDINATOR":
                require(isinstance(outgoing, bytes), "E_AUTH_LANE_BOOTSTRAP_RESPONSE_MISSING")
                observed_sha256 = value["observation"]["secret_frame_sha256"]
                self.bootstrap_store.capture(outgoing, observed_sha256)
            else:
                require(outgoing is None, "E_AUTH_LANE_BOOTSTRAP_RESPONSE_UNEXPECTED")
            if command == "RESTART_OWNED_SERVICE_SET":
                self.bootstrap_store.clear()
            return value
        finally:
            if mode == "EMERGENCY_CLEANUP" or self.session.state in {"TERMINAL_SUCCEEDED", "TERMINAL_FAILED"}:
                self.roundtrip.close()

    def dispatch(self, command: str, now: datetime) -> dict:
        return self._exchange(command, now, "NORMAL")

    def abort_cleanup(self) -> dict:
        self.bootstrap_store.clear()
        if self.remote_cleanup_confirmed or self.receipt_state in {"CLEANED", "TERMINAL_SUCCEEDED"}:
            self.roundtrip.close()
            return {"all_owned_processes_cleaned": True, "all_owned_ports_released": True}
        if self.session.pending is not None or self.session.state in {"TERMINAL_SUCCEEDED", "TERMINAL_FAILED"}:
            self.roundtrip.close()
            return {"all_owned_processes_cleaned": False, "all_owned_ports_released": False}
        now = self.clock()
        try:
            value = self._exchange("CLEANUP_OWNED_PROCESSES", now, "EMERGENCY_CLEANUP")
            cleaned = value["all_owned_processes_cleaned"] is True and value["all_owned_ports_released"] is True
            self.remote_cleanup_confirmed = cleaned
            return {"all_owned_processes_cleaned": cleaned, "all_owned_ports_released": cleaned}
        except Exception:
            return {"all_owned_processes_cleaned": False, "all_owned_ports_released": False}


class DomainAgentServer:
    """One accepted mTLS connection, then the exact per-domain command chain."""

    def __init__(
        self, plan: dict, coordinator_route_plan: dict, core: DomainAgentCore,
        clock: Callable[[], datetime], timeout_seconds: float = 30.0,
    ) -> None:
        require(AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY, "E_AUTH_LANE_ACTIVATION_NOT_READY")
        self.transport = load_transport_module()
        require(
            self.transport.TRANSPORT_ACTIVATION_READY
            and self.transport.SOCKET_ADAPTER_ACTIVATION_READY,
            "E_AUTH_LANE_TRANSPORT_ACTIVATION_NOT_READY",
        )
        self.plan, self.coordinator_route_plan, self.core = plan, coordinator_route_plan, core
        self.clock, self.timeout_seconds = clock, timeout_seconds

    def serve(self) -> dict:
        listener = None
        tls_socket = None
        try:
            listener = foreign(self.transport.open_domain_agent_listener, self.plan, self.timeout_seconds)
            tls_socket = foreign(listener.accept_exact_coordinator, self.coordinator_route_plan)
            listener = None
            while self.core.session.state not in {"TERMINAL_SUCCEEDED", "TERMINAL_FAILED"}:
                request = _receive_message_until(
                    tls_socket,
                    parse_time(self.plan["limits"]["execution_expires_at"], "E_AUTH_LANE_EXECUTION_EXPIRY"),
                    self.clock,
                )
                pending = self.core.prepare(request, self.clock())
                payload = pending.payload
                incoming = foreign(self.transport.receive_secret_frame, tls_socket) \
                    if payload.get("secret_frame_direction") == "COORDINATOR_TO_DOMAIN" else None
                reply = self.core.execute_prepared(incoming)
                try:
                    foreign(self.transport.send_message_frame, tls_socket, reply.response_frame)
                    if reply.outgoing_secret_frame is not None:
                        foreign(self.transport.send_secret_frame, tls_socket, bytes(reply.outgoing_secret_frame))
                finally:
                    reply.clear_secret()
            return self.core.terminal_cleanup or {
                "all_owned_processes_cleaned": self.core.session.state == "TERMINAL_SUCCEEDED",
                "all_owned_ports_released": self.core.session.state == "TERMINAL_SUCCEEDED",
            }
        except Exception:
            return self.core.fatal_abort()
        finally:
            if tls_socket is not None:
                tls_socket.close()
            if listener is not None:
                listener.close()


def coordinator_route_plan(domain_plan: dict, endpoint_manifest: dict) -> dict:
    rows = endpoint_manifest.get("domains", [])
    require(isinstance(rows, list) and len(rows) == 3, "E_AUTH_LANE_ENDPOINT_SET")
    row = next((value for value in rows if value.get("domain_id") == "domain-1"), None)
    require(isinstance(row, dict), "E_AUTH_LANE_COORDINATOR_ENDPOINT")
    address = row["overlay_ip"]
    host = f"[{address}]" if ":" in address else address
    return {
        "domain_id": "domain-1", "run_id": domain_plan["run_id"],
        "source_commit": domain_plan["source_commit"], "bindings": domain_plan["bindings"],
        "network": {"agent_control_endpoint": f"https://{host}:{row['agent_control_port']}"},
    }


def build_live_domain_core(
    plan: dict, execution: dict, endpoint_manifest: dict, readiness: dict,
    coordinator_public_key_path: Path, domain_public_key_path: Path,
    domain_private_key_path: Path, clock: Callable[[], datetime],
) -> DomainAgentCore:
    """Construct the real backend only after every independent activation gate opens."""
    require(AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY, "E_AUTH_LANE_ACTIVATION_NOT_READY")
    backend_module = load_backend_module()
    executor_module = load_executor_module()
    require(
        backend_module.LIVE_LOCAL_BACKEND_ACTIVATION_READY
        and executor_module.EXECUTOR_ACTIVATION_READY,
        "E_AUTH_LANE_EXECUTION_COMPONENT_ACTIVATION_NOT_READY",
    )
    exchange = ServerBootstrapExchange()
    runtime = backend_module.BoundedLocalProcessRuntime()
    control = backend_module.EtcdOpenBaoControl(plan)
    backend = backend_module.LiveLocalBackend(plan, runtime, control, exchange)
    executor = executor_module.FixedCommandExecutor(
        plan, execution, endpoint_manifest, readiness, backend,
    )
    return DomainAgentCore(
        plan, readiness, executor, backend, exchange,
        coordinator_public_key_path, domain_public_key_path,
        domain_private_key_path, clock,
    )


def status() -> dict:
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.authenticated_domain_lane_status.v0",
        "status": "AUTHENTICATED_REAL_DOMAIN_LANE_PRESENT_FINAL_RUNTIME_ACTIVATION_CLOSED",
        "authenticated_domain_lane_activation_ready": AUTHENTICATED_DOMAIN_LANE_ACTIVATION_READY,
        "message_lifetime_seconds": MESSAGE_LIFETIME_SECONDS,
        "secret_persistence_allowed": False, "automatic_retry_allowed": False,
        "arbitrary_command_or_shell_surface": False,
        "real_private_inputs_read": 0, "credential_files_read": 0,
        "network_accessed": False, "listeners_started": 0,
        "processes_started": 0, "faults_injected": 0, "spend_usd_cents": 0,
        "execution_authorized": False, "production_admissible": False,
    }


if __name__ == "__main__":
    print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
