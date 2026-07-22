"""Fail-closed fixed-command executor core for one T22-A1 domain.

The core revalidates an exact private workload plan, enforces its lifecycle,
normalizes bounded observations/effects, and emits hash-bound private receipts.
No live backend is present yet; non-synthetic backends remain hard-disabled.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[2]
PLAN_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_workload_plan_v1.py"
SESSION_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_agent_session_v1.py"
RECEIPT_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/domain-command-receipt/v1\0"
EXECUTOR_ACTIVATION_READY = False


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


def load_plan_module():
    return load_module("t22a1_plan_for_executor", PLAN_SOURCE)


def load_session_module():
    return load_module("t22a1_session_for_executor", SESSION_SOURCE)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def receipt_digest(value: object) -> str:
    return hashlib.sha256(RECEIPT_DOMAIN + canonical(value)).hexdigest()


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and value != "0" * 64 and all(character in "0123456789abcdef" for character in value)


def parse_time(value: object, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise SafeFailure(code) from error
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0, code)
    return parsed


def utc_text(value: datetime) -> str:
    require(value.tzinfo is not None and value.utcoffset().total_seconds() == 0, "E_DOMAIN_EXECUTOR_TIMEZONE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


EFFECT_KEYS = {
    "network_accessed", "listeners_started", "listeners_stopped",
    "service_processes_started", "service_processes_stopped",
    "faults_injected", "spend_usd_cents",
}
RECEIPT_KEYS = {
    "schema", "packet_kind", "run_id", "source_commit",
    "execution_contract_sha256", "domain_workload_plan_sha256",
    "runtime_readiness_packet_sha256", "domain_id", "sequence",
    "previous_receipt_sha256", "command", "state_before", "state_after",
    "result", "failure_code", "observation", "effects",
    "cumulative_spend_usd_cents", "synthetic_backend",
    "arbitrary_command_or_shell_used", "automatic_retry_allowed",
    "production_admissible", "observed_at", "content_sha256",
}

OBSERVATION_KEYS = {
    "PREFLIGHT": {
        "tool_hash_set_verified", "credential_hash_and_key_match_verified",
        "owned_paths_private_and_empty", "exact_ports_available",
        "ambient_credentials_absent", "preflight_receipt_sha256",
    },
    "START_OWNED_CLUSTER_MEMBERS": {
        "etcd_process_started", "openbao_process_started", "owned_process_set_sha256",
        "process_receipt_sha256", "openbao_bootstrap_role", "secret_frame_action",
        "secret_frame_sha256", "secret_frame_persisted",
    },
    "QUERY_CLUSTER_STATE": {
        "etcd_member_count", "etcd_voter_count", "openbao_member_count",
        "openbao_voter_count", "local_etcd_healthy", "local_openbao_unsealed",
        "cluster_observation_sha256",
    },
    "EXECUTE_AUTHORIZE_CONSUME": {
        "linearizable_authorize_consume_observed", "replay_consume_rejected",
        "authorized_value_sha256", "consumed_value_sha256",
        "consume_revision_sha256", "replay_revision_sha256",
    },
    "CREATE_PREFAULT_TRANSIT_SIGNATURE": {
        "prefault_transit_signature_created", "transit_challenge_sha256",
        "transit_signature_sha256", "consumed_state_sha256",
    },
    "STOP_OWNED_SERVICE_SET": {
        "target_domain_id", "etcd_process_stopped", "openbao_process_stopped",
        "stopped_owned_process_set_sha256",
    },
    "VERIFY_SURVIVING_QUORUM_AND_STATE": {
        "surviving_two_domain_etcd_quorum_observed",
        "surviving_two_domain_openbao_available", "prefault_state_match_verified",
        "survivor_observation_sha256",
    },
    "VERIFY_POSTFAULT_TRANSIT_SIGNATURE": {
        "postfault_transit_signature_verified", "transit_challenge_sha256",
        "transit_signature_sha256",
    },
    "RESTART_OWNED_SERVICE_SET": {
        "target_domain_id", "etcd_process_restarted", "openbao_process_restarted",
        "restarted_owned_process_set_sha256", "secret_frame_action",
        "secret_frame_sha256", "secret_frame_persisted",
    },
    "VERIFY_TARGET_REJOIN": {
        "target_domain_id", "target_etcd_rejoined", "target_openbao_rejoined",
        "etcd_voter_count", "openbao_voter_count", "rejoin_observation_sha256",
    },
    "CLEANUP_OWNED_PROCESSES": {
        "all_owned_processes_stopped", "all_owned_ports_released",
        "owned_process_log_set_sha256", "owned_process_log_count",
        "cleanup_receipt_sha256", "secret_value_scan_passed",
        "exact_secret_match_count",
    },
    "TERMINAL_STATUS": {
        "lifecycle_succeeded", "command_receipt_count", "domain_evidence_head_sha256",
    },
}


class Backend(Protocol):
    synthetic_only: bool

    def preflight(self, plan: dict) -> dict: ...
    def start_owned_cluster_members(self, plan: dict) -> dict: ...
    def query_cluster_state(self, plan: dict) -> dict: ...
    def execute_authorize_consume(self, plan: dict) -> dict: ...
    def create_prefault_transit_signature(self, plan: dict) -> dict: ...
    def stop_owned_service_set(self, plan: dict) -> dict: ...
    def verify_surviving_quorum_and_state(self, plan: dict) -> dict: ...
    def verify_postfault_transit_signature(self, plan: dict) -> dict: ...
    def restart_owned_service_set(self, plan: dict) -> dict: ...
    def verify_target_rejoin(self, plan: dict) -> dict: ...
    def cleanup_owned_processes(self, plan: dict) -> dict: ...
    def terminal_status(self, plan: dict) -> dict: ...


def validate_effects(value: object) -> dict:
    require(isinstance(value, dict) and set(value) == EFFECT_KEYS, "E_DOMAIN_EXECUTOR_EFFECT_SHAPE")
    assert isinstance(value, dict)
    require(isinstance(value["network_accessed"], bool), "E_DOMAIN_EXECUTOR_NETWORK_EFFECT")
    for field in EFFECT_KEYS - {"network_accessed"}:
        require(isinstance(value[field], int) and 0 <= value[field] <= 100000, "E_DOMAIN_EXECUTOR_NUMERIC_EFFECT")
    return value


def validate_observation(command: str, value: object, plan: dict, prior: dict[str, dict]) -> dict:
    require(command in OBSERVATION_KEYS, "E_DOMAIN_EXECUTOR_COMMAND")
    require(isinstance(value, dict) and set(value) == OBSERVATION_KEYS[command], "E_DOMAIN_EXECUTOR_OBSERVATION_SHAPE")
    assert isinstance(value, dict)
    digest_fields = [field for field in value if field.endswith("_sha256")]
    require(all(is_sha256(value[field]) for field in digest_fields), "E_DOMAIN_EXECUTOR_OBSERVATION_DIGEST")
    domain_id = plan["domain_id"]
    fault_target = plan["role"]["fault_target_domain_id"]
    if command == "PREFLIGHT":
        require(all(value[field] is True for field in (
            "tool_hash_set_verified", "credential_hash_and_key_match_verified",
            "owned_paths_private_and_empty", "exact_ports_available", "ambient_credentials_absent",
        )), "E_DOMAIN_EXECUTOR_PREFLIGHT")
    elif command == "START_OWNED_CLUSTER_MEMBERS":
        require(value["etcd_process_started"] is True and value["openbao_process_started"] is True, "E_DOMAIN_EXECUTOR_PROCESS_START")
        expected_role = "LEADER_INITIALIZE_AND_HOLD_MEMORY_ONLY" if domain_id == "domain-1" else "FOLLOWER_RETRY_JOIN_AND_UNSEAL"
        expected_action = "PRODUCED_MEMORY_ONLY" if domain_id == "domain-1" else "CONSUMED_MEMORY_ONLY"
        require(value["openbao_bootstrap_role"] == expected_role and value["secret_frame_action"] == expected_action, "E_DOMAIN_EXECUTOR_BOOTSTRAP_ROLE")
        require(value["secret_frame_persisted"] is False, "E_DOMAIN_EXECUTOR_SECRET_PERSISTENCE")
    elif command == "QUERY_CLUSTER_STATE":
        require(value["etcd_member_count"] == value["etcd_voter_count"] == 3, "E_DOMAIN_EXECUTOR_ETCD_CLUSTER")
        require(value["openbao_member_count"] == value["openbao_voter_count"] == 3, "E_DOMAIN_EXECUTOR_OPENBAO_CLUSTER")
        require(value["local_etcd_healthy"] is True and value["local_openbao_unsealed"] is True, "E_DOMAIN_EXECUTOR_LOCAL_HEALTH")
    elif command == "EXECUTE_AUTHORIZE_CONSUME":
        require(domain_id == "domain-1", "E_DOMAIN_EXECUTOR_COORDINATOR_COMMAND")
        require(value["linearizable_authorize_consume_observed"] is True and value["replay_consume_rejected"] is True, "E_DOMAIN_EXECUTOR_CONSUME")
        require(value["authorized_value_sha256"] == plan["workload"]["authorized_unclaimed_value_sha256"], "E_DOMAIN_EXECUTOR_AUTHORIZED_VALUE")
        require(value["consumed_value_sha256"] == plan["workload"]["consumed_value_sha256"], "E_DOMAIN_EXECUTOR_CONSUMED_VALUE")
    elif command == "CREATE_PREFAULT_TRANSIT_SIGNATURE":
        require(domain_id == "domain-1" and value["prefault_transit_signature_created"] is True, "E_DOMAIN_EXECUTOR_PREFAULT")
        require(value["consumed_state_sha256"] == plan["workload"]["consumed_value_sha256"], "E_DOMAIN_EXECUTOR_PREFAULT_STATE")
    elif command == "STOP_OWNED_SERVICE_SET":
        require(domain_id == fault_target and value["target_domain_id"] == fault_target, "E_DOMAIN_EXECUTOR_STOP_TARGET")
        require(value["etcd_process_stopped"] is True and value["openbao_process_stopped"] is True, "E_DOMAIN_EXECUTOR_STOP")
    elif command == "VERIFY_SURVIVING_QUORUM_AND_STATE":
        require(domain_id != fault_target, "E_DOMAIN_EXECUTOR_SURVIVOR_DOMAIN")
        require(value["surviving_two_domain_etcd_quorum_observed"] is True, "E_DOMAIN_EXECUTOR_SURVIVOR_ETCD")
        require(value["surviving_two_domain_openbao_available"] is True and value["prefault_state_match_verified"] is True, "E_DOMAIN_EXECUTOR_SURVIVOR_STATE")
    elif command == "VERIFY_POSTFAULT_TRANSIT_SIGNATURE":
        require(domain_id == "domain-1" and value["postfault_transit_signature_verified"] is True, "E_DOMAIN_EXECUTOR_POSTFAULT")
        prefault = prior.get("CREATE_PREFAULT_TRANSIT_SIGNATURE")
        require(prefault is not None, "E_DOMAIN_EXECUTOR_PREFAULT_MISSING")
        require(value["transit_challenge_sha256"] == prefault["transit_challenge_sha256"], "E_DOMAIN_EXECUTOR_TRANSIT_CHALLENGE")
        require(value["transit_signature_sha256"] == prefault["transit_signature_sha256"], "E_DOMAIN_EXECUTOR_TRANSIT_SIGNATURE")
    elif command == "RESTART_OWNED_SERVICE_SET":
        require(domain_id == fault_target and value["target_domain_id"] == fault_target, "E_DOMAIN_EXECUTOR_RESTART_TARGET")
        require(value["etcd_process_restarted"] is True and value["openbao_process_restarted"] is True, "E_DOMAIN_EXECUTOR_RESTART")
        require(value["secret_frame_action"] == "CONSUMED_MEMORY_ONLY" and value["secret_frame_persisted"] is False, "E_DOMAIN_EXECUTOR_RESTART_SECRET")
    elif command == "VERIFY_TARGET_REJOIN":
        require(domain_id == fault_target and value["target_domain_id"] == fault_target, "E_DOMAIN_EXECUTOR_REJOIN_TARGET")
        require(value["target_etcd_rejoined"] is True and value["target_openbao_rejoined"] is True, "E_DOMAIN_EXECUTOR_REJOIN")
        require(value["etcd_voter_count"] == value["openbao_voter_count"] == 3, "E_DOMAIN_EXECUTOR_REJOIN_VOTERS")
    elif command == "CLEANUP_OWNED_PROCESSES":
        require(value["all_owned_processes_stopped"] is True and value["all_owned_ports_released"] is True, "E_DOMAIN_EXECUTOR_CLEANUP")
        require(value["owned_process_log_count"] >= 2 and value["secret_value_scan_passed"] is True, "E_DOMAIN_EXECUTOR_CLEANUP_EVIDENCE")
        require(value["exact_secret_match_count"] == 0, "E_DOMAIN_EXECUTOR_SECRET_SCAN")
    elif command == "TERMINAL_STATUS":
        require(
            value["lifecycle_succeeded"] is True
            and value["command_receipt_count"] == len(plan["command_policy"]["allowed_commands"]),
            "E_DOMAIN_EXECUTOR_TERMINAL",
        )
    return value


def validate_backend_result(command: str, value: object, plan: dict, prior: dict[str, dict]) -> dict:
    require(isinstance(value, dict) and set(value) == {"observation", "effects"}, "E_DOMAIN_EXECUTOR_BACKEND_RESULT")
    assert isinstance(value, dict)
    result = {
        "observation": validate_observation(command, value["observation"], plan, prior),
        "effects": validate_effects(value["effects"]),
    }
    effects = result["effects"]
    if command == "PREFLIGHT":
        require(effects == {
            "network_accessed": False, "listeners_started": 0, "listeners_stopped": 0,
            "service_processes_started": 0, "service_processes_stopped": 0,
            "faults_injected": 0, "spend_usd_cents": 0,
        }, "E_DOMAIN_EXECUTOR_PREFLIGHT_EFFECT")
    elif command == "START_OWNED_CLUSTER_MEMBERS":
        require(
            effects["network_accessed"] is True and effects["listeners_started"] >= 4
            and effects["service_processes_started"] == 2 and effects["faults_injected"] == 0,
            "E_DOMAIN_EXECUTOR_START_EFFECT",
        )
    elif command == "STOP_OWNED_SERVICE_SET":
        require(
            effects["network_accessed"] is False and effects["service_processes_stopped"] == 2
            and effects["faults_injected"] == 1,
            "E_DOMAIN_EXECUTOR_STOP_EFFECT",
        )
    elif command == "RESTART_OWNED_SERVICE_SET":
        require(
            effects["network_accessed"] is True and effects["service_processes_started"] == 2
            and effects["faults_injected"] == 0,
            "E_DOMAIN_EXECUTOR_RESTART_EFFECT",
        )
    elif command == "CLEANUP_OWNED_PROCESSES":
        require(
            effects["listeners_stopped"] >= 4 and effects["service_processes_stopped"] == 2
            and effects["faults_injected"] == 0,
            "E_DOMAIN_EXECUTOR_CLEANUP_EFFECT",
        )
    return result


def validate_receipt(
    value: object,
    plan: dict,
    expected_state: str,
    expected_sequence: int,
    expected_previous: str,
    prior_observations: dict[str, dict],
    prior_spend_usd_cents: int,
) -> dict:
    require(isinstance(value, dict) and set(value) == RECEIPT_KEYS, "E_DOMAIN_EXECUTOR_RECEIPT_SHAPE")
    assert isinstance(value, dict)
    require(value["schema"] == "agent_bridge.biocortex.track_b.t22_a1.domain_command_receipt.v1", "E_DOMAIN_EXECUTOR_RECEIPT_SCHEMA")
    require(value["packet_kind"] == "T22_A1_PRIVATE_DOMAIN_FIXED_COMMAND_RECEIPT", "E_DOMAIN_EXECUTOR_RECEIPT_KIND")
    require(value["run_id"] == plan["run_id"] and value["source_commit"] == plan["source_commit"], "E_DOMAIN_EXECUTOR_RECEIPT_RUN")
    require(value["execution_contract_sha256"] == plan["bindings"]["execution_contract_sha256"], "E_DOMAIN_EXECUTOR_RECEIPT_EXECUTION")
    require(value["domain_workload_plan_sha256"] == plan["content_sha256"], "E_DOMAIN_EXECUTOR_RECEIPT_PLAN")
    require(value["runtime_readiness_packet_sha256"] == plan["bindings"]["runtime_readiness_packet_sha256"], "E_DOMAIN_EXECUTOR_RECEIPT_READINESS")
    require(value["domain_id"] == plan["domain_id"], "E_DOMAIN_EXECUTOR_RECEIPT_DOMAIN")
    require(value["sequence"] == expected_sequence and value["previous_receipt_sha256"] == expected_previous, "E_DOMAIN_EXECUTOR_RECEIPT_CHAIN")
    require(value["state_before"] == expected_state, "E_DOMAIN_EXECUTOR_RECEIPT_STATE")
    command = value["command"]
    require(command in plan["command_policy"]["allowed_commands"], "E_DOMAIN_EXECUTOR_RECEIPT_COMMAND")
    session = load_session_module()
    try:
        expected_after = session.next_state(plan["domain_id"], plan["role"]["fault_target_domain_id"], expected_state, command)
    except RuntimeError as error:
        raise SafeFailure(str(error)) from error
    require(value["state_after"] == expected_after, "E_DOMAIN_EXECUTOR_RECEIPT_STATE")
    require(value["result"] == "SUCCEEDED" and value["failure_code"] is None, "E_DOMAIN_EXECUTOR_RECEIPT_RESULT")
    validate_observation(command, value["observation"], plan, prior_observations)
    validate_backend_result(command, {"observation": value["observation"], "effects": value["effects"]}, plan, prior_observations)
    expected_spend = prior_spend_usd_cents + value["effects"]["spend_usd_cents"]
    require(value["cumulative_spend_usd_cents"] == expected_spend, "E_DOMAIN_EXECUTOR_RECEIPT_SPEND")
    require(expected_spend <= plan["limits"]["maximum_spend_usd_cents"], "E_DOMAIN_EXECUTOR_SPEND_LIMIT")
    require(isinstance(value["synthetic_backend"], bool), "E_DOMAIN_EXECUTOR_RECEIPT_BACKEND")
    require(value["arbitrary_command_or_shell_used"] is False, "E_DOMAIN_EXECUTOR_RECEIPT_SHELL")
    require(value["automatic_retry_allowed"] is False and value["production_admissible"] is False, "E_DOMAIN_EXECUTOR_RECEIPT_CLAIMS")
    observed_at = parse_time(value["observed_at"], "E_DOMAIN_EXECUTOR_RECEIPT_TIME")
    require(observed_at < parse_time(plan["limits"]["execution_expires_at"], "E_DOMAIN_EXECUTOR_EXPIRY"), "E_DOMAIN_EXECUTOR_RECEIPT_EXPIRED")
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256")
    require(claimed == receipt_digest(unsigned), "E_DOMAIN_EXECUTOR_RECEIPT_DIGEST")
    return value


def validate_receipt_chain(values: object, plan: dict) -> dict:
    require(isinstance(values, list) and values, "E_DOMAIN_EXECUTOR_RECEIPT_CHAIN_EMPTY")
    state = "CREATED"
    previous = "0" * 64
    observations: dict[str, dict] = {}
    spend = 0
    started_at: datetime | None = None
    previous_time: datetime | None = None
    for sequence, value in enumerate(values):
        validate_receipt(value, plan, state, sequence, previous, observations, spend)
        observed_at = parse_time(value["observed_at"], "E_DOMAIN_EXECUTOR_RECEIPT_TIME")
        if started_at is None:
            started_at = observed_at
        require(previous_time is None or previous_time <= observed_at, "E_DOMAIN_EXECUTOR_RECEIPT_TIME_ORDER")
        require(int((observed_at - started_at).total_seconds()) <= plan["limits"]["maximum_runtime_seconds"], "E_DOMAIN_EXECUTOR_RECEIPT_RUNTIME")
        previous_time = observed_at
        state = value["state_after"]
        previous = value["content_sha256"]
        observations[value["command"]] = value["observation"]
        spend = value["cumulative_spend_usd_cents"]
    require(state == "TERMINAL_SUCCEEDED", "E_DOMAIN_EXECUTOR_RECEIPT_CHAIN_INCOMPLETE")
    return {
        "domain_id": plan["domain_id"],
        "receipt_count": len(values),
        "chain_head_sha256": previous,
        "state": state,
        "cumulative_spend_usd_cents": spend,
        "runtime_seconds": int((previous_time - started_at).total_seconds()),
        "synthetic_backend": any(value["synthetic_backend"] for value in values),
    }


@dataclass
class FixedCommandExecutor:
    plan: dict
    execution: dict
    endpoint_manifest: dict
    readiness: dict
    backend: Backend
    state: str = "CREATED"
    started_at: datetime | None = None
    previous_receipt_sha256: str = "0" * 64
    receipts: list[dict] = field(default_factory=list)
    observations: dict[str, dict] = field(default_factory=dict)
    total_spend_usd_cents: int = 0

    def __post_init__(self) -> None:
        plan_module = load_plan_module()
        try:
            plan_module.validate_plan(self.plan, self.execution, self.endpoint_manifest, self.readiness)
        except RuntimeError as error:
            raise SafeFailure(str(error)) from error
        require(self.backend.synthetic_only or EXECUTOR_ACTIVATION_READY, "E_DOMAIN_EXECUTOR_ACTIVATION_NOT_READY")

    def _dispatch(self, command: str) -> dict:
        if command == "PREFLIGHT":
            return self.backend.preflight(self.plan)
        if command == "START_OWNED_CLUSTER_MEMBERS":
            return self.backend.start_owned_cluster_members(self.plan)
        if command == "QUERY_CLUSTER_STATE":
            return self.backend.query_cluster_state(self.plan)
        if command == "EXECUTE_AUTHORIZE_CONSUME":
            return self.backend.execute_authorize_consume(self.plan)
        if command == "CREATE_PREFAULT_TRANSIT_SIGNATURE":
            return self.backend.create_prefault_transit_signature(self.plan)
        if command == "STOP_OWNED_SERVICE_SET":
            return self.backend.stop_owned_service_set(self.plan)
        if command == "VERIFY_SURVIVING_QUORUM_AND_STATE":
            return self.backend.verify_surviving_quorum_and_state(self.plan)
        if command == "VERIFY_POSTFAULT_TRANSIT_SIGNATURE":
            return self.backend.verify_postfault_transit_signature(self.plan)
        if command == "RESTART_OWNED_SERVICE_SET":
            return self.backend.restart_owned_service_set(self.plan)
        if command == "VERIFY_TARGET_REJOIN":
            return self.backend.verify_target_rejoin(self.plan)
        if command == "CLEANUP_OWNED_PROCESSES":
            return self.backend.cleanup_owned_processes(self.plan)
        if command == "TERMINAL_STATUS":
            return self.backend.terminal_status(self.plan)
        raise SafeFailure("E_DOMAIN_EXECUTOR_COMMAND")

    def execute(self, command: str, now: datetime) -> dict:
        require(command in self.plan["command_policy"]["allowed_commands"], "E_DOMAIN_EXECUTOR_COMMAND_NOT_ALLOWED")
        require(self.state not in {"TERMINAL_SUCCEEDED", "TERMINAL_FAILED"}, "E_DOMAIN_EXECUTOR_TERMINAL")
        require(now.tzinfo is not None and now.utcoffset().total_seconds() == 0, "E_DOMAIN_EXECUTOR_TIMEZONE")
        require(now < parse_time(self.plan["limits"]["execution_expires_at"], "E_DOMAIN_EXECUTOR_EXPIRY"), "E_DOMAIN_EXECUTOR_EXPIRED")
        if self.started_at is None:
            self.started_at = now
        runtime = int((now - self.started_at).total_seconds())
        require(0 <= runtime <= self.plan["limits"]["maximum_runtime_seconds"], "E_DOMAIN_EXECUTOR_RUNTIME_LIMIT")
        session = load_session_module()
        try:
            next_state = session.next_state(
                self.plan["domain_id"], self.plan["role"]["fault_target_domain_id"], self.state, command,
            )
        except RuntimeError as error:
            raise SafeFailure(str(error)) from error
        dispatched = False
        try:
            dispatched = True
            result = validate_backend_result(command, self._dispatch(command), self.plan, self.observations)
            effects = result["effects"]
            next_spend = self.total_spend_usd_cents + effects["spend_usd_cents"]
            require(next_spend <= self.plan["limits"]["maximum_spend_usd_cents"], "E_DOMAIN_EXECUTOR_SPEND_LIMIT")
        except Exception as error:
            if dispatched:
                self.state = "TERMINAL_FAILED"
            if isinstance(error, SafeFailure):
                raise
            raise SafeFailure("E_DOMAIN_EXECUTOR_BACKEND_FAILURE") from error
        sequence = len(self.receipts)
        receipt = {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_command_receipt.v1",
            "packet_kind": "T22_A1_PRIVATE_DOMAIN_FIXED_COMMAND_RECEIPT",
            "run_id": self.plan["run_id"],
            "source_commit": self.plan["source_commit"],
            "execution_contract_sha256": self.plan["bindings"]["execution_contract_sha256"],
            "domain_workload_plan_sha256": self.plan["content_sha256"],
            "runtime_readiness_packet_sha256": self.plan["bindings"]["runtime_readiness_packet_sha256"],
            "domain_id": self.plan["domain_id"],
            "sequence": sequence,
            "previous_receipt_sha256": self.previous_receipt_sha256,
            "command": command,
            "state_before": self.state,
            "state_after": next_state,
            "result": "SUCCEEDED",
            "failure_code": None,
            "observation": result["observation"],
            "effects": effects,
            "cumulative_spend_usd_cents": next_spend,
            "synthetic_backend": self.backend.synthetic_only,
            "arbitrary_command_or_shell_used": False,
            "automatic_retry_allowed": False,
            "production_admissible": False,
            "observed_at": utc_text(now),
        }
        receipt["content_sha256"] = receipt_digest(receipt)
        validate_receipt(
            receipt, self.plan, self.state, sequence, self.previous_receipt_sha256,
            self.observations, self.total_spend_usd_cents,
        )
        self.state = next_state
        self.total_spend_usd_cents = next_spend
        self.previous_receipt_sha256 = receipt["content_sha256"]
        self.receipts.append(receipt)
        self.observations[command] = result["observation"]
        return receipt


def status() -> dict:
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.domain_executor_core_status.v0",
        "status": "OFFLINE_FIXED_COMMAND_EXECUTOR_CORE_READY_LIVE_BACKEND_AND_ACTIVATION_ABSENT",
        "executor_activation_ready": EXECUTOR_ACTIVATION_READY,
        "real_private_plans_read": 0,
        "credential_files_read": 0,
        "network_accessed": False,
        "listeners_started": 0,
        "processes_started": 0,
        "services_started": 0,
        "faults_injected": 0,
        "spend_usd_cents": 0,
        "execution_authorized": False,
        "production_admissible": False,
    }


if __name__ == "__main__":
    print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
