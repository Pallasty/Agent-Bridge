#!/usr/bin/env python3
"""Verify the D81 D60 environment/margin precommit packet without timing work."""

from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_environment_margin_precommit_d81_contract.json"
RESULT = HERE / "fh_l8_d60_environment_margin_precommit_d81_result.json"


class D81Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D81Error(f"object required: {path.name}")
    return value


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def command(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def current_environment() -> dict[str, str]:
    governors = {
        path.read_text(encoding="utf-8").strip()
        for path in Path("/sys/devices/system/cpu").glob("cpu*/cpufreq/scaling_governor")
    }
    if len(governors) != 1:
        raise D81Error("CPU governors are absent or non-uniform")
    cgroup_line = read("/proc/self/cgroup")
    if not cgroup_line.startswith("0::"):
        raise D81Error("unified cgroup v2 identity unavailable")
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "machine": platform.machine(),
        "cpu_model": command("bash", "-lc", "lscpu | sed -n 's/^Model name:[[:space:]]*//p'"),
        "online_cpu_list": read("/sys/devices/system/cpu/online"),
        "scaling_driver": read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver"),
        "scaling_governor": next(iter(governors)),
        "energy_performance_preference": read(
            "/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"
        ),
        "filesystem_type": command("findmnt", "-no", "FSTYPE", "--target", str(ROOT)),
        "cgroup_version": "v2",
        "cgroup_path": cgroup_line.removeprefix("0::"),
    }


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    result = load(RESULT)
    if contract.get("contract_id") != "FH-L8-D60-ENVIRONMENT-MARGIN-PRECOMMIT-D81-V1":
        raise D81Error("contract identity drift")
    baseline = str(contract.get("baseline_commit", ""))
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", baseline, "HEAD"],
        check=False,
    ).returncode != 0:
        raise D81Error("HEAD is not descended from the frozen D80 baseline")

    environment = contract.get("environment_precommit")
    if not isinstance(environment, Mapping):
        raise D81Error("environment precommit missing")
    observed = current_environment()
    for field, value in observed.items():
        if environment.get(field) != value:
            raise D81Error(f"environment identity drift: {field}")
    if environment.get("concurrent_load_exclusion_mechanism") is not None:
        raise D81Error("unverified load-exclusion mechanism claimed")

    if contract.get("selected_rule_form") != (
        "precommitted_measurement_population_margin_and_timeout_rule"
    ):
        raise D81Error("rule-form drift")
    population = contract.get("operation_population")
    if not isinstance(population, Mapping) or len(population) != 5:
        raise D81Error("operation population drift")
    if any(not isinstance(value, int) or value <= 0 for value in population.values()):
        raise D81Error("invalid operation population")

    rule = contract.get("rule_precommit")
    if not isinstance(rule, Mapping):
        raise D81Error("rule precommit missing")
    missing = [
        "concurrent_load_exclusion_mechanism",
        "measurement_margin",
        "timeout_policy",
    ]
    if rule.get("measurement_margin") is not None or rule.get("timeout_policy") is not None:
        raise D81Error("owner numeric policy was inferred")
    if result.get("missing_inputs") != missing or result.get("missing_input_count") != 3:
        raise D81Error("missing-input receipt drift")
    if result.get("decision") != contract.get("decision"):
        raise D81Error("decision drift")
    for field in (
        "timing_measurements_executed",
        "external_requests_sent",
        "scientific_kernel_calls_executed",
    ):
        if result.get(field) != 0:
            raise D81Error("forbidden execution recorded")
    if result.get("numeric_runtime_seconds_proven") is not False:
        raise D81Error("numeric runtime claimed")
    if result.get("full53_execution_authorized") is not False:
        raise D81Error("full53 authority claimed")
    return {
        "verification": "FH_L8_D60_ENVIRONMENT_MARGIN_PRECOMMIT_D81",
        "status": result["status"],
        "environment_identity_verified": True,
        "selected_rule_form": contract["selected_rule_form"],
        "missing_inputs": missing,
        "decision": result["decision"],
        "next_gate": result["next_gate"],
        "full53_execution_authorized": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
