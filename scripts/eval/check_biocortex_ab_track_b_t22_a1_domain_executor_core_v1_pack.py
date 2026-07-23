"""Synthetic lifecycle KAT for the T22-A1 fixed-command executor core."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_executor_core_v1.py"
spec = importlib.util.spec_from_file_location("t22a1domainexecutor", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
plan_module = module.load_plan_module()

SOURCE_COMMIT = "a" * 40
RUN_ID = "t22-a1-20260722T220000.000000z-123456789abc"
NOW = datetime(2026, 7, 22, 22, 0, tzinfo=timezone.utc)


def sha(label: str) -> str:
    return hashlib.sha256(f"T22_A1_DOMAIN_EXECUTOR_SYNTHETIC:{label}".encode()).hexdigest()


ENDPOINT = {
    "source_commit": SOURCE_COMMIT,
    "run_id": RUN_ID,
    "content_sha256": sha("endpoint"),
    "domains": [
        {
            "domain_id": f"domain-{number}", "overlay_ip": f"100.64.50.{number}",
            "agent_control_port": 29000, "etcd_client_port": 2379, "etcd_peer_port": 2380,
            "openbao_api_port": 8200, "openbao_cluster_port": 8201,
            "bind_exact_overlay_ip_only": True, "public_listener_allowed": False,
        }
        for number in (1, 2, 3)
    ],
}
EXECUTION = {
    "source_commit": SOURCE_COMMIT, "run_id": RUN_ID, "content_sha256": sha("execution"),
    "private_runtime": {
        "private_endpoint_manifest_content_sha256": ENDPOINT["content_sha256"],
        "runtime_credential_manifest_content_sha256": sha("credentials"),
    },
    "topology": {"domains": [
        {
            "domain_id": f"domain-{number}",
            "role": "COORDINATOR_VOTER" if number == 1 else "PARTICIPANT_VOTER",
            "etcd_member": f"etcd-{number}", "openbao_member": f"bao-{number}",
        }
        for number in (1, 2, 3)
    ]},
    "fault": {"target_domain_id": "domain-3"},
    "authorization": {"maximum_runtime_seconds": 3600, "automatic_retry_allowed": False},
    "budget": {"maximum_spend_usd_cents": 0},
    "expires_at": "2026-07-22T23:00:00Z",
}


def identity(root: Path, name: str) -> dict:
    return {
        "certificate_path": str(root / f"{name}.crt"),
        "private_key_path": str(root / f"{name}.key"),
        "certificate_sha256": sha(f"certificate:{root}:{name}"),
        "spki_sha256": sha(f"spki:{root}:{name}"),
        "private_key_spki_sha256": sha(f"spki:{root}:{name}"),
        "private_key_file_mode": "0600",
        "certificate_private_key_match_verified": True,
    }


def readiness(number: int) -> dict:
    domain_id = f"domain-{number}"
    root = Path(f"/private/t22-a1/{RUN_ID}/{domain_id}")
    credentials = root / "credentials"
    endpoint = ENDPOINT["domains"][number - 1]
    coordinator = None if number != 1 else {
        "client_identity": identity(credentials, "coordinator"),
        "runtime_public_key_path": str(credentials / "coordinator-runtime.pub"),
        "runtime_private_key_path": str(credentials / "coordinator-runtime"),
    }
    coordinator_identity = identity(credentials, "coordinator")
    coordinator_trust = {
        "certificate_path": coordinator_identity["certificate_path"],
        "certificate_sha256": coordinator_identity["certificate_sha256"],
        "spki_sha256": coordinator_identity["spki_sha256"],
        "runtime_public_key_path": str(credentials / "coordinator-runtime.pub"),
        "runtime_public_key_sha256": sha("coordinator-runtime"),
    }
    return {
        "source_commit": SOURCE_COMMIT, "run_id": RUN_ID, "domain_id": domain_id,
        "content_sha256": sha(f"readiness:{number}"),
        "bindings": {
            "private_endpoint_manifest_content_sha256": ENDPOINT["content_sha256"],
            "runtime_credential_manifest_content_sha256": EXECUTION["private_runtime"]["runtime_credential_manifest_content_sha256"],
        },
        "endpoint_binding": {key: endpoint[key] for key in (
            "overlay_ip", "agent_control_port", "etcd_client_port", "etcd_peer_port",
            "openbao_api_port", "openbao_cluster_port",
        )},
        "toolchain": {"executables": [
            {"name": name, "path": f"/private/tools/{domain_id}/{name}", "sha256": sha(f"tool:{number}:{name}")}
            for name in plan_module.TOOL_NAMES
        ]},
        "local_paths": {
            "domain_private_root": str(root), "etcd_data_dir": str(root / "etcd"),
            "openbao_data_dir": str(root / "openbao"), "owned_logs_dir": str(root / "logs"),
            "domain_evidence_dir": str(root / "evidence"),
            "execution_reservation_dir": str(root / "execution-reservations"),
        },
        "credential_placement": {
            "mode": "OWNER_MEDIATED_OUT_OF_BAND_EXACT_HASH_PLACEMENT",
            "all_paths_local_to_attested_host": True,
            "ca_certificate_path": str(credentials / "ca.crt"),
            "ca_certificate_sha256": sha(f"ca:{number}"),
            "domain_identity": identity(credentials, "domain"),
            "domain_operator_public_key_path": str(credentials / "domain-operator.pub"),
            "domain_operator_private_key_path": str(credentials / "domain-operator"),
            "coordinator_trust_material": coordinator_trust,
            "coordinator_material": coordinator,
        },
    }


READINESS = [readiness(number) for number in (1, 2, 3)]
PLANS = [plan_module.build_plan(EXECUTION, ENDPOINT, packet) for packet in READINESS]


def effects(command: str) -> dict:
    value = {
        "network_accessed": command not in {"PREFLIGHT", "STOP_OWNED_SERVICE_SET"},
        "listeners_started": 0, "listeners_stopped": 0,
        "service_processes_started": 0, "service_processes_stopped": 0,
        "faults_injected": 0, "spend_usd_cents": 0,
    }
    if command == "START_OWNED_CLUSTER_MEMBERS":
        value.update(listeners_started=4, service_processes_started=2)
    elif command == "STOP_OWNED_SERVICE_SET":
        value.update(service_processes_stopped=2, faults_injected=1)
    elif command == "RESTART_OWNED_SERVICE_SET":
        value.update(service_processes_started=2)
    elif command == "CLEANUP_OWNED_PROCESSES":
        value.update(listeners_stopped=4, service_processes_stopped=2)
    return value


class SyntheticBackend:
    synthetic_only = True

    def __init__(self, domain_id: str, overrides: dict[str, object] | None = None):
        self.domain_id = domain_id
        self.overrides = overrides or {}
        self.prefault_challenge = sha("transit-challenge")
        self.prefault_signature = sha("transit-signature")

    def result(self, command: str, observation: dict) -> dict:
        value = {"observation": observation, "effects": effects(command)}
        override = self.overrides.get(command)
        if callable(override):
            override(value)
        return value

    def preflight(self, plan: dict) -> dict:
        return self.result("PREFLIGHT", {
            "tool_hash_set_verified": True, "credential_hash_and_key_match_verified": True,
            "owned_paths_private_and_empty": True, "exact_ports_available": True,
            "ambient_credentials_absent": True, "preflight_receipt_sha256": sha(f"preflight:{self.domain_id}"),
        })

    def start_owned_cluster_members(self, plan: dict) -> dict:
        leader = self.domain_id == "domain-1"
        return self.result("START_OWNED_CLUSTER_MEMBERS", {
            "etcd_process_started": True, "openbao_process_started": True,
            "owned_process_set_sha256": sha(f"process-set:{self.domain_id}:start"),
            "process_receipt_sha256": sha(f"process-receipt:{self.domain_id}:start"),
            "openbao_bootstrap_role": "LEADER_INITIALIZE_AND_HOLD_MEMORY_ONLY" if leader else "FOLLOWER_RETRY_JOIN_AND_UNSEAL",
            "secret_frame_action": "PRODUCED_MEMORY_ONLY" if leader else "CONSUMED_MEMORY_ONLY",
            "secret_frame_sha256": sha("unseal-frame"), "secret_frame_persisted": False,
        })

    def query_cluster_state(self, plan: dict) -> dict:
        return self.result("QUERY_CLUSTER_STATE", {
            "etcd_member_count": 3, "etcd_voter_count": 3,
            "openbao_member_count": 3, "openbao_voter_count": 3,
            "local_etcd_healthy": True, "local_openbao_unsealed": True,
            "cluster_observation_sha256": sha(f"cluster:{self.domain_id}"),
        })

    def execute_authorize_consume(self, plan: dict) -> dict:
        return self.result("EXECUTE_AUTHORIZE_CONSUME", {
            "linearizable_authorize_consume_observed": True, "replay_consume_rejected": True,
            "authorized_value_sha256": plan["workload"]["authorized_unclaimed_value_sha256"],
            "consumed_value_sha256": plan["workload"]["consumed_value_sha256"],
            "consume_revision_sha256": sha("consume-revision"),
            "replay_revision_sha256": sha("replay-revision"),
        })

    def create_prefault_transit_signature(self, plan: dict) -> dict:
        return self.result("CREATE_PREFAULT_TRANSIT_SIGNATURE", {
            "prefault_transit_signature_created": True,
            "transit_challenge_sha256": self.prefault_challenge,
            "transit_signature_sha256": self.prefault_signature,
            "consumed_state_sha256": plan["workload"]["consumed_value_sha256"],
        })

    def stop_owned_service_set(self, plan: dict) -> dict:
        return self.result("STOP_OWNED_SERVICE_SET", {
            "target_domain_id": plan["role"]["fault_target_domain_id"],
            "etcd_process_stopped": True, "openbao_process_stopped": True,
            "stopped_owned_process_set_sha256": sha(f"stopped:{self.domain_id}"),
        })

    def verify_surviving_quorum_and_state(self, plan: dict) -> dict:
        return self.result("VERIFY_SURVIVING_QUORUM_AND_STATE", {
            "surviving_two_domain_etcd_quorum_observed": True,
            "surviving_two_domain_openbao_available": True,
            "prefault_state_match_verified": True,
            "survivor_observation_sha256": sha(f"survivor:{self.domain_id}"),
        })

    def verify_postfault_transit_signature(self, plan: dict) -> dict:
        return self.result("VERIFY_POSTFAULT_TRANSIT_SIGNATURE", {
            "postfault_transit_signature_verified": True,
            "transit_challenge_sha256": self.prefault_challenge,
            "transit_signature_sha256": self.prefault_signature,
        })

    def restart_owned_service_set(self, plan: dict) -> dict:
        return self.result("RESTART_OWNED_SERVICE_SET", {
            "target_domain_id": plan["role"]["fault_target_domain_id"],
            "etcd_process_restarted": True, "openbao_process_restarted": True,
            "restarted_owned_process_set_sha256": sha(f"restarted:{self.domain_id}"),
            "secret_frame_action": "CONSUMED_MEMORY_ONLY", "secret_frame_sha256": sha("unseal-frame"),
            "secret_frame_persisted": False,
        })

    def verify_target_rejoin(self, plan: dict) -> dict:
        return self.result("VERIFY_TARGET_REJOIN", {
            "target_domain_id": plan["role"]["fault_target_domain_id"],
            "target_etcd_rejoined": True, "target_openbao_rejoined": True,
            "etcd_voter_count": 3, "openbao_voter_count": 3,
            "rejoin_observation_sha256": sha(f"rejoin:{self.domain_id}"),
        })

    def cleanup_owned_processes(self, plan: dict) -> dict:
        return self.result("CLEANUP_OWNED_PROCESSES", {
            "all_owned_processes_stopped": True, "all_owned_ports_released": True,
            "owned_process_log_set_sha256": sha(f"logs:{self.domain_id}"),
            "owned_process_log_count": 4, "cleanup_receipt_sha256": sha(f"cleanup:{self.domain_id}"),
            "secret_value_scan_passed": True, "exact_secret_match_count": 0,
        })

    def terminal_status(self, plan: dict, previous_receipt_sha256: str) -> dict:
        return self.result("TERMINAL_STATUS", {
            "lifecycle_succeeded": True,
            "command_receipt_count": len(plan["command_policy"]["allowed_commands"]),
            "domain_evidence_head_sha256": previous_receipt_sha256,
        })


SEQUENCES = {
    "domain-1": [
        "PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE",
        "EXECUTE_AUTHORIZE_CONSUME", "CREATE_PREFAULT_TRANSIT_SIGNATURE",
        "VERIFY_SURVIVING_QUORUM_AND_STATE", "VERIFY_POSTFAULT_TRANSIT_SIGNATURE",
        "CLEANUP_OWNED_PROCESSES", "TERMINAL_STATUS",
    ],
    "domain-2": [
        "PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE",
        "VERIFY_SURVIVING_QUORUM_AND_STATE", "CLEANUP_OWNED_PROCESSES", "TERMINAL_STATUS",
    ],
    "domain-3": [
        "PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE",
        "STOP_OWNED_SERVICE_SET", "RESTART_OWNED_SERVICE_SET", "VERIFY_TARGET_REJOIN",
        "CLEANUP_OWNED_PROCESSES", "TERMINAL_STATUS",
    ],
}

executors: list[module.FixedCommandExecutor] = []
receipt_count = 0
for number, plan in enumerate(PLANS, 1):
    executor = module.FixedCommandExecutor(plan, EXECUTION, ENDPOINT, READINESS[number - 1], SyntheticBackend(plan["domain_id"]))
    for offset, command in enumerate(SEQUENCES[plan["domain_id"]]):
        receipt = executor.execute(command, NOW + timedelta(seconds=offset))
        unsigned = dict(receipt)
        claimed = unsigned.pop("content_sha256")
        assert claimed == module.receipt_digest(unsigned)
        assert receipt["synthetic_backend"] is True
        assert receipt["arbitrary_command_or_shell_used"] is False
        assert receipt["automatic_retry_allowed"] is False
        assert receipt["production_admissible"] is False
        receipt_count += 1
    assert executor.state == "TERMINAL_SUCCEEDED"
    assert executor.receipts[-1]["previous_receipt_sha256"] == executor.receipts[-2]["content_sha256"]
    chain = module.validate_receipt_chain(executor.receipts, plan)
    assert chain["state"] == "TERMINAL_SUCCEEDED"
    assert chain["receipt_count"] == len(SEQUENCES[plan["domain_id"]])
    assert chain["synthetic_backend"] is True
    executors.append(executor)


def expect_failure(action, expected: str) -> None:  # noqa: ANN001
    try:
        action()
    except module.SafeFailure as error:
        assert str(error) == expected, (str(error), expected)
        return
    raise AssertionError(f"unsafe executor path admitted: {expected}")


class RealBackend(SyntheticBackend):
    synthetic_only = False


expect_failure(
    lambda: module.FixedCommandExecutor(PLANS[0], EXECUTION, ENDPOINT, READINESS[0], RealBackend("domain-1")),
    "E_DOMAIN_EXECUTOR_ACTIVATION_NOT_READY",
)

mutated_plan = copy.deepcopy(PLANS[0])
mutated_plan["command_policy"]["arbitrary_command_or_shell_allowed"] = True
mutated_plan.pop("content_sha256")
mutated_plan["content_sha256"] = plan_module.digest(mutated_plan)
expect_failure(
    lambda: module.FixedCommandExecutor(mutated_plan, EXECUTION, ENDPOINT, READINESS[0], SyntheticBackend("domain-1")),
    "E_WORKLOAD_PLAN_EXACT_RECONSTRUCTION",
)

domain_two_executor = module.FixedCommandExecutor(PLANS[1], EXECUTION, ENDPOINT, READINESS[1], SyntheticBackend("domain-2"))
expect_failure(lambda: domain_two_executor.execute("STOP_OWNED_SERVICE_SET", NOW), "E_DOMAIN_EXECUTOR_COMMAND_NOT_ALLOWED")
expect_failure(lambda: domain_two_executor.execute("QUERY_CLUSTER_STATE", NOW), "E_AGENT_SESSION_TRANSITION")

expired_executor = module.FixedCommandExecutor(PLANS[0], EXECUTION, ENDPOINT, READINESS[0], SyntheticBackend("domain-1"))
expect_failure(lambda: expired_executor.execute("PREFLIGHT", NOW + timedelta(hours=2)), "E_DOMAIN_EXECUTOR_EXPIRED")

runtime_execution = copy.deepcopy(EXECUTION)
runtime_execution["authorization"]["maximum_runtime_seconds"] = 10
runtime_plan = plan_module.build_plan(runtime_execution, ENDPOINT, READINESS[0])
runtime_executor = module.FixedCommandExecutor(runtime_plan, runtime_execution, ENDPOINT, READINESS[0], SyntheticBackend("domain-1"))
runtime_executor.execute("PREFLIGHT", NOW)
expect_failure(lambda: runtime_executor.execute("START_OWNED_CLUSTER_MEMBERS", NOW + timedelta(seconds=11)), "E_DOMAIN_EXECUTOR_RUNTIME_LIMIT")

bad_result_executor = module.FixedCommandExecutor(
    PLANS[0], EXECUTION, ENDPOINT, READINESS[0],
    SyntheticBackend("domain-1", {"PREFLIGHT": lambda value: value.pop("effects")}),
)
expect_failure(lambda: bad_result_executor.execute("PREFLIGHT", NOW), "E_DOMAIN_EXECUTOR_BACKEND_RESULT")
assert bad_result_executor.state == "TERMINAL_FAILED"
expect_failure(lambda: bad_result_executor.execute("PREFLIGHT", NOW), "E_DOMAIN_EXECUTOR_TERMINAL")

backend_exception_executor = module.FixedCommandExecutor(
    PLANS[0], EXECUTION, ENDPOINT, READINESS[0],
    SyntheticBackend("domain-1", {"PREFLIGHT": lambda value: (_ for _ in ()).throw(ValueError("sensitive-local-text"))}),
)
expect_failure(lambda: backend_exception_executor.execute("PREFLIGHT", NOW), "E_DOMAIN_EXECUTOR_BACKEND_FAILURE")
assert backend_exception_executor.state == "TERMINAL_FAILED"

bad_preflight_executor = module.FixedCommandExecutor(
    PLANS[0], EXECUTION, ENDPOINT, READINESS[0],
    SyntheticBackend("domain-1", {"PREFLIGHT": lambda value: value["observation"].update(tool_hash_set_verified=False)}),
)
expect_failure(lambda: bad_preflight_executor.execute("PREFLIGHT", NOW), "E_DOMAIN_EXECUTOR_PREFLIGHT")
assert bad_preflight_executor.state == "TERMINAL_FAILED"

bad_effect_executor = module.FixedCommandExecutor(
    PLANS[0], EXECUTION, ENDPOINT, READINESS[0],
    SyntheticBackend("domain-1", {"PREFLIGHT": lambda value: value["effects"].update(network_accessed=True)}),
)
expect_failure(lambda: bad_effect_executor.execute("PREFLIGHT", NOW), "E_DOMAIN_EXECUTOR_PREFLIGHT_EFFECT")
assert bad_effect_executor.state == "TERMINAL_FAILED"

bad_spend_execution = copy.deepcopy(EXECUTION)
bad_spend_execution["budget"]["maximum_spend_usd_cents"] = 1
bad_spend_plan = plan_module.build_plan(bad_spend_execution, ENDPOINT, READINESS[0])
bad_spend_executor = module.FixedCommandExecutor(
    bad_spend_plan, bad_spend_execution, ENDPOINT, READINESS[0],
    SyntheticBackend("domain-1", {"QUERY_CLUSTER_STATE": lambda value: value["effects"].update(spend_usd_cents=2)}),
)
bad_spend_executor.execute("PREFLIGHT", NOW)
bad_spend_executor.execute("START_OWNED_CLUSTER_MEMBERS", NOW + timedelta(seconds=1))
expect_failure(lambda: bad_spend_executor.execute("QUERY_CLUSTER_STATE", NOW + timedelta(seconds=2)), "E_DOMAIN_EXECUTOR_SPEND_LIMIT")
assert bad_spend_executor.state == "TERMINAL_FAILED"

post_backend = SyntheticBackend(
    "domain-1", {"VERIFY_POSTFAULT_TRANSIT_SIGNATURE": lambda value: value["observation"].update(transit_signature_sha256=sha("wrong-signature"))},
)
post_executor = module.FixedCommandExecutor(PLANS[0], EXECUTION, ENDPOINT, READINESS[0], post_backend)
for offset, command in enumerate(SEQUENCES["domain-1"][:6]):
    post_executor.execute(command, NOW + timedelta(seconds=offset))
expect_failure(
    lambda: post_executor.execute("VERIFY_POSTFAULT_TRANSIT_SIGNATURE", NOW + timedelta(seconds=6)),
    "E_DOMAIN_EXECUTOR_TRANSIT_SIGNATURE",
)
assert post_executor.state == "TERMINAL_FAILED"

expect_failure(
    lambda: executors[0].execute("TERMINAL_STATUS", NOW + timedelta(seconds=20)),
    "E_DOMAIN_EXECUTOR_TERMINAL",
)

expect_failure(
    lambda: module.validate_receipt_chain(executors[0].receipts[:-1], PLANS[0]),
    "E_DOMAIN_EXECUTOR_RECEIPT_CHAIN_INCOMPLETE",
)
broken_chain = copy.deepcopy(executors[0].receipts)
broken_chain[1]["previous_receipt_sha256"] = sha("wrong-previous")
broken_chain[1].pop("content_sha256")
broken_chain[1]["content_sha256"] = module.receipt_digest(broken_chain[1])
expect_failure(lambda: module.validate_receipt_chain(broken_chain, PLANS[0]), "E_DOMAIN_EXECUTOR_RECEIPT_CHAIN")

forged_receipt = copy.deepcopy(executors[0].receipts)
forged_receipt[0]["content_sha256"] = sha("forged-receipt")
expect_failure(lambda: module.validate_receipt_chain(forged_receipt, PLANS[0]), "E_DOMAIN_EXECUTOR_RECEIPT_DIGEST")

wrong_observation = copy.deepcopy(executors[0].receipts)
wrong_observation[3]["observation"]["replay_consume_rejected"] = False
wrong_observation[3].pop("content_sha256")
wrong_observation[3]["content_sha256"] = module.receipt_digest(wrong_observation[3])
expect_failure(lambda: module.validate_receipt_chain(wrong_observation, PLANS[0]), "E_DOMAIN_EXECUTOR_CONSUME")

wrong_time = copy.deepcopy(executors[0].receipts)
wrong_time[2]["observed_at"] = module.utc_text(NOW - timedelta(seconds=1))
wrong_time[2].pop("content_sha256")
wrong_time[2]["content_sha256"] = module.receipt_digest(wrong_time[2])
expect_failure(lambda: module.validate_receipt_chain(wrong_time, PLANS[0]), "E_DOMAIN_EXECUTOR_RECEIPT_TIME_ORDER")

wrong_terminal_head = copy.deepcopy(executors[0].receipts)
wrong_terminal_head[-1]["observation"]["domain_evidence_head_sha256"] = sha("wrong-terminal-head")
wrong_terminal_head[-1].pop("content_sha256")
wrong_terminal_head[-1]["content_sha256"] = module.receipt_digest(wrong_terminal_head[-1])
expect_failure(
    lambda: module.validate_receipt_chain(wrong_terminal_head, PLANS[0]),
    "E_DOMAIN_EXECUTOR_TERMINAL_CHAIN_HEAD",
)

status = module.status()
assert status["status"] == "OFFLINE_FIXED_COMMAND_EXECUTOR_CORE_AND_LIVE_BACKEND_PRESENT_ACTIVATION_CLOSED"
assert status["executor_activation_ready"] is False
assert status["real_private_plans_read"] == status["credential_files_read"] == 0
assert status["network_accessed"] is False
assert status["listeners_started"] == status["processes_started"] == status["services_started"] == 0
assert status["faults_injected"] == status["spend_usd_cents"] == 0
assert status["execution_authorized"] is False and status["production_admissible"] is False

negative_count = 20
print("t22_a1_domain_executor_core_check\tpass")
print("synthetic_valid_domain_lifecycle_count\t3")
print(f"synthetic_valid_command_receipt_count\t{receipt_count}")
print(f"directed_negative_test_count\t{negative_count}")
print("real_private_plans_read\t0")
print("credential_files_read\t0")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("processes_started\t0")
print("services_started\t0")
print("faults_injected\t0")
print("production_admissible\tfalse")
