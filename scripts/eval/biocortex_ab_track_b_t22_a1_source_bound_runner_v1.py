"""Source-bound global scheduler for the T22-A1 three-domain run.

The core compiles all three exact workload plans, dispatches the only allowed
23-command inter-domain schedule, replays every receipt chain, requires cleanup
on success and on abort, and hands a closed transcript to an injected evidence
finalizer. The live local-process backend is present; authenticated live lanes
and activation remain disabled until the final audit.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

ROOT = Path(__file__).resolve().parents[2]
PLAN_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_workload_plan_v1.py"
EXECUTOR_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_domain_executor_core_v1.py"
TRANSCRIPT_DOMAIN = b"agent-bridge/biocortex/track-b/t22-a1/source-bound-runner-transcript/v1\0"
DOMAIN_IDS = ("domain-1", "domain-2", "domain-3")
RUNNER_ACTIVATION_READY = False


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
    return load_module("t22a1_plan_for_source_bound_runner", PLAN_SOURCE)


def load_executor_module():
    return load_module("t22a1_executor_for_source_bound_runner", EXECUTOR_SOURCE)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: object) -> str:
    return hashlib.sha256(TRANSCRIPT_DOMAIN + canonical(value)).hexdigest()


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


def global_schedule(fault_target_domain_id: str) -> list[tuple[str, str]]:
    require(fault_target_domain_id in {"domain-2", "domain-3"}, "E_RUNNER_FAULT_TARGET")
    survivor = "domain-3" if fault_target_domain_id == "domain-2" else "domain-2"
    schedule: list[tuple[str, str]] = []
    for command in ("PREFLIGHT", "START_OWNED_CLUSTER_MEMBERS", "QUERY_CLUSTER_STATE"):
        schedule.extend((domain_id, command) for domain_id in DOMAIN_IDS)
    schedule.extend([
        ("domain-1", "EXECUTE_AUTHORIZE_CONSUME"),
        ("domain-1", "CREATE_PREFAULT_TRANSIT_SIGNATURE"),
        (fault_target_domain_id, "STOP_OWNED_SERVICE_SET"),
        ("domain-1", "VERIFY_SURVIVING_QUORUM_AND_STATE"),
        (survivor, "VERIFY_SURVIVING_QUORUM_AND_STATE"),
        ("domain-1", "VERIFY_POSTFAULT_TRANSIT_SIGNATURE"),
        (fault_target_domain_id, "RESTART_OWNED_SERVICE_SET"),
        (fault_target_domain_id, "VERIFY_TARGET_REJOIN"),
    ])
    schedule.extend((domain_id, "CLEANUP_OWNED_PROCESSES") for domain_id in DOMAIN_IDS)
    schedule.extend((domain_id, "TERMINAL_STATUS") for domain_id in DOMAIN_IDS)
    require(len(schedule) == 23 and len(set(schedule)) == 23, "E_RUNNER_SCHEDULE_INTERNAL")
    return schedule


class DomainLane(Protocol):
    domain_id: str
    synthetic_only: bool

    def dispatch(self, command: str, now: datetime) -> dict: ...
    def abort_cleanup(self) -> dict: ...


def validate_admission(execution: dict, admission: dict) -> None:
    require(
        admission.get("status") == "AUTHORIZED_T22_A1_EXACT_OWNER_SIGNED_NONPRODUCTION_EXECUTION_ADMISSION"
        and admission.get("run_id") == execution.get("run_id")
        and admission.get("source_commit") == execution.get("source_commit")
        and admission.get("execution_contract_sha256") == execution.get("content_sha256")
        and is_sha256(admission.get("content_sha256")),
        "E_RUNNER_ADMISSION",
    )


def validate_readiness_packets(execution: dict, endpoint_manifest: dict, packets: list[dict]) -> None:
    require(isinstance(packets, list) and [row.get("domain_id") for row in packets] == list(DOMAIN_IDS), "E_RUNNER_READINESS_SET")
    require(len({row.get("content_sha256") for row in packets}) == 3, "E_RUNNER_READINESS_DUPLICATE")
    for packet in packets:
        require(
            packet.get("run_id") == execution.get("run_id")
            and packet.get("source_commit") == execution.get("source_commit")
            and packet.get("bindings", {}).get("execution_contract_sha256") in {None, execution.get("content_sha256")}
            and packet.get("bindings", {}).get("private_endpoint_manifest_content_sha256") == endpoint_manifest.get("content_sha256")
            and is_sha256(packet.get("content_sha256")),
            "E_RUNNER_READINESS_BINDING",
        )


def validate_finalization(value: object) -> dict:
    required = {
        "evidence_manifest_content_sha256", "terminal_evidence_content_sha256",
        "all_owned_processes_cleaned", "all_owned_ports_released",
        "secret_value_scan_passed",
    }
    require(isinstance(value, dict) and set(value) == required, "E_RUNNER_FINALIZATION_SHAPE")
    assert isinstance(value, dict)
    require(
        is_sha256(value["evidence_manifest_content_sha256"])
        and is_sha256(value["terminal_evidence_content_sha256"]),
        "E_RUNNER_FINALIZATION_DIGEST",
    )
    require(
        value["all_owned_processes_cleaned"] is True
        and value["all_owned_ports_released"] is True
        and value["secret_value_scan_passed"] is True,
        "E_RUNNER_FINALIZATION_CLEANUP",
    )
    return value


def _failure_result(execution: dict, admission: dict, code: str, cleanup: list[dict]) -> dict:
    cleaned = bool(cleanup) and all(
        row == {"all_owned_processes_cleaned": True, "all_owned_ports_released": True}
        for row in cleanup
    )
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.source_bound_runner_result.v1",
        "status": "FAIL_T22_A1_DISTRIBUTED_RUN", "failure_code": code,
        "run_id": execution.get("run_id"), "source_commit": execution.get("source_commit"),
        "execution_contract_sha256": execution.get("content_sha256"),
        "execution_admission_receipt_sha256": admission.get("content_sha256"),
        "evidence_manifest_content_sha256": None,
        "terminal_evidence_content_sha256": None,
        "all_owned_processes_cleaned": cleaned,
        "all_owned_ports_released": cleaned,
        "secret_value_scan_passed": False,
        "automatic_retry_allowed": False, "production_admissible": False,
    }


def run_source_bound(
    execution: dict,
    admission: dict,
    endpoint_manifest: dict,
    readiness_packets: list[dict],
    lane_factory: Callable[[dict, dict], DomainLane],
    evidence_finalizer: Callable[[dict, dict, list[dict], dict[str, list[dict]], list[dict]], dict],
    clock: Callable[[], datetime],
    synthetic_only: bool,
) -> dict:
    """Run the exact global schedule; the caller owns durable evidence I/O."""
    lanes: dict[str, DomainLane] = {}
    try:
        require(isinstance(execution, dict) and is_sha256(execution.get("content_sha256")), "E_RUNNER_EXECUTION")
        validate_admission(execution, admission)
        require(endpoint_manifest.get("run_id") == execution["run_id"] and endpoint_manifest.get("source_commit") == execution["source_commit"], "E_RUNNER_ENDPOINT")
        require(endpoint_manifest.get("content_sha256") == execution.get("private_runtime", {}).get("private_endpoint_manifest_content_sha256"), "E_RUNNER_ENDPOINT")
        validate_readiness_packets(execution, endpoint_manifest, readiness_packets)
        require(synthetic_only or RUNNER_ACTIVATION_READY, "E_RUNNER_ACTIVATION_NOT_READY")
        plan_module = load_plan_module()
        executor_module = load_executor_module()
        plans = [plan_module.build_plan(execution, endpoint_manifest, packet) for packet in readiness_packets]
        require([plan.get("domain_id") for plan in plans] == list(DOMAIN_IDS), "E_RUNNER_PLAN_SET")
        for plan, packet in zip(plans, readiness_packets, strict=True):
            lane = lane_factory(plan, packet)
            require(lane.domain_id == plan["domain_id"] and lane.synthetic_only is synthetic_only, "E_RUNNER_LANE_BINDING")
            lanes[plan["domain_id"]] = lane
        fault_target = execution.get("fault", {}).get("target_domain_id")
        schedule = global_schedule(fault_target)
        expires = parse_time(execution.get("expires_at"), "E_RUNNER_EXPIRY")
        receipt_chains = {domain_id: [] for domain_id in DOMAIN_IDS}
        transcript: list[dict] = []
        previous_time: datetime | None = None
        for sequence, (domain_id, command) in enumerate(schedule):
            now = clock()
            require(now.tzinfo is not None and now.utcoffset().total_seconds() == 0, "E_RUNNER_TIMEZONE")
            require((previous_time is None or previous_time <= now) and now < expires, "E_RUNNER_TIME_WINDOW")
            previous_time = now
            receipt = lanes[domain_id].dispatch(command, now)
            require(
                isinstance(receipt, dict) and receipt.get("domain_id") == domain_id
                and receipt.get("command") == command and is_sha256(receipt.get("content_sha256")),
                "E_RUNNER_RECEIPT_BINDING",
            )
            receipt_chains[domain_id].append(receipt)
            row = {
                "sequence": sequence, "domain_id": domain_id, "command": command,
                "command_receipt_sha256": receipt["content_sha256"],
            }
            row["transcript_sha256"] = digest(row)
            transcript.append(row)
        for plan in plans:
            summary = executor_module.validate_receipt_chain(receipt_chains[plan["domain_id"]], plan)
            require(summary.get("state") == "TERMINAL_SUCCEEDED" and summary.get("synthetic_backend") is synthetic_only, "E_RUNNER_RECEIPT_CHAIN")
        finalization = validate_finalization(evidence_finalizer(
            execution, admission, plans, receipt_chains, transcript,
        ))
        return {
            "schema": "agent_bridge.biocortex.track_b.t22_a1.source_bound_runner_result.v1",
            "status": "PASS_T22_A1_TERMINAL_EVIDENCE_READY", "failure_code": None,
            "run_id": execution["run_id"], "source_commit": execution["source_commit"],
            "execution_contract_sha256": execution["content_sha256"],
            "execution_admission_receipt_sha256": admission["content_sha256"],
            **finalization,
            "automatic_retry_allowed": False, "production_admissible": False,
        }
    except Exception as error:
        cleanup: list[dict] = []
        for domain_id in reversed(DOMAIN_IDS):
            if domain_id in lanes:
                try:
                    cleanup.append(lanes[domain_id].abort_cleanup())
                except Exception:
                    cleanup.append({"all_owned_processes_cleaned": False, "all_owned_ports_released": False})
        code = str(error) if isinstance(error, RuntimeError) and str(error).startswith("E_") else "E_RUNNER_LOCAL_FAILURE"
        return _failure_result(execution, admission, code, cleanup)


def status() -> dict:
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a1.source_bound_runner_status.v0",
        "status": "OFFLINE_SOURCE_BOUND_GLOBAL_SCHEDULER_AND_LOCAL_BACKEND_READY_LIVE_LANES_ACTIVATION_CLOSED",
        "runner_activation_ready": RUNNER_ACTIVATION_READY,
        "global_command_count": 23, "automatic_retry_allowed": False,
        "real_private_inputs_read": 0, "network_accessed": False,
        "listeners_started": 0, "processes_started": 0, "faults_injected": 0,
        "execution_authorized": False, "production_admissible": False,
    }


if __name__ == "__main__":
    print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
