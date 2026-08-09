#!/usr/bin/env python3
"""Reversible host-admin transaction for the FH-L8 D82 CPU15 partition."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_isolation_transaction_d82r_contract.json"
CGROUP_ROOT = Path("/sys/fs/cgroup")
IRQ_ROOT = Path("/proc/irq")
CPU_ROOT = Path("/sys/devices/system/cpu")


class D82RTransactionError(RuntimeError):
    pass


def load_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D82RTransactionError(f"object required: {path}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_cpu_list(spec: str) -> set[int]:
    result: set[int] = set()
    for part in spec.strip().split(","):
        if not part:
            continue
        if "-" in part:
            first_text, last_text = part.split("-", 1)
            first, last = int(first_text), int(last_text)
            if first > last:
                raise D82RTransactionError("descending CPU range")
            result.update(range(first, last + 1))
        else:
            result.add(int(part))
    return result


def format_cpu_list(cpus: set[int]) -> str:
    if not cpus:
        raise D82RTransactionError("empty CPU set")
    ordered = sorted(cpus)
    ranges: list[str] = []
    start = previous = ordered[0]
    for cpu in ordered[1:]:
        if cpu == previous + 1:
            previous = cpu
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = cpu
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(ranges)


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-ISOLATION-TRANSACTION-D82R-V1":
        raise D82RTransactionError("contract identity drift")
    baseline = str(contract.get("baseline_commit", ""))
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", baseline, "HEAD"],
        check=False,
        capture_output=True,
    ).returncode != 0:
        raise D82RTransactionError("HEAD is not descended from baseline")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / name) != expected:
            raise D82RTransactionError(f"source pin drift: {name}")
    target = contract["target"]
    if target["cpu"] != 15 or target["thread_siblings"] != "15":
        raise D82RTransactionError("target CPU drift")
    if target["service_cgroup"] != (
        "fh-l8-d60-isolated.slice/fh-l8-d82-measurement.service"
    ):
        raise D82RTransactionError("service cgroup drift")
    transaction = contract["transaction"]
    if transaction["modes"] != ["plan", "apply", "verify", "run", "rollback"]:
        raise D82RTransactionError("transaction mode drift")
    if any(
        transaction[field] is not True
        for field in (
            "state_written_before_first_mutation",
            "rollback_refuses_populated_service",
            "rollback_refuses_irq_drift",
            "root_cpuset_disabled_only_if_enabled_by_this_transaction",
            "automatic_rollback_on_apply_failure",
            "run_requires_applied_state_and_green_verification",
        )
    ):
        raise D82RTransactionError("rollback policy weakened")


class RealBackend:
    def __init__(self, state_file: Path):
        self.state_file = state_file

    @staticmethod
    def euid() -> int:
        return os.geteuid()

    @staticmethod
    def read(path: Path) -> str:
        return path.read_text(encoding="utf-8").strip()

    @staticmethod
    def exists(path: Path) -> bool:
        return path.exists()

    @staticmethod
    def mkdir(path: Path) -> None:
        path.mkdir(mode=0o755)

    @staticmethod
    def rmdir(path: Path) -> None:
        path.rmdir()

    @staticmethod
    def write(path: Path, value: str) -> None:
        path.write_text(value, encoding="utf-8")

    @staticmethod
    def irq_paths() -> list[Path]:
        return sorted(IRQ_ROOT.glob("*/smp_affinity_list"), key=lambda path: int(path.parent.name))

    def state_exists(self) -> bool:
        return self.state_file.exists()

    def save_state(self, state: Mapping[str, Any]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".fh-l8-d82-", dir=self.state_file.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.state_file)
        finally:
            try:
                Path(temp_name).unlink()
            except FileNotFoundError:
                pass

    def load_state(self) -> Mapping[str, Any]:
        return load_json(self.state_file)

    def delete_state(self) -> None:
        self.state_file.unlink()


def add_controller(backend: Any, path: Path, controller: str) -> None:
    backend.write(path, f"+{controller}")
    if controller not in backend.read(path).split():
        raise D82RTransactionError(f"controller enable failed: {path}")


def remove_controller(backend: Any, path: Path, controller: str) -> None:
    backend.write(path, f"-{controller}")
    if controller in backend.read(path).split():
        raise D82RTransactionError(f"controller disable failed: {path}")


def write_exact(backend: Any, path: Path, value: str) -> None:
    backend.write(path, value)
    observed = backend.read(path)
    if path.name in {"cpuset.cpus", "cpuset.cpus.exclusive"}:
        if parse_cpu_list(observed) != parse_cpu_list(value):
            raise D82RTransactionError(f"CPU-set write drift: {path}")
    elif observed != value:
        raise D82RTransactionError(f"write drift: {path}")


def plan(backend: Any, contract: Mapping[str, Any]) -> dict[str, Any]:
    target = contract["target"]
    cpu = int(target["cpu"])
    parent = CGROUP_ROOT / target["parent_cgroup"]
    service = CGROUP_ROOT / target["service_cgroup"]
    controllers = set(backend.read(CGROUP_ROOT / "cgroup.controllers").split())
    subtree = set(backend.read(CGROUP_ROOT / "cgroup.subtree_control").split())
    online = parse_cpu_list(backend.read(CPU_ROOT / "online"))
    siblings = backend.read(CPU_ROOT / f"cpu{cpu}" / "topology/thread_siblings_list")
    conflicts = [
        str(path)
        for path in backend.irq_paths()
        if cpu in parse_cpu_list(backend.read(path))
    ]
    blockers: list[str] = []
    if backend.euid() != contract["transaction"]["apply_requires_euid"]:
        blockers.append("host_admin_credential_missing")
    if "cpuset" not in controllers:
        blockers.append("root_cpuset_controller_missing")
    if cpu not in online:
        blockers.append("target_cpu_offline")
    if siblings != target["thread_siblings"]:
        blockers.append("target_cpu_smt_topology_drift")
    if backend.exists(parent) or backend.exists(service):
        blockers.append("target_cgroup_already_exists")
    if backend.state_exists():
        blockers.append("transaction_state_already_exists")
    return {
        "status": "READY" if not blockers else "BLOCKED",
        "euid": backend.euid(),
        "root_cpuset_available": "cpuset" in controllers,
        "root_cpuset_already_enabled": "cpuset" in subtree,
        "target_cpu": cpu,
        "target_cpu_online": cpu in online,
        "target_cpu_thread_siblings": siblings,
        "irq_conflict_count": len(conflicts),
        "irq_conflict_paths": conflicts,
        "blockers": blockers,
        "mutations_executed": 0,
    }


def verify_applied(backend: Any, contract: Mapping[str, Any]) -> dict[str, Any]:
    target = contract["target"]
    cpu = int(target["cpu"])
    parent = CGROUP_ROOT / target["parent_cgroup"]
    service = CGROUP_ROOT / target["service_cgroup"]
    checks = {
        "root_cpuset_enabled": "cpuset"
        in backend.read(CGROUP_ROOT / "cgroup.subtree_control").split(),
        "parent_exists": backend.exists(parent),
        "service_exists": backend.exists(service),
    }
    if checks["parent_exists"]:
        checks.update(
            {
                "parent_cpu_exact": parse_cpu_list(backend.read(parent / "cpuset.cpus")) == {cpu},
                "parent_exclusive_exact": parse_cpu_list(
                    backend.read(parent / "cpuset.cpus.exclusive")
                )
                == {cpu},
                "parent_partition_root": backend.read(parent / "cpuset.cpus.partition")
                == target["parent_partition_state"],
                "parent_cpuset_enabled": "cpuset"
                in backend.read(parent / "cgroup.subtree_control").split(),
            }
        )
    if checks["service_exists"]:
        checks.update(
            {
                "service_cpu_exact": parse_cpu_list(backend.read(service / "cpuset.cpus"))
                == {cpu},
                "service_exclusive_exact": parse_cpu_list(
                    backend.read(service / "cpuset.cpus.exclusive")
                )
                == {cpu},
                "service_partition_isolated": backend.read(service / "cpuset.cpus.partition")
                == target["service_partition_state"],
            }
        )
    conflicts = sum(
        cpu in parse_cpu_list(backend.read(path)) for path in backend.irq_paths()
    )
    checks["irq_conflicts_zero"] = conflicts == target["irq_conflict_count_required"]
    return {
        "status": "VERIFIED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "irq_conflict_count": conflicts,
    }


def apply(backend: Any, contract: Mapping[str, Any]) -> dict[str, Any]:
    current_plan = plan(backend, contract)
    if current_plan["blockers"]:
        raise D82RTransactionError("apply blocked: " + ",".join(current_plan["blockers"]))
    target = contract["target"]
    cpu = int(target["cpu"])
    parent = CGROUP_ROOT / target["parent_cgroup"]
    service = CGROUP_ROOT / target["service_cgroup"]
    root_subtree = CGROUP_ROOT / "cgroup.subtree_control"
    root_cpuset_was_enabled = current_plan["root_cpuset_already_enabled"]
    irq_changes = []
    for path_text in current_plan["irq_conflict_paths"]:
        path = Path(path_text)
        original = backend.read(path)
        remaining = parse_cpu_list(original) - {cpu}
        if not remaining:
            remaining = {min(parse_cpu_list(backend.read(CPU_ROOT / "online")) - {cpu})}
        irq_changes.append(
            {"path": path_text, "original": original, "applied": format_cpu_list(remaining)}
        )
    state: dict[str, Any] = {
        "schema_version": 1,
        "status": "applying",
        "root_cpuset_was_enabled": root_cpuset_was_enabled,
        "parent_cgroup": str(parent),
        "service_cgroup": str(service),
        "irq_changes": irq_changes,
    }
    backend.save_state(state)
    try:
        if not root_cpuset_was_enabled:
            add_controller(backend, root_subtree, "cpuset")
        mems = backend.read(CGROUP_ROOT / "cpuset.mems.effective")
        if not mems:
            raise D82RTransactionError("root effective memory nodes empty")
        backend.mkdir(parent)
        write_exact(backend, parent / "cpuset.mems", mems)
        write_exact(backend, parent / "cpuset.cpus", target["cpu_set"])
        write_exact(backend, parent / "cpuset.cpus.exclusive", target["cpu_set"])
        write_exact(backend, parent / "cpuset.cpus.partition", target["parent_partition_state"])
        add_controller(backend, parent / "cgroup.subtree_control", "cpuset")
        backend.mkdir(service)
        write_exact(backend, service / "cpuset.mems", mems)
        write_exact(backend, service / "cpuset.cpus", target["cpu_set"])
        write_exact(backend, service / "cpuset.cpus.exclusive", target["cpu_set"])
        write_exact(backend, service / "cpuset.cpus.partition", target["service_partition_state"])
        for change in irq_changes:
            write_exact(backend, Path(change["path"]), change["applied"])
        verification = verify_applied(backend, contract)
        if verification["status"] != "VERIFIED":
            raise D82RTransactionError("post-apply verification failed")
        state["status"] = "applied"
        backend.save_state(state)
        return {"status": "APPLIED", "verification": verification}
    except Exception as error:
        rollback_error = None
        try:
            rollback(backend, contract, allow_applying=True)
        except Exception as nested:
            rollback_error = str(nested)
        suffix = f"; rollback failed: {rollback_error}" if rollback_error else "; rolled back"
        raise D82RTransactionError(f"apply failed: {error}{suffix}") from error


def rollback(
    backend: Any, contract: Mapping[str, Any], *, allow_applying: bool = False
) -> dict[str, Any]:
    if backend.euid() != contract["transaction"]["apply_requires_euid"]:
        raise D82RTransactionError("rollback requires host admin credential")
    if not backend.state_exists():
        raise D82RTransactionError("transaction state missing")
    state = backend.load_state()
    if state.get("status") not in ({"applied", "applying"} if allow_applying else {"applied"}):
        raise D82RTransactionError("transaction state not rollback-eligible")
    service = Path(state["service_cgroup"])
    parent = Path(state["parent_cgroup"])
    if backend.exists(service) and backend.read(service / "cgroup.procs"):
        raise D82RTransactionError("service cgroup populated; rollback refused")
    for change in state["irq_changes"]:
        path = Path(change["path"])
        current = backend.read(path)
        if current not in {change["applied"], change["original"]}:
            raise D82RTransactionError(f"IRQ affinity drift; rollback refused: {path}")
    for change in reversed(state["irq_changes"]):
        path = Path(change["path"])
        if backend.read(path) == change["applied"]:
            write_exact(backend, path, change["original"])
    if backend.exists(service):
        write_exact(backend, service / "cpuset.cpus.partition", "member")
        backend.rmdir(service)
    if backend.exists(parent):
        if "cpuset" in backend.read(parent / "cgroup.subtree_control").split():
            remove_controller(backend, parent / "cgroup.subtree_control", "cpuset")
        write_exact(backend, parent / "cpuset.cpus.partition", "member")
        backend.rmdir(parent)
    if not state["root_cpuset_was_enabled"]:
        remove_controller(backend, CGROUP_ROOT / "cgroup.subtree_control", "cpuset")
    backend.delete_state()
    return {"status": "ROLLED_BACK"}


def validate_run_preconditions(backend: Any, contract: Mapping[str, Any]) -> None:
    if backend.euid() != contract["transaction"]["apply_requires_euid"]:
        raise D82RTransactionError("run requires host admin credential")
    if not backend.state_exists() or backend.load_state().get("status") != "applied":
        raise D82RTransactionError("run requires applied transaction state")
    if verify_applied(backend, contract)["status"] != "VERIFIED":
        raise D82RTransactionError("run requires green isolation verification")


def run_command(backend: Any, contract: Mapping[str, Any], command: list[str]) -> dict[str, Any]:
    validate_run_preconditions(backend, contract)
    if not command:
        raise D82RTransactionError("run command missing")
    target = contract["target"]
    service = CGROUP_ROOT / target["service_cgroup"]
    child = os.fork()
    if child == 0:
        try:
            backend.write(service / "cgroup.procs", str(os.getpid()))
            os.sched_setaffinity(0, {int(target["cpu"])})
            os.execvp(command[0], command)
        except BaseException:
            os._exit(126)
    _, status = os.waitpid(child, 0)
    exit_code = os.waitstatus_to_exitcode(status)
    return {"status": "COMMAND_EXITED", "exit_code": exit_code}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["plan", "apply", "verify", "run", "rollback"])
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    contract = load_json(CONTRACT)
    verify_contract(contract)
    state_file = args.state_file or Path(contract["target"]["state_file"])
    backend = RealBackend(state_file)
    if args.mode == "plan":
        result = plan(backend, contract)
    elif args.mode == "apply":
        result = apply(backend, contract)
    elif args.mode == "verify":
        result = verify_applied(backend, contract)
    elif args.mode == "run":
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        result = run_command(backend, contract, command)
    else:
        result = rollback(backend, contract)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except D82RTransactionError as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from error
