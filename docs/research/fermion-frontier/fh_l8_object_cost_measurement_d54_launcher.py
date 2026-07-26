#!/usr/bin/env python3
"""Fail-closed isolated launcher for the authorized FH-L8 D54 sample plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUNNER = HERE / "fh_l8_object_cost_measurement_d54_runner.py"
AUTH = HERE / "fh_l8_object_cost_measurement_d54r_v3_authorization.json"
D53 = HERE / "fh_l8_object_cost_measurement_d53_contract.json"
ALLOWED_PARENT = Path("/Data/CascadeProjects/.ab-experiments")
ROOT = ALLOWED_PARENT / "fh-l8-d54-object-cost-v3"
MAX_CAPTURE = 1_048_576
TIMEOUT_SECONDS = 180


class LaunchError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii") + b"\n"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LaunchError(f"{path.name}: object required")
    return value


def publish(path: Path, raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_CAPTURE or os.path.lexists(path):
        raise LaunchError(f"unsafe publication: {path.name}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb", buffering=0) as handle:
            handle.write(raw)
            os.fsync(handle.fileno())
        os.link(temporary, path, follow_symlinks=False)
        os.unlink(temporary)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return {"path": path.name, "bytes": len(raw), "sha256": sha(raw)}


def cgroup_path() -> Path:
    rows = Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines()
    unified = [row.split(":", 2)[2] for row in rows if row.startswith("0::")]
    if len(unified) != 1:
        raise LaunchError("unified cgroup identity unavailable")
    path = Path("/sys/fs/cgroup") / unified[0].lstrip("/")
    if not path.is_dir():
        raise LaunchError("cgroup path unavailable")
    return path


def integer_file(root: Path, name: str) -> int:
    raw = (root / name).read_text(encoding="ascii").strip()
    if not raw.isdigit():
        raise LaunchError(f"invalid {name}")
    return int(raw)


def event_file(root: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in (root / "memory.events").read_text(encoding="ascii").splitlines():
        key, raw = row.split()
        if key in result or not raw.isdigit():
            raise LaunchError("invalid memory.events")
        result[key] = int(raw)
    for required in ("oom", "oom_kill"):
        if required not in result:
            raise LaunchError("incomplete memory.events")
    return result


def worker(args: argparse.Namespace) -> int:
    root = cgroup_path()
    before = event_file(root)
    command = [
        sys.executable, "-I", "-B", str(RUNNER),
        "--authorization", str(AUTH),
        "--tier", args.tier, "--size", str(args.size),
        "--sample-kind", args.sample_kind, "--repetition", str(args.repetition),
    ]
    completed = subprocess.run(
        command, cwd=HERE, env={
            "HOME": str(Path.home()), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONMALLOC": "default",
        }, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT_SECONDS,
        check=False,
    )
    after = event_file(root)
    swap = integer_file(root, "memory.swap.current")
    envelope = {
        "schema_version": 1,
        "sample": {
            "tier": args.tier, "size": args.size,
            "sample_kind": args.sample_kind, "repetition": args.repetition,
        },
        "runner_return_code": completed.returncode,
        "runner_stdout_bytes": len(completed.stdout),
        "runner_stdout_sha256": sha(completed.stdout),
        "runner_stderr_bytes": len(completed.stderr),
        "runner_stderr_sha256": sha(completed.stderr),
        "runner_stdout": completed.stdout.decode("utf-8", errors="strict"),
        "runner_stderr": completed.stderr.decode("utf-8", errors="strict"),
        "cgroup_memory_current_bytes": integer_file(root, "memory.current"),
        "cgroup_memory_peak_bytes": integer_file(root, "memory.peak"),
        "cgroup_memory_events_delta": {
            key: after.get(key, 0) - before.get(key, 0) for key in sorted(set(before) | set(after))
        },
        "cgroup_swap_current_bytes": swap,
        "cgroup_path": str(root.relative_to("/sys/fs/cgroup")),
        "network_interfaces": sorted(
            row.split(":", 1)[0].strip()
            for row in Path("/proc/net/dev").read_text(encoding="ascii").splitlines()
            if ":" in row
        ),
    }
    print(canonical(envelope).decode("ascii"), end="")
    return 0


def sample_name(sample: dict[str, Any]) -> str:
    tier = "synthetic" if sample["tier"] == "synthetic_object_calibration" else "fixed64"
    return f"{tier}-n{sample['size']}-{sample['sample_kind']}-r{sample['repetition']}"


def plan() -> list[dict[str, Any]]:
    d53 = load(D53)
    result: list[dict[str, Any]] = []
    for tier in d53["fixture_tiers"]:
        for size in tier.get("sizes", tier.get("sample_prefix_sizes")):
            for kind, count in (
                ("warmup", d53["isolation"]["warmup_runs_per_size"]),
                ("measured", d53["isolation"]["measured_runs_per_size"]),
            ):
                for repetition in range(count):
                    result.append({"tier": tier["tier"], "size": size,
                                   "sample_kind": kind, "repetition": repetition})
    return result


def validate_envelope(raw: bytes, sample: dict[str, Any]) -> dict[str, Any]:
    if len(raw) > MAX_CAPTURE:
        raise LaunchError("worker output cap exceeded")
    envelope = json.loads(raw)
    if envelope.get("sample") != sample or envelope.get("runner_return_code") != 0:
        raise LaunchError("worker sample/runner status mismatch")
    if envelope.get("runner_stderr_bytes") != 0 or envelope.get("cgroup_swap_current_bytes") != 0:
        raise LaunchError("stderr or swap fails closed")
    if envelope.get("network_interfaces") != ["lo"]:
        raise LaunchError("network namespace isolation unavailable")
    events = envelope.get("cgroup_memory_events_delta", {})
    if events.get("oom") != 0 or events.get("oom_kill") != 0:
        raise LaunchError("OOM event fails closed")
    result = json.loads(envelope["runner_stdout"])
    if any(result.get(key) != value for key, value in sample.items()):
        raise LaunchError("runner result identity drift")
    if result.get("packed_q3_reads") != 0:
        raise LaunchError("packed-q3 authority violation")
    envelope["result"] = result
    del envelope["runner_stdout"]
    del envelope["runner_stderr"]
    return envelope


def git_identity() -> str:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout
    if dirty:
        raise LaunchError("execution requires committed clean source")
    return head


def launch() -> dict[str, Any]:
    authorization = load(AUTH)
    if ROOT != Path(authorization["isolation"]["scratch_root"]):
        raise LaunchError("scratch authorization drift")
    if os.path.lexists(ROOT) or ROOT.parent.resolve() != ALLOWED_PARENT.resolve():
        raise LaunchError("authorized scratch must start absent")
    samples = plan()
    if len(samples) != authorization["sample_plan"]["total_fresh_processes"]:
        raise LaunchError("sample plan drift")
    commit = git_identity()
    ROOT.mkdir(mode=0o700)
    receipts = ROOT / "receipts"
    receipts.mkdir(mode=0o700)
    identities = []
    for index, sample in enumerate(samples):
        name = sample_name(sample)
        unit = f"ab-fh-l8-d54-{index:02d}-{os.getpid()}"
        command = [
            "/usr/bin/systemd-run", "--user", "--quiet", "--wait", "--collect", "--pipe",
            f"--unit={unit}", "--service-type=exec", "--property=AllowedCPUs=0",
            "--property=MemoryAccounting=yes", "--property=MemoryMax=536870912",
            "--property=MemoryHigh=402653184", "--property=MemorySwapMax=0",
            "--property=OOMPolicy=stop", "--property=TasksMax=16",
            f"--property=RuntimeMaxSec={TIMEOUT_SECONDS + 10}s",
            "/usr/bin/bwrap", "--unshare-net", "--ro-bind", "/", "/",
            "--dev", "/dev", "--proc", "/proc", "--chdir", str(HERE),
            "/usr/bin/env", "-i", f"HOME={Path.home()}", "PATH=/usr/bin:/bin",
            "LANG=C.UTF-8", "LC_ALL=C.UTF-8", "PYTHONDONTWRITEBYTECODE=1",
            sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--worker",
            "--tier", sample["tier"], "--size", str(sample["size"]),
            "--sample-kind", sample["sample_kind"], "--repetition", str(sample["repetition"]),
        ]
        completed = subprocess.run(
            command, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=TIMEOUT_SECONDS + 20, check=False,
        )
        if completed.returncode or completed.stderr:
            raise LaunchError(
                f"{name}: isolated launch failed ({completed.returncode}, {completed.stderr[:512]!r})"
            )
        envelope = validate_envelope(completed.stdout, sample)
        identity = publish(receipts / f"{name}.json", canonical(envelope))
        identities.append({**sample, **identity})
    state = {
        "schema_version": 1, "status": "D54_RAW_SAMPLE_SET_COMPLETE",
        "source_commit": commit, "authorization_sha256": sha(AUTH.read_bytes()),
        "sample_count": len(identities), "receipts": identities,
        "packed_q3_reads": 0, "full53_executed": False,
        "full53_extrapolation_performed": False,
    }
    state_id = publish(ROOT / "launcher-state.json", canonical(state))
    return {"status": state["status"], "sample_count": len(identities),
            "scratch_root": str(ROOT), "launcher_state": state_id}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--worker", action="store_true")
    value.add_argument("--tier")
    value.add_argument("--size", type=int)
    value.add_argument("--sample-kind")
    value.add_argument("--repetition", type=int)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        result = worker(args) if args.worker else launch()
    except Exception as exc:
        print(canonical({"status": "INDETERMINATE_MEASUREMENT_FAILURE",
                         "error": f"{type(exc).__name__}: {exc}"}).decode("ascii"), end="")
        return 1
    if not args.worker:
        print(canonical(result).decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
