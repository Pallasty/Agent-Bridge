#!/usr/bin/env python3
"""Launch/resume the authorized D54 sample plan in isolated user services."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "fh_l8_object_cost_measurement_d54r_runner.py"
WORKER = HERE / "fh_l8_object_cost_measurement_d54_worker.py"
AUTHORIZATION = HERE / "fh_l8_object_cost_measurement_d54r_authorization.json"
D53 = HERE / "fh_l8_object_cost_measurement_d53_contract.json"


class LauncherError(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise LauncherError(f"{path}: JSON object required")
    return value


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def plan() -> list[dict[str, Any]]:
    spec = importlib.util.spec_from_file_location("d54_runner_plan", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.sample_plan(load(D53))


def atomic_write(path: Path, payload: bytes) -> None:
    staging = path.with_suffix(path.suffix + ".tmp")
    if staging.exists() or path.exists():
        raise LauncherError(f"publication target already exists: {path}")
    with staging.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.rename(staging, path)


def properties(unit: str) -> dict[str, str]:
    names = [
        "Id",
        "ActiveState",
        "SubState",
        "Result",
        "ExecMainCode",
        "ExecMainStatus",
        "MemoryPeak",
    ]
    completed = subprocess.run(
        ["systemctl", "--user", "show", f"{unit}.service", *[f"-p{name}" for name in names]],
        check=True,
        capture_output=True,
        text=True,
    )
    return dict(line.split("=", 1) for line in completed.stdout.splitlines() if "=" in line)


def stop_unit(unit: str) -> None:
    subprocess.run(
        ["systemctl", "--user", "stop", f"{unit}.service"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["systemctl", "--user", "reset-failed", f"{unit}.service"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def validate_receipt(receipt: Mapping[str, Any], requested: Mapping[str, Any], auth: Mapping[str, Any]) -> None:
    if receipt.get("status") != "COMPLETED_D54_FRESH_OBJECT_COST_SAMPLE":
        raise LauncherError("worker receipt status drift")
    runner = receipt.get("runner")
    if not isinstance(runner, Mapping):
        raise LauncherError("runner receipt missing")
    for key, value in requested.items():
        if runner.get(key) != value:
            raise LauncherError(f"runner sample identity drift: {key}")
    if runner.get("packed_q3_reads") != 0:
        raise LauncherError("packed-q3 read observed")
    if runner.get("scientific_kernel_calls", 0) > auth["sample_plan"][
        "maximum_scientific_kernel_calls_per_process"
    ]:
        raise LauncherError("scientific call cap exceeded")
    cgroup = receipt.get("cgroup")
    if not isinstance(cgroup, Mapping) or cgroup.get("swap_current_bytes") != 0:
        raise LauncherError("zero-swap condition failed")
    delta = cgroup.get("events_delta", {})
    if delta.get("oom", 0) or delta.get("oom_kill", 0):
        raise LauncherError("OOM event observed")
    if cgroup.get("memory_peak_bytes", 1 << 63) > auth["isolation"]["memory_max_bytes"]:
        raise LauncherError("cgroup memory peak exceeds authorization")


def launch_one(index: int, requested: Mapping[str, Any], scratch: Path, auth: Mapping[str, Any]) -> Mapping[str, Any]:
    unit = f"ab-fh-l8-d54-{index:03d}"
    capture = scratch / "captures"
    stdout = capture / f"{index:03d}.stdout"
    stderr = capture / f"{index:03d}.stderr"
    stop_unit(unit)
    command = [
        "/usr/bin/systemd-run",
        "--user",
        "--quiet",
        "--remain-after-exit",
        f"--unit={unit}",
        "--service-type=exec",
        "--property=MemoryAccounting=yes",
        "--property=MemoryMax=536870912",
        "--property=MemoryHigh=402653184",
        "--property=MemorySwapMax=0",
        "--property=AllowedCPUs=0",
        "--property=OOMPolicy=stop",
        "--property=TimeoutStartSec=240s",
        "--property=RuntimeMaxSec=240s",
        "--property=TasksMax=16",
        "--property=IPAddressDeny=any",
        f"--property=StandardOutput=file:{stdout}",
        f"--property=StandardError=file:{stderr}",
        sys.executable,
        "-I",
        "-B",
        str(WORKER),
        "--runner",
        str(RUNNER),
        "--authorization",
        str(AUTHORIZATION),
        "--tier",
        str(requested["tier"]),
        "--size",
        str(requested["size"]),
        "--sample-kind",
        str(requested["sample_kind"]),
        "--repetition",
        str(requested["repetition"]),
    ]
    completed = subprocess.run(command, check=False, capture_output=True)
    if completed.returncode or completed.stdout or completed.stderr:
        raise LauncherError(f"systemd-run failed: {completed.returncode} {completed.stderr!r}")
    deadline = time.monotonic() + 245
    while True:
        state = properties(unit)
        if state.get("SubState") in {"exited", "failed", "dead"}:
            break
        if time.monotonic() > deadline:
            stop_unit(unit)
            raise LauncherError("sample unit timeout")
        time.sleep(0.1)
    raw_stdout = stdout.read_bytes()
    raw_stderr = stderr.read_bytes()
    if (
        state.get("Result") != "success"
        or state.get("ExecMainStatus") != "0"
        or raw_stderr
    ):
        stop_unit(unit)
        raise LauncherError(f"sample unit failed: {state}, stderr={raw_stderr!r}")
    try:
        receipt = json.loads(raw_stdout)
    except json.JSONDecodeError as error:
        stop_unit(unit)
        raise LauncherError(f"worker stdout is not JSON: {error}") from error
    validate_receipt(receipt, requested, auth)
    receipt = {
        **receipt,
        "launcher": {
            "unit": unit,
            "systemd_memory_peak_bytes": int(state["MemoryPeak"]),
            "worker_stdout_sha256": digest_bytes(raw_stdout),
            "worker_stderr_sha256": digest_bytes(raw_stderr),
        },
    }
    stop_unit(unit)
    stdout.unlink()
    stderr.unlink()
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    auth = load(AUTHORIZATION)
    scratch = Path(auth["isolation"]["scratch_root"])
    samples = plan()
    if len(samples) != auth["sample_plan"]["total_fresh_processes"]:
        raise LauncherError("sample-plan count drift")
    manifest = {
        "schema_version": 1,
        "authorization_sha256": digest(AUTHORIZATION),
        "runner_sha256": digest(RUNNER),
        "worker_sha256": digest(WORKER),
        "sample_plan_sha256": digest_bytes(canonical(samples)),
        "sample_count": len(samples),
    }
    if not scratch.exists():
        scratch.mkdir(mode=0o700, parents=False)
        (scratch / "samples").mkdir(mode=0o700)
        (scratch / "captures").mkdir(mode=0o700)
        atomic_write(scratch / "manifest.json", canonical(manifest))
    elif load(scratch / "manifest.json") != manifest:
        raise LauncherError("resume manifest drift")
    limit = len(samples) if args.limit is None else min(args.limit, len(samples))
    for index, requested in enumerate(samples[:limit]):
        target = scratch / "samples" / f"{index:03d}.json"
        if target.exists():
            validate_receipt(load(target), requested, auth)
            continue
        receipt = launch_one(index, requested, scratch, auth)
        atomic_write(target, canonical(receipt))
        print(f"completed {index + 1}/{len(samples)}", flush=True)
    completed = len(list((scratch / "samples").glob("*.json")))
    print(json.dumps({"status": "COMPLETE" if completed == len(samples) else "INCOMPLETE", "completed": completed, "total": len(samples)}))


if __name__ == "__main__":
    main()
