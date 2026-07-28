#!/usr/bin/env python3
"""Run one authorized D54 sample and attach in-cgroup resource metrics."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


class WorkerError(RuntimeError):
    pass


def cgroup_root() -> Path:
    for line in Path("/proc/self/cgroup").read_text().splitlines():
        fields = line.split(":", 2)
        if len(fields) == 3 and fields[0] == "0":
            return Path("/sys/fs/cgroup") / fields[2].lstrip("/")
    raise WorkerError("unified cgroup path not found")


def integer_file(root: Path, name: str) -> int:
    value = (root / name).read_text().strip()
    if not value.isdigit():
        raise WorkerError(f"{name} is not an integer")
    return int(value)


def events(root: Path) -> dict[str, int]:
    result = {}
    for line in (root / "memory.events").read_text().splitlines():
        key, value = line.split()
        result[key] = int(value)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--tier", required=True)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--sample-kind", required=True)
    parser.add_argument("--repetition", type=int, required=True)
    args = parser.parse_args()

    root = cgroup_root()
    before = events(root)
    command = [
        sys.executable,
        "-I",
        "-B",
        str(args.runner),
        "--authorization",
        str(args.authorization),
        "--tier",
        args.tier,
        "--size",
        str(args.size),
        "--sample-kind",
        args.sample_kind,
        "--repetition",
        str(args.repetition),
    ]
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            "HOME": os.environ["HOME"],
            "PATH": os.environ["PATH"],
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    after = events(root)
    if completed.returncode or completed.stderr:
        raise WorkerError(
            f"sample runner failed: return={completed.returncode}, stderr={completed.stderr!r}"
        )
    try:
        runner = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise WorkerError(f"runner stdout is not JSON: {error}") from error
    delta = {
        key: after.get(key, 0) - before.get(key, 0)
        for key in sorted(set(before) | set(after))
    }
    receipt = {
        "schema_version": 1,
        "status": "COMPLETED_D54_FRESH_OBJECT_COST_SAMPLE",
        "runner": runner,
        "cgroup": {
            "path": str(root),
            "memory_current_bytes": integer_file(root, "memory.current"),
            "memory_peak_bytes": integer_file(root, "memory.peak"),
            "swap_current_bytes": integer_file(root, "memory.swap.current"),
            "events_before": before,
            "events_after": after,
            "events_delta": delta,
        },
    }
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
