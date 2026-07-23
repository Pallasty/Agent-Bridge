#!/usr/bin/env python3
"""Frozen systemd launcher and post-exit receipt publisher for FH-L8 D18-C."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "fh_l8_fresh_consumer_d18c_runner.py"
CHECKER = HERE / "fh_l8_fresh_consumer_d18c_checker.py"
CONTRACT = HERE / "fh_l8_fresh_consumer_d18c_contract.json"
ALLOWED_PARENT = Path("/Data/CascadeProjects/.ab-experiments")
UNIT_RE = re.compile(r"ab-fh-l8-d18c-[a-z0-9][a-z0-9-]{0,47}")
MAX_CAPTURE_BYTES = 262_144
MEMORY_MAX = "536870912"
MEMORY_HIGH = "402653184"
MEMORY_SWAP_MAX = "0"
CLEAN_ENV = {
    "HOME": str(Path.home()),
    "PATH": "/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PYTHONDONTWRITEBYTECODE": "1",
    "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
    "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{os.getuid()}/bus",
}


class LauncherError(ValueError):
    """The launch, runner, or post-exit publication failed closed."""


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_publish(path: Path, payload: bytes) -> dict[str, Any]:
    if len(payload) > MAX_CAPTURE_BYTES:
        raise LauncherError(f"{path.name} exceeds capture cap")
    temporary = path.with_name(f".{path.name}.launcher-{os.getpid()}")
    if os.path.lexists(path) or os.path.lexists(temporary):
        raise LauncherError(f"{path.name} already exists")
    try:
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(fd, "wb", buffering=0) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path, follow_symlinks=False)
        os.unlink(temporary)
        _fsync_dir(path.parent)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise LauncherError(f"cannot publish {path.name}: {exc}") from exc
    observed = path.read_bytes()
    if observed != payload:
        raise LauncherError(f"{path.name} post-publication rehash drift")
    return {"path": path.name, "bytes": len(observed), "sha256": _sha(observed)}


def _prepare_final_publication(
    path: Path, payload: bytes
) -> tuple[Path, dict[str, Any]]:
    """Fully validate final-receipt bytes before the final name exists."""
    if len(payload) > MAX_CAPTURE_BYTES:
        raise LauncherError(f"{path.name} exceeds capture cap")
    temporary = path.with_name(f".{path.name}.final-staging-{os.getpid()}")
    if os.path.lexists(path) or os.path.lexists(temporary):
        raise LauncherError(f"{path.name} final publication collision")
    try:
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(fd, "wb", buffering=0) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        metadata = temporary.lstat()
        observed = temporary.read_bytes()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
            or metadata.st_size != len(payload)
            or observed != payload
        ):
            raise LauncherError("final receipt staging identity drift")
        _fsync_dir(path.parent)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except BaseException:
            pass
        raise
    return temporary, {
        "path": path.name,
        "bytes": len(payload),
        "sha256": _sha(payload),
    }


def _publish_prepared_final(path: Path, temporary: Path) -> None:
    """Publish no-replace and persist; perform no fallible check afterwards."""
    linked = False
    try:
        if os.path.lexists(path):
            raise LauncherError(f"{path.name} already exists")
        os.link(temporary, path, follow_symlinks=False)
        linked = True
        os.unlink(temporary)
        _fsync_dir(path.parent)
    except BaseException:
        if linked:
            try:
                path.unlink(missing_ok=True)
                _fsync_dir(path.parent)
            except BaseException:
                pass
        else:
            try:
                temporary.unlink(missing_ok=True)
            except BaseException:
                pass
        raise


def _verify_runner_scratch_identity(
    scratch: Path, lock_fd: int, runner_result: dict[str, Any], phase: str
) -> None:
    custody = runner_result.get("scratch_custody")
    if not isinstance(custody, dict):
        raise LauncherError("runner scratch custody record missing")
    root = scratch.lstat()
    lock_path = (scratch / "exclusive.lock").lstat()
    lock_fd_stat = os.fstat(lock_fd)
    if (
        not stat.S_ISDIR(root.st_mode)
        or root.st_dev != custody.get("scratch_root_device")
        or root.st_ino != custody.get("scratch_root_inode")
        or root.st_uid != custody.get("scratch_root_owner_uid")
        or stat.S_IMODE(root.st_mode) != custody.get("scratch_root_mode")
        or not stat.S_ISREG(lock_path.st_mode)
        or lock_path.st_dev != custody.get("exclusive_lock_device")
        or lock_path.st_ino != custody.get("exclusive_lock_inode")
        or lock_path.st_ino != lock_fd_stat.st_ino
        or lock_path.st_dev != lock_fd_stat.st_dev
        or lock_path.st_uid != custody.get("exclusive_lock_owner_uid")
        or stat.S_IMODE(lock_path.st_mode) != custody.get("exclusive_lock_mode")
        or lock_path.st_nlink != 1
    ):
        raise LauncherError(f"runner scratch/lock identity drift at {phase}")


def _systemd_properties(unit: str) -> dict[str, str]:
    names = (
        "Id",
        "ActiveState",
        "SubState",
        "Result",
        "ExecMainCode",
        "ExecMainStatus",
        "MemoryPeak",
        "MemoryCurrent",
        "ControlGroup",
    )
    completed = subprocess.run(
        ["/usr/bin/systemctl", "--user", "show", unit, *[f"--property={name}" for name in names]],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=CLEAN_ENV,
        check=False,
    )
    if completed.returncode:
        raise LauncherError(
            f"cannot inspect completed systemd unit: {completed.stderr.decode(errors='replace')}"
        )
    properties: dict[str, str] = {}
    for line in completed.stdout.decode("utf-8", errors="strict").splitlines():
        if "=" not in line:
            raise LauncherError("malformed systemd property output")
        key, value = line.split("=", 1)
        if key in properties:
            raise LauncherError("duplicate systemd property")
        properties[key] = value
    if set(properties) != set(names):
        raise LauncherError("incomplete systemd property set")
    return properties


def _best_effort_stop_unit(unit: str) -> None:
    try:
        subprocess.run(
            ["/usr/bin/systemctl", "--user", "stop", f"{unit}.service"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=CLEAN_ENV,
            check=False,
        )
    except OSError:
        pass


def _stop_and_confirm_unit(unit: str) -> tuple[int, dict[str, str]]:
    service = f"{unit}.service"
    try:
        stopped = subprocess.run(
            ["/usr/bin/systemctl", "--user", "stop", service],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=CLEAN_ENV,
            check=False,
        )
    except OSError as exc:
        raise LauncherError(f"cannot stop completed systemd unit: {exc}") from exc
    if stopped.returncode:
        raise LauncherError(
            "cannot stop completed systemd unit: "
            f"return={stopped.returncode} "
            f"stdout={stopped.stdout!r} stderr={stopped.stderr!r}"
        )

    names = ("Id", "LoadState", "ActiveState", "SubState", "ControlGroup")
    poll_deadline = time.monotonic() + 10
    last_observation = "no post-stop observation"
    while True:
        try:
            observed = subprocess.run(
                [
                    "/usr/bin/systemctl",
                    "--user",
                    "show",
                    service,
                    *[f"--property={name}" for name in names],
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=CLEAN_ENV,
                check=False,
            )
        except OSError as exc:
            raise LauncherError(
                f"cannot inspect stopped systemd unit: {exc}"
            ) from exc
        if observed.returncode == 0:
            properties: dict[str, str] = {}
            try:
                decoded = observed.stdout.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise LauncherError(
                    f"invalid post-stop systemd property encoding: {exc}"
                ) from exc
            for line in decoded.splitlines():
                if "=" not in line:
                    raise LauncherError("malformed post-stop systemd property output")
                key, value = line.split("=", 1)
                if key in properties:
                    raise LauncherError("duplicate post-stop systemd property")
                properties[key] = value
            if set(properties) != set(names):
                raise LauncherError("incomplete post-stop systemd property set")
            last_observation = repr(properties)
            if (
                properties["Id"] == service
                and properties["LoadState"] in ("loaded", "not-found")
                and properties["ActiveState"] == "inactive"
                and properties["SubState"] == "dead"
                and properties["ControlGroup"] == ""
            ):
                return stopped.returncode, properties
        else:
            last_observation = (
                f"return={observed.returncode} "
                f"stdout={observed.stdout!r} stderr={observed.stderr!r}"
            )
        if time.monotonic() > poll_deadline:
            raise LauncherError(
                "systemd unit did not become inactive/dead with its transient "
                f"cgroup removed: {last_observation}"
            )
        time.sleep(0.05)


def _remove_and_confirm_capture_root(
    capture_root: Path, capture_stdout: Path, capture_stderr: Path
) -> None:
    try:
        capture_stdout.unlink()
        capture_stderr.unlink()
        capture_root.rmdir()
        _fsync_dir(capture_root.parent)
    except OSError as exc:
        raise LauncherError(f"cannot remove launcher capture root: {exc}") from exc
    if any(
        os.path.lexists(path)
        for path in (capture_stdout, capture_stderr, capture_root)
    ):
        raise LauncherError("launcher capture root still exists after removal")


def _release_lock_noexcept(lock_fd: int) -> None:
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
    except BaseException:
        pass
    try:
        os.close(lock_fd)
    except BaseException:
        pass


def launch(unit: str, scratch: Path) -> dict[str, Any]:
    if UNIT_RE.fullmatch(unit) is None:
        raise LauncherError("invalid D18-C unit name")
    if not scratch.is_absolute() or os.path.lexists(scratch):
        raise LauncherError("scratch must be a fresh absolute path")
    if scratch.parent.resolve(strict=True) != ALLOWED_PARENT.resolve(strict=True):
        raise LauncherError("scratch parent is not authorized")
    runtime_dir = Path(CLEAN_ENV["XDG_RUNTIME_DIR"])
    bus = runtime_dir / "bus"
    runtime_stat = runtime_dir.lstat()
    bus_stat = bus.lstat()
    if (
        not stat.S_ISDIR(runtime_stat.st_mode)
        or runtime_stat.st_uid != os.getuid()
        or stat.S_IMODE(runtime_stat.st_mode) & 0o077
        or not stat.S_ISSOCK(bus_stat.st_mode)
        or bus_stat.st_uid != os.getuid()
    ):
        raise LauncherError("user systemd runtime directory/bus custody drift")
    contract_check = subprocess.run(
        [sys.executable, "-I", "-B", str(CHECKER), "--mode", "contract"],
        cwd=HERE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=CLEAN_ENV,
        check=False,
    )
    if contract_check.returncode:
        raise LauncherError("frozen contract checker rejected launch")
    if len(contract_check.stdout) > MAX_CAPTURE_BYTES or contract_check.stderr:
        raise LauncherError("contract checker output envelope drift")

    capture_root = ALLOWED_PARENT / f".{unit}-capture"
    if os.path.lexists(capture_root):
        raise LauncherError("launcher capture root already exists")
    capture_root.mkdir(mode=0o700)
    capture_stdout = capture_root / "stdout"
    capture_stderr = capture_root / "stderr"
    command = [
        "/usr/bin/systemd-run",
        "--user",
        "--quiet",
        "--remain-after-exit",
        f"--unit={unit}",
        "--service-type=exec",
        "--property=MemoryAccounting=yes",
        f"--property=MemoryMax={MEMORY_MAX}",
        f"--property=MemoryHigh={MEMORY_HIGH}",
        f"--property=MemorySwapMax={MEMORY_SWAP_MAX}",
        "--property=OOMPolicy=stop",
        "--property=TimeoutStartSec=240s",
        "--property=RuntimeMaxSec=240s",
        "--property=TasksMax=64",
        f"--property=StandardOutput=file:{capture_stdout}",
        f"--property=StandardError=file:{capture_stderr}",
        "/usr/bin/env",
        "-i",
        f"HOME={CLEAN_ENV['HOME']}",
        f"PATH={CLEAN_ENV['PATH']}",
        f"LANG={CLEAN_ENV['LANG']}",
        f"LC_ALL={CLEAN_ENV['LC_ALL']}",
        "PYTHONDONTWRITEBYTECODE=1",
        sys.executable,
        "-I",
        "-B",
        str(RUNNER),
        "--contract",
        str(CONTRACT),
        "--scratch",
        str(scratch),
    ]
    try:
        launch_result = subprocess.run(
            command,
            cwd=HERE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=CLEAN_ENV,
            check=False,
        )
        if launch_result.returncode or launch_result.stdout or launch_result.stderr:
            raise LauncherError(
                "systemd-run launch failed: "
                f"return={launch_result.returncode} "
                f"stdout={launch_result.stdout!r} stderr={launch_result.stderr!r}"
            )
        poll_deadline = time.monotonic() + 245
        while True:
            properties = _systemd_properties(unit)
            if properties["SubState"] in ("exited", "failed", "dead"):
                break
            if time.monotonic() > poll_deadline:
                raise LauncherError("systemd runner did not reach terminal state")
            time.sleep(0.1)
        try:
            runner_stdout_bytes = capture_stdout.read_bytes()
            runner_stderr_bytes = capture_stderr.read_bytes()
        except OSError as exc:
            raise LauncherError(f"cannot read runner capture: {exc}") from exc
        if (
            len(runner_stdout_bytes) > MAX_CAPTURE_BYTES
            or len(runner_stderr_bytes) > MAX_CAPTURE_BYTES
        ):
            raise LauncherError("runner stdout/stderr capture cap exceeded")
        if (
            properties["Id"] != f"{unit}.service"
            or properties["Result"] != "success"
            or properties["ExecMainCode"] not in ("1", "exited")
            or properties["ExecMainStatus"] != "0"
            or properties["ActiveState"] != "active"
            or properties["SubState"] != "exited"
            or properties["ControlGroup"] != ""
        ):
            raise LauncherError(
                "runner/systemd terminal status failed: "
                f"properties={properties}"
            )
    except BaseException:
        _best_effort_stop_unit(unit)
        raise
    systemd_stop_return_code, post_stop_systemd_properties = (
        _stop_and_confirm_unit(unit)
    )
    try:
        runner_result = json.loads(
            runner_stdout_bytes.decode("utf-8", errors="strict"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                LauncherError(f"non-finite runner JSON: {value}")
            ),
            parse_float=lambda value: (_ for _ in ()).throw(
                LauncherError(f"floating-point runner JSON: {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LauncherError(f"invalid runner stdout JSON: {exc}") from exc
    if (
        not isinstance(runner_result, dict)
        or runner_result.get("verified") is not True
        or runner_result.get("status")
        != "VERIFIED_D18C_FRESH_EXCLUSIVE_PACKED_Q3_BOUNDED_4096_PREFLIGHT"
    ):
        raise LauncherError("runner did not return the verified D18-C outcome")
    resources = runner_result.get("resources")
    if (
        not isinstance(resources, dict)
        or not resources.get("cgroup_path", "").endswith(f"/{unit}.service")
    ):
        raise LauncherError("runner cgroup path is not bound to the launched unit")
    if runner_stderr_bytes:
        raise LauncherError("runner/systemd produced stderr")
    memory_peak = properties["MemoryPeak"]
    if not memory_peak.isdigit() or int(memory_peak) > 335_544_320:
        raise LauncherError("post-exit systemd MemoryPeak exceeds cap")

    _remove_and_confirm_capture_root(
        capture_root, capture_stdout, capture_stderr
    )

    lock_path = scratch / "exclusive.lock"
    try:
        lock_fd = os.open(lock_path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise LauncherError(f"cannot open scratch custody lock: {exc}") from exc
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        try:
            os.close(lock_fd)
        except OSError:
            pass
        raise LauncherError(f"cannot reacquire scratch custody: {exc}") from exc
    try:
        _verify_runner_scratch_identity(
            scratch, lock_fd, runner_result, "launcher_reacquire"
        )
        stdout_identity = _atomic_publish(
            scratch / "runner-stdout.json", runner_stdout_bytes
        )
        contract_stdout_identity = _atomic_publish(
            scratch / "contract-checker-stdout.json", contract_check.stdout
        )
        launcher_receipt = {
            "schema_version": 1,
            "contract_id": runner_result["contract_id"],
            "status": "VERIFIED_D18C_POST_EXIT_LAUNCHER_RECEIPT",
            "verified": True,
            "unit": unit,
            "command_sha256": _sha(
                b"\0".join(item.encode("utf-8") for item in command)
            ),
            "contract_checker_stdout": contract_stdout_identity,
            "runner_return_code": int(properties["ExecMainStatus"]),
            "runner_stdout": stdout_identity,
            "runner_stderr_bytes": len(runner_stderr_bytes),
            "runner_stderr_sha256": _sha(runner_stderr_bytes),
            "systemd_properties": properties,
            "systemd_stop_return_code": systemd_stop_return_code,
            "post_stop_systemd_properties": post_stop_systemd_properties,
            "post_exit_cgroup": {
                "runner_observed_path": resources["cgroup_path"],
                "pre_stop_control_group": properties["ControlGroup"],
                "post_stop_control_group": post_stop_systemd_properties[
                    "ControlGroup"
                ],
                "state": "ABSENT_AT_POST_EXIT_INSPECTION_AND_AFTER_STOP",
                "explanation": (
                    "systemd reported an empty ControlGroup in the post-exit "
                    "snapshot and again after the successful stop; the runner's "
                    "own cgroup path remains bound to the exact unit Id, but no "
                    "post-exit ControlGroup path is asserted"
                ),
            },
            "post_exit_memory_peak_bytes": int(memory_peak),
            "terminal_receipt": runner_result["terminal_receipt"],
            "observation_scope": (
                "after_runner_exit_runner_terminal_receipt_systemd_stop_and_"
                "capture_removal;"
                "before_launcher_receipt_publication"
            ),
        }
        launcher_payload = _canonical_json(launcher_receipt)
        launcher_path = scratch / "launcher-receipt.json"
        launcher_staging, launcher_identity = _prepare_final_publication(
            launcher_path, launcher_payload
        )
        final_result = {**runner_result, "launcher_receipt": launcher_identity}
        _verify_runner_scratch_identity(
            scratch, lock_fd, runner_result, "launcher_pre_publication"
        )
        _publish_prepared_final(launcher_path, launcher_staging)
    except BaseException:
        _release_lock_noexcept(lock_fd)
        raise
    _release_lock_noexcept(lock_fd)
    return final_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", required=True)
    parser.add_argument("--scratch", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = launch(args.unit, args.scratch)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "D18C_LAUNCHER_FAILED",
                    "verified": False,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, allow_nan=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
