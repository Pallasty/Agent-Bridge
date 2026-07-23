"""Synthetic KAT for the T22-A1 source-bound global scheduler."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a1_source_bound_runner_v1.py"
spec = importlib.util.spec_from_file_location("t22a1sourceboundrunner", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

NOW = datetime.now(timezone.utc).replace(microsecond=0)
SOURCE_COMMIT = "a" * 40
RUN_ID = "t22-a1-20260722T220000.000000z-123456789abc"


def sha(label: str) -> str:
    return hashlib.sha256(f"T22_A1_SOURCE_RUNNER_SYNTHETIC:{label}".encode()).hexdigest()


EXECUTION = {
    "run_id": RUN_ID, "source_commit": SOURCE_COMMIT, "content_sha256": sha("execution"),
    "expires_at": (NOW + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
    "private_runtime": {"private_endpoint_manifest_content_sha256": sha("endpoint")},
    "fault": {"target_domain_id": "domain-2"},
}
ADMISSION = {
    "status": "AUTHORIZED_T22_A1_EXACT_OWNER_SIGNED_NONPRODUCTION_EXECUTION_ADMISSION",
    "run_id": RUN_ID, "source_commit": SOURCE_COMMIT,
    "execution_contract_sha256": EXECUTION["content_sha256"], "content_sha256": sha("admission"),
}
ENDPOINT = {"run_id": RUN_ID, "source_commit": SOURCE_COMMIT, "content_sha256": sha("endpoint")}
READINESS = [{
    "domain_id": f"domain-{number}", "run_id": RUN_ID, "source_commit": SOURCE_COMMIT,
    "content_sha256": sha(f"readiness:{number}"),
    "bindings": {"private_endpoint_manifest_content_sha256": ENDPOINT["content_sha256"]},
} for number in (1, 2, 3)]


class FakePlanModule:
    @staticmethod
    def build_plan(execution: dict, _endpoint: dict, packet: dict) -> dict:
        domain_id = packet["domain_id"]
        return {
            "domain_id": domain_id, "run_id": execution["run_id"],
            "source_commit": execution["source_commit"],
            "content_sha256": sha(f"plan:{domain_id}"),
        }


class FakeExecutorModule:
    @staticmethod
    def validate_receipt_chain(receipts: list[dict], plan: dict) -> dict:
        expected = [command for domain_id, command in module.global_schedule("domain-2") if domain_id == plan["domain_id"]]
        if [receipt["command"] for receipt in receipts] != expected:
            raise RuntimeError("E_SYNTHETIC_CHAIN")
        return {"state": "TERMINAL_SUCCEEDED", "synthetic_backend": True}


module.load_plan_module = lambda: FakePlanModule
module.load_executor_module = lambda: FakeExecutorModule


class Lane:
    synthetic_only = True

    def __init__(self, plan: dict, _packet: dict) -> None:
        self.domain_id = plan["domain_id"]
        self.commands: list[str] = []
        self.fail_command: str | None = None

    def dispatch(self, command: str, _now: datetime) -> dict:
        if command == self.fail_command:
            raise RuntimeError("E_SYNTHETIC_LANE_FAILURE")
        self.commands.append(command)
        return {"domain_id": self.domain_id, "command": command, "content_sha256": sha(f"{self.domain_id}:{command}")}

    def abort_cleanup(self) -> dict:
        return {"all_owned_processes_cleaned": True, "all_owned_ports_released": True}


clock_offset = 0


def clock() -> datetime:
    global clock_offset
    clock_offset += 1
    return NOW + timedelta(seconds=clock_offset)


def finalizer(_execution: dict, _admission: dict, plans: list[dict], chains: dict[str, list[dict]], transcript: list[dict]) -> dict:
    assert len(plans) == 3 and sum(map(len, chains.values())) == len(transcript) == 23
    assert [row["sequence"] for row in transcript] == list(range(23))
    return {
        "evidence_manifest_content_sha256": sha("manifest"),
        "terminal_evidence_content_sha256": sha("terminal"),
        "all_owned_processes_cleaned": True, "all_owned_ports_released": True,
        "secret_value_scan_passed": True,
    }


result = module.run_source_bound(EXECUTION, ADMISSION, ENDPOINT, READINESS, Lane, finalizer, clock, True)
assert result["status"] == "PASS_T22_A1_TERMINAL_EVIDENCE_READY"
assert result["evidence_manifest_content_sha256"] == sha("manifest")

negative_count = 0


def expect_failure(
    execution: dict = EXECUTION,
    admission: dict = ADMISSION,
    endpoint: dict = ENDPOINT,
    readiness: list[dict] = READINESS,
    lane_factory=Lane,
    evidence_finalizer=finalizer,
    synthetic_only: bool = True,
) -> dict:  # noqa: ANN001
    global clock_offset
    clock_offset = 0
    value = module.run_source_bound(
        execution, admission, endpoint, readiness, lane_factory,
        evidence_finalizer, clock, synthetic_only,
    )
    assert value["status"] == "FAIL_T22_A1_DISTRIBUTED_RUN"
    assert value["failure_code"].startswith("E_") and value["automatic_retry_allowed"] is False
    return value


bad_admission = copy.deepcopy(ADMISSION)
bad_admission["execution_contract_sha256"] = sha("other-execution")
assert expect_failure(admission=bad_admission)["failure_code"] == "E_RUNNER_ADMISSION"
negative_count += 1

bad_endpoint = copy.deepcopy(ENDPOINT)
bad_endpoint["content_sha256"] = sha("other-endpoint")
assert expect_failure(endpoint=bad_endpoint)["failure_code"] == "E_RUNNER_ENDPOINT"
negative_count += 1

reversed_readiness = list(reversed(copy.deepcopy(READINESS)))
assert expect_failure(readiness=reversed_readiness)["failure_code"] == "E_RUNNER_READINESS_SET"
negative_count += 1

class WrongLane(Lane):
    def __init__(self, plan: dict, packet: dict) -> None:
        super().__init__(plan, packet)
        self.domain_id = "domain-3" if plan["domain_id"] == "domain-1" else plan["domain_id"]


assert expect_failure(lane_factory=WrongLane)["failure_code"] == "E_RUNNER_LANE_BINDING"
negative_count += 1

class FailingLane(Lane):
    def __init__(self, plan: dict, packet: dict) -> None:
        super().__init__(plan, packet)
        if self.domain_id == "domain-2":
            self.fail_command = "STOP_OWNED_SERVICE_SET"


failed_lane = expect_failure(lane_factory=FailingLane)
assert failed_lane["failure_code"] == "E_SYNTHETIC_LANE_FAILURE"
assert failed_lane["all_owned_processes_cleaned"] is True
negative_count += 1

def bad_finalizer(*_arguments) -> dict:  # noqa: ANN002
    value = finalizer(*_arguments)
    value["terminal_evidence_content_sha256"] = "0" * 64
    return value


assert expect_failure(evidence_finalizer=bad_finalizer)["failure_code"] == "E_RUNNER_FINALIZATION_DIGEST"
negative_count += 1

module.RUNNER_ACTIVATION_READY = False
non_synthetic = expect_failure(synthetic_only=False)
assert non_synthetic["failure_code"] == "E_RUNNER_ACTIVATION_NOT_READY"
negative_count += 1

bad_expiry = copy.deepcopy(EXECUTION)
bad_expiry["expires_at"] = NOW.isoformat().replace("+00:00", "Z")
assert expect_failure(execution=bad_expiry)["failure_code"] == "E_RUNNER_TIME_WINDOW"
negative_count += 1

assert len(module.global_schedule("domain-2")) == len(module.global_schedule("domain-3")) == 23
try:
    module.global_schedule("domain-1")
except module.SafeFailure as error:
    assert str(error) == "E_RUNNER_FAULT_TARGET"
else:
    raise AssertionError("coordinator fault target admitted")
negative_count += 1

status = module.status()
assert status["runner_activation_ready"] is False and status["global_command_count"] == 23
assert status["network_accessed"] is False and status["listeners_started"] == status["processes_started"] == 0
assert status["faults_injected"] == 0 and status["production_admissible"] is False

print("t22_a1_source_bound_runner_check\tpass")
print("synthetic_complete_global_schedule_count\t1")
print("synthetic_dispatched_command_count\t23")
print(f"directed_negative_test_count\t{negative_count}")
print("real_private_inputs_read\t0")
print("network_accessed\tfalse")
print("listeners_started\t0")
print("processes_started\t0")
print("faults_injected\t0")
print("production_admissible\tfalse")
