#!/usr/bin/env python3
"""Freeze the D82 owner policy and fail closed on live CPU isolation."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_owner_policy_isolation_d82_contract.json"
RESULT = HERE / "fh_l8_d60_owner_policy_isolation_d82_result.json"
CGROUP_ROOT = Path("/sys/fs/cgroup")


class D82Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D82Error(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_optional(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None


def parse_cpu_list(spec: str | None) -> set[int]:
    if not spec:
        return set()
    cpus: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise D82Error("descending CPU range")
            cpus.update(range(start, end + 1))
        else:
            cpus.add(int(part))
    return cpus


def format_cpu_list(cpus: set[int]) -> str:
    return ",".join(str(cpu) for cpu in sorted(cpus))


def irq_conflict_count(target_cpu: int) -> int:
    conflicts = 0
    for affinity_path in Path("/proc/irq").glob("*/smp_affinity_list"):
        try:
            if target_cpu in parse_cpu_list(affinity_path.read_text(encoding="utf-8").strip()):
                conflicts += 1
        except (FileNotFoundError, PermissionError, ValueError):
            continue
    return conflicts


def command(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def current_base_environment() -> dict[str, str]:
    governors = {
        path.read_text(encoding="utf-8").strip()
        for path in Path("/sys/devices/system/cpu").glob("cpu*/cpufreq/scaling_governor")
    }
    if len(governors) != 1:
        raise D82Error("CPU governors are absent or non-uniform")
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "machine": platform.machine(),
        "cpu_model": command("bash", "-lc", "lscpu | sed -n 's/^Model name:[[:space:]]*//p'"),
        "online_cpu_list": Path("/sys/devices/system/cpu/online")
        .read_text(encoding="utf-8")
        .strip(),
        "scaling_driver": Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver")
        .read_text(encoding="utf-8")
        .strip(),
        "scaling_governor": next(iter(governors)),
        "energy_performance_preference": Path(
            "/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"
        )
        .read_text(encoding="utf-8")
        .strip(),
        "filesystem_type": command("findmnt", "-no", "FSTYPE", "--target", str(ROOT)),
        "cgroup_version": "v2",
    }


def current_isolation_snapshot(requirement: Mapping[str, Any]) -> dict[str, Any]:
    target_cpu = int(requirement["target_cpu"])
    cgroup_line = Path("/proc/self/cgroup").read_text(encoding="utf-8").strip()
    if not cgroup_line.startswith("0::"):
        raise D82Error("unified cgroup v2 identity unavailable")
    cgroup_path = cgroup_line.removeprefix("0::")
    cgroup_dir = CGROUP_ROOT / cgroup_path.lstrip("/")
    root_controllers = set((read_optional(CGROUP_ROOT / "cgroup.controllers") or "").split())
    root_subtree = set((read_optional(CGROUP_ROOT / "cgroup.subtree_control") or "").split())
    online_cpus = parse_cpu_list(read_optional(Path("/sys/devices/system/cpu/online")))
    siblings = read_optional(
        Path(f"/sys/devices/system/cpu/cpu{target_cpu}/topology/thread_siblings_list")
    )
    d81_environment = load(
        HERE / "fh_l8_d60_environment_margin_precommit_d81_contract.json"
    )["environment_precommit"]
    current_environment = current_base_environment()
    return {
        "d81_environment_identity_except_cgroup_path_matches": all(
            d81_environment.get(field) == value for field, value in current_environment.items()
        ),
        "root_cpuset_controller_available": "cpuset" in root_controllers,
        "root_cpuset_subtree_enabled": "cpuset" in root_subtree,
        "current_cgroup_path": cgroup_path,
        "current_partition_state": read_optional(cgroup_dir / "cpuset.cpus.partition"),
        "current_effective_cpus": format_cpu_list(
            parse_cpu_list(read_optional(cgroup_dir / "cpuset.cpus.effective"))
        ),
        "current_exclusive_effective_cpus": format_cpu_list(
            parse_cpu_list(read_optional(cgroup_dir / "cpuset.cpus.exclusive.effective"))
        ),
        "root_isolated_cpus": format_cpu_list(
            parse_cpu_list(read_optional(CGROUP_ROOT / "cpuset.cpus.isolated"))
        ),
        "process_affinity": format_cpu_list(set(os.sched_getaffinity(0))),
        "target_cpu_online": target_cpu in online_cpus,
        "target_cpu_thread_siblings": siblings,
        "irq_affinity_target_conflict_count": irq_conflict_count(target_cpu),
    }


def evaluate_isolation(
    snapshot: Mapping[str, Any], requirement: Mapping[str, Any]
) -> dict[str, Any]:
    target_cpu = int(requirement["target_cpu"])
    target = str(target_cpu)
    failed: list[str] = []

    def require(name: str, condition: bool) -> None:
        if not condition:
            failed.append(name)

    require("root_cpuset_controller_available", snapshot.get("root_cpuset_controller_available") is True)
    require(
        "d81_environment_identity_except_cgroup_path_matches",
        snapshot.get("d81_environment_identity_except_cgroup_path_matches") is True,
    )
    require("root_cpuset_subtree_enabled", snapshot.get("root_cpuset_subtree_enabled") is True)
    require(
        "target_service_cgroup_path",
        snapshot.get("current_cgroup_path") == requirement.get("target_service_cgroup_path"),
    )
    require(
        "partition_state_isolated",
        snapshot.get("current_partition_state") == requirement.get("partition_state_required"),
    )
    require(
        "effective_cpu_set_exact",
        snapshot.get("current_effective_cpus") == requirement.get("effective_cpu_set_required"),
    )
    require(
        "exclusive_effective_cpu_set_exact",
        snapshot.get("current_exclusive_effective_cpus")
        == requirement.get("exclusive_effective_cpu_set_required"),
    )
    require(
        "target_cpu_root_isolated",
        target_cpu in parse_cpu_list(snapshot.get("root_isolated_cpus")),
    )
    require(
        "process_affinity_exact",
        snapshot.get("process_affinity") == requirement.get("process_affinity_required"),
    )
    require("target_cpu_online", snapshot.get("target_cpu_online") is True)
    require("target_cpu_has_no_smt_sibling", snapshot.get("target_cpu_thread_siblings") == target)
    require(
        "irq_affinity_excludes_target",
        snapshot.get("irq_affinity_target_conflict_count")
        == requirement.get("irq_affinity_target_conflict_count_required"),
    )
    return {"admitted": not failed, "failed_predicates": failed}


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-OWNER-POLICY-ISOLATION-D82-V1":
        raise D82Error("contract identity drift")
    baseline = str(contract.get("baseline_commit", ""))
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", baseline, "HEAD"],
        check=False,
        capture_output=True,
    ).returncode != 0:
        raise D82Error("HEAD is not descended from the frozen baseline")
    source_pins = contract.get("source_pins")
    if not isinstance(source_pins, Mapping) or len(source_pins) != 3:
        raise D82Error("source pins missing")
    for name, expected in source_pins.items():
        if digest(HERE / str(name)) != expected:
            raise D82Error(f"source pin drift: {name}")

    owner = contract.get("owner_decision")
    if not isinstance(owner, Mapping):
        raise D82Error("owner decision missing")
    if owner.get("runtime_claim_class") != (
        "EMPIRICAL_ADMISSION_RUNTIME_ENVELOPE_NOT_DETERMINISTIC_WORST_CASE"
    ):
        raise D82Error("runtime claim class drift")
    if owner.get("deterministic_worst_case_runtime_claimed") is not False:
        raise D82Error("deterministic worst-case runtime was claimed")
    if owner.get("numeric_runtime_seconds_proven") is not False:
        raise D82Error("numeric runtime proof was claimed")

    margin = contract.get("measurement_margin")
    if not isinstance(margin, Mapping):
        raise D82Error("measurement margin missing")
    coverage = margin.get("coverage_numerator") / margin.get("coverage_denominator")
    confidence = (
        margin.get("confidence_per_operation_class_numerator")
        / margin.get("confidence_per_operation_class_denominator")
    )
    expected_samples = math.ceil(math.log(1 - confidence) / math.log(coverage))
    if expected_samples != 459 or margin.get("confirmatory_samples_per_operation_class") != 459:
        raise D82Error("confirmatory sample size drift")
    class_count = margin.get("operation_class_count")
    if class_count != 5 or margin.get("total_confirmatory_samples") != 459 * class_count:
        raise D82Error("confirmatory population drift")
    familywise = Fraction(1, 1) - class_count * (
        Fraction(1, 1)
        - Fraction(
            margin.get("confidence_per_operation_class_numerator"),
            margin.get("confidence_per_operation_class_denominator"),
        )
    )
    if familywise != Fraction(
        margin.get("familywise_confidence_lower_bound_numerator"),
        margin.get("familywise_confidence_lower_bound_denominator"),
    ):
        raise D82Error("familywise confidence drift")
    if margin.get("method") != "DISTRIBUTION_FREE_ONE_SIDED_SAMPLE_MAXIMUM_TOLERANCE_LIMIT":
        raise D82Error("margin method drift")
    if margin.get("tolerance_limit_scope") != (
        "BATCH_COST_POPULATION_ONLY_NOT_A_WHOLE_RUN_TAIL_OR_WORST_CASE_PROOF"
    ):
        raise D82Error("tolerance-limit scope drift")
    if margin.get("scalar_margin_multiplier") is not None:
        raise D82Error("scalar margin multiplier forbidden")
    if margin.get("posthoc_sample_exclusion_allowed") is not False:
        raise D82Error("posthoc sample exclusion opened")
    if margin.get("d54r_evidence_disposition") != "PILOT_AND_HOTSPOT_ORDERING_ONLY":
        raise D82Error("D54R evidence promoted")
    if margin.get("confirmatory_sample_timeout_seconds") != 240:
        raise D82Error("confirmatory sample timeout drift")

    timeout = contract.get("timeout_policy")
    if not isinstance(timeout, Mapping):
        raise D82Error("timeout policy missing")
    if timeout.get("full_run_deadline_rule") != (
        "CEILING_OF_SEALED_EMPIRICAL_ADMISSION_RUNTIME_ENVELOPE_SECONDS"
    ):
        raise D82Error("deadline derivation drift")
    if timeout.get("deadline_scalar_multiplier") is not None:
        raise D82Error("deadline scalar multiplier forbidden")
    if timeout.get("timeout_disposition") != "INDETERMINATE_MEASUREMENT_FAILURE":
        raise D82Error("timeout disposition drift")
    if timeout.get("automatic_retry_allowed") is not False:
        raise D82Error("automatic retry opened")
    if timeout.get("deadline_extension_allowed") is not False:
        raise D82Error("deadline extension opened")
    if timeout.get("systemd_service_type") != "exec":
        raise D82Error("systemd service type drift")
    if timeout.get("runtime_timeout_directive") != "RuntimeMaxSec":
        raise D82Error("runtime timeout directive drift")
    if timeout.get("termination_grace_seconds") != 30:
        raise D82Error("termination grace drift")

    requirement = contract.get("load_isolation_requirement")
    if not isinstance(requirement, Mapping):
        raise D82Error("load isolation requirement missing")
    if requirement.get("mechanism") != "CGROUP_V2_CPUSET_ISOLATED_PARTITION":
        raise D82Error("load isolation mechanism drift")
    if requirement.get("target_cpu") != 15:
        raise D82Error("target CPU drift")
    if requirement.get("target_cpu_topology") != "SINGLE_THREAD_E_CORE_NO_SMT_SIBLING":
        raise D82Error("target CPU topology drift")
    if requirement.get("irq_affinity_target_conflict_count_required") != 0:
        raise D82Error("IRQ isolation weakened")

    authority = contract.get("authority")
    if not isinstance(authority, Mapping):
        raise D82Error("authority missing")
    for field in (
        "host_cgroup_mutations_executed",
        "timing_measurements_executed",
        "production_io_executed",
        "external_requests_sent",
        "scientific_kernel_calls_executed",
    ):
        if authority.get(field) != 0:
            raise D82Error("forbidden execution recorded")
    if authority.get("numeric_runtime_seconds_proven") is not False:
        raise D82Error("numeric runtime proof authority opened")
    if authority.get("full53_execution_authorized") is not False:
        raise D82Error("full53 authority opened")


def build_result(contract: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    requirement = contract["load_isolation_requirement"]
    isolation = evaluate_isolation(snapshot, requirement)
    admitted = isolation["admitted"]
    observation = {
        "d81_environment_identity_except_cgroup_path_matches": snapshot[
            "d81_environment_identity_except_cgroup_path_matches"
        ],
        "root_cpuset_controller_available": snapshot["root_cpuset_controller_available"],
        "root_cpuset_subtree_enabled": snapshot["root_cpuset_subtree_enabled"],
        "target_service_cgroup_path_exact": (
            snapshot["current_cgroup_path"] == requirement["target_service_cgroup_path"]
        ),
        "partition_state_isolated": (
            snapshot["current_partition_state"] == requirement["partition_state_required"]
        ),
        "effective_cpu_set_exact": (
            snapshot["current_effective_cpus"] == requirement["effective_cpu_set_required"]
        ),
        "exclusive_effective_cpu_set_exact": (
            snapshot["current_exclusive_effective_cpus"]
            == requirement["exclusive_effective_cpu_set_required"]
        ),
        "target_cpu_root_isolated": (
            requirement["target_cpu"] in parse_cpu_list(snapshot["root_isolated_cpus"])
        ),
        "process_affinity_exact": (
            snapshot["process_affinity"] == requirement["process_affinity_required"]
        ),
        "target_cpu_online": snapshot["target_cpu_online"],
        "target_cpu_has_no_smt_sibling": (
            snapshot["target_cpu_thread_siblings"] == str(requirement["target_cpu"])
        ),
        "irq_affinity_excludes_target": (
            snapshot["irq_affinity_target_conflict_count"]
            == requirement["irq_affinity_target_conflict_count_required"]
        ),
    }
    if admitted:
        status = "VERIFIED_D82_OWNER_POLICY_AND_LOAD_ISOLATION_ADMITTED"
        decision = "READY_D82_FOR_D83_SEALED_PREMEASUREMENT_PACKET_GENERATION"
        next_gate = "D83_SEALED_PREMEASUREMENT_PACKET_GENERATION"
        missing_inputs: list[str] = []
    else:
        status = "VERIFIED_D82_OWNER_POLICY_FROZEN_LOAD_ISOLATION_FAIL_CLOSED"
        decision = "BLOCKED_D82_OWNER_POLICY_FROZEN_HOST_ISOLATION_NOT_ADMITTED"
        next_gate = "HOST_ADMIN_CPUSET_ISOLATED_PARTITION_PROVISIONING_AND_FRESH_D82_RECEIPT"
        missing_inputs = ["concurrent_load_exclusion_mechanism"]
    return {
        "status": status,
        "source_pin_count": 3,
        "owner_numeric_policy_frozen": True,
        "runtime_claim_class": contract["owner_decision"]["runtime_claim_class"],
        "confirmatory_samples_per_operation_class": 459,
        "operation_class_count": 5,
        "total_confirmatory_samples": 2295,
        "familywise_confidence_lower_bound": "95/100",
        "timeout_policy_frozen": True,
        "load_isolation_admitted": admitted,
        "load_isolation_observation": observation,
        "load_isolation_failed_predicates": isolation["failed_predicates"],
        "missing_input_count": len(missing_inputs),
        "missing_inputs": missing_inputs,
        "environment_recapture_required": True,
        "host_cgroup_mutations_executed": 0,
        "timing_measurements_executed": 0,
        "production_io_executed": 0,
        "external_requests_sent": 0,
        "scientific_kernel_calls_executed": 0,
        "numeric_runtime_seconds_proven": False,
        "full53_execution_authorized": False,
        "decision": decision,
        "next_gate": next_gate,
    }


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    verify_contract(contract)
    result = build_result(contract, current_isolation_snapshot(contract["load_isolation_requirement"]))
    if load(RESULT) != result:
        raise D82Error("result drift")
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
