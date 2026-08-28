#!/usr/bin/env python3
"""Installed-binary R9 durable-receipt restart acceptance harness.

The default mode is a read-only preflight.  The live exercise is intentionally
gated by one exact confirmation token and runs an exact-byte private copy of
the pinned binary in an isolated, disposable state root.  Its controlled
filesystem fault proves that a live body event can commit while ACK cleanup is
unavailable, then that restart classifies the preserved receipt as Duplicate
and removes it without changing the committed rows.

Only privacy-bounded JSON is written to stdout.  Raw MCP output, filesystem
paths, process identities, receipt identities, span identities, systemd unit
names, and cgroup nonces never enter the public packet.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import json
import math
import os
import pathlib
import queue
import re
import shutil
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from typing import Any, Callable, Iterable, Mapping, Sequence


SCHEMA = "agent_bridge.r9_installed_receipt_restart_acceptance.v1"
EXECUTION_CONFIRMATION = "r9-installed-receipt-restart-authorized"
CRASH_POINT = "crash_before_any_successful_ack"
LIVE_ACK_WARNING = "durable workload receipt committed but ACK cleanup failed"
STARTUP_RECONCILIATION_LOG = (
    "durable workload receipt startup reconciliation completed"
)
STANDIN_ATTEMPT_TOKEN = b"r9-standin-attempt-v1\n"
WORK_ROOT_PREFIX = "agent-bridge-r9-receipt-restart-"
MAX_BINARY_BYTES = 512 * 1024 * 1024
MAX_JSON_BYTES = 64 * 1024
MAX_PROTOCOL_LINE_BYTES = 1024 * 1024
MAX_PROTOCOL_STREAM_BYTES = 4 * 1024 * 1024
MAX_STDERR_LINE_BYTES = 256 * 1024
MAX_STDERR_STREAM_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 90
MIN_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 300
MAX_UNIX_SECONDS = 253_402_300_799
MAX_U32 = (1 << 32) - 1
MAX_U64 = (1 << 64) - 1
MIN_I64 = -(1 << 63)
MAX_I64 = (1 << 63) - 1
R9_LEDGER_SCHEMA_MARKER = b"agent_bridge.workload_receipt_commit.v1"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
RECEIPT_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
UUID_V4_PATTERN = (
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
SESSION_ID_RE = re.compile(rf"ses-{UUID_V4_PATTERN}\Z")
SPAN_ID_RE = re.compile(rf"agent-spawn-{UUID_V4_PATTERN}\Z")
UNIT_RE = re.compile(r"agent-bridge-agent-[0-9a-f]{32}\.scope\Z")
NONCE_RE = re.compile(r"[0-9a-f]{32}\Z")
PRIVATE_OUTPUT_FORBIDDEN_KEYS = frozenset(
    {
        "path",
        "binary_path",
        "work_root",
        "receipt_id",
        "span_id",
        "unit",
        "nonce",
        "pid",
        "session_id",
    }
)
MCP_ENV_KEYS = frozenset(
    {
        "HOME",
        "PATH",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "XDG_RUNTIME_DIR",
        "DBUS_SESSION_BUS_ADDRESS",
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_STATE_HOME",
        "AGENT_BRIDGE_DB",
        "AGENT_BRIDGE_STATE_DIR",
        "AGENT_BRIDGE_REPO",
        "AGENT_BRIDGE_BODY_TELEMETRY",
        "AGENT_BRIDGE_CGROUP_CUSTODY",
        "AGENT_BRIDGE_CGROUP_RUNTIME_MAX_SEC",
        "AGENT_BRIDGE_CGROUP_RECEIPT_DIR",
        "AGENT_BRIDGE_AGENT_RUNTIME",
        "AGENT_BRIDGE_CLAUDE_BIN",
        "AGENT_BRIDGE_EMBED_BACKEND",
        "AGENT_BRIDGE_DIM_GUARD_STRICT",
        "AGENT_BRIDGE_TOOLSET",
        "AGENT_BRIDGE_TOOL_PROFILE",
        "AGENT_BRIDGE_TERMINAL",
        "AGENT_BRIDGE_HEADLESS",
        "AGENT_BRIDGE_CLIENT",
        "AGENT_BRIDGE_MCP_SOURCE",
        "AGENT_BRIDGE_MAX_BLOCKING_THREADS",
        "AB_ALLOW_AGENT_SPAWN",
        "AB_ALLOW_SHELL_EXEC",
        "AB_ALLOW_TERMINAL_WRITE",
        "AB_ALLOW_BROWSER",
        "RUST_LOG",
        "NO_COLOR",
    }
)


class HarnessError(Exception):
    """Failure carrying only a fixed, privacy-safe public explanation."""

    def __init__(self, code: str, message: str, *, exit_code: int = 2) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.exit_code = exit_code


class ProbePending(Exception):
    """A bounded poll has not reached its expected state yet."""


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - argparse plumbing
        raise HarnessError("invalid_arguments", "command-line arguments were rejected")


class Deadline:
    def __init__(self, seconds: float) -> None:
        self._end = time.monotonic() + seconds

    def remaining(self) -> float:
        remaining = self._end - time.monotonic()
        if remaining <= 0:
            raise HarnessError("exercise_timeout", "the bounded exercise timed out")
        return remaining

    def sleep(self, seconds: float = 0.025) -> None:
        time.sleep(min(seconds, self.remaining()))


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def strict_json_loads(raw: bytes | str, *, maximum: int = MAX_JSON_BYTES) -> Any:
    if isinstance(raw, str):
        encoded = raw.encode("utf-8", "strict")
        text = raw
    else:
        encoded = raw
        text = raw.decode("utf-8", "strict")
    if len(encoded) > maximum:
        raise ValueError("JSON exceeds bound")
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=lambda _value: (_ for _ in ()).throw(
            ValueError("non-finite JSON number")
        ),
    )


def _sha256_fd(fd: int, *, maximum: int = MAX_BINARY_BYTES) -> tuple[str, int, bool]:
    digest = hashlib.sha256()
    total = 0
    marker_present = False
    overlap = b""
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > maximum:
            raise HarnessError("binary_too_large", "the pinned binary exceeds the size bound")
        digest.update(chunk)
        marker_window = overlap + chunk
        marker_present = marker_present or R9_LEDGER_SCHEMA_MARKER in marker_window
        overlap = marker_window[-(len(R9_LEDGER_SCHEMA_MARKER) - 1) :]
    return digest.hexdigest(), total, marker_present


def _physical_absolute_path(value: str) -> pathlib.Path:
    path = pathlib.Path(value)
    if not path.is_absolute():
        raise HarnessError("binary_not_absolute", "the binary path must be absolute")
    normalized = pathlib.Path(os.path.normpath(value))
    if str(normalized) != value or os.path.realpath(value) != value:
        raise HarnessError(
            "binary_not_physical",
            "the binary path must name a normalized physical file",
        )
    return path


def inspect_source_binary(path_value: str, expected_sha256: str) -> dict[str, Any]:
    """Read-only source inspection; owner/mode are observations, not trust gates."""

    if SHA256_RE.fullmatch(expected_sha256) is None:
        raise HarnessError(
            "invalid_expected_sha256",
            "expected SHA-256 must be 64 lowercase hexadecimal characters",
        )
    path = _physical_absolute_path(path_value)
    try:
        metadata = os.lstat(path)
    except OSError as error:
        raise HarnessError("binary_unavailable", "the pinned binary is unavailable") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise HarnessError(
            "binary_not_regular",
            "the binary must be a non-symlink regular file",
        )
    if metadata.st_size <= 0 or metadata.st_size > MAX_BINARY_BYTES:
        raise HarnessError("binary_size_invalid", "the pinned binary size is invalid")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise HarnessError("binary_unreadable", "the pinned binary cannot be read") from error
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise HarnessError("binary_not_regular", "the binary is not a regular file")
        digest, size, marker_present = _sha256_fd(fd)
    finally:
        os.close(fd)
    if (opened.st_dev, opened.st_ino, size) != (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
    ):
        raise HarnessError("binary_changed", "the pinned binary changed during inspection")
    if digest != expected_sha256:
        raise HarnessError("binary_digest_mismatch", "the pinned binary digest does not match")
    # This byte marker is only a fail-closed R9 readiness discriminator.  It
    # does not prove runtime behavior; the gated restart exercise does that.
    if not marker_present:
        raise HarnessError(
            "r9_schema_marker_missing",
            "the pinned binary does not contain the required R9 schema marker",
        )
    return {
        "path": path,
        "sha256": digest,
        "size": size,
        "dev": opened.st_dev,
        "ino": opened.st_ino,
        "mtime_ns": opened.st_mtime_ns,
        "owner_is_current_user": opened.st_uid == os.geteuid(),
        "group_or_other_writable": bool(opened.st_mode & 0o022),
        "owner_executable": bool(opened.st_mode & stat.S_IXUSR),
        "marker_present": True,
    }


def _inspect_private_runtime_directory(path: pathlib.Path) -> os.stat_result:
    if (
        not path.is_absolute()
        or pathlib.Path(os.path.normpath(str(path))) != path
        or os.path.realpath(path) != str(path)
    ):
        raise HarnessError(
            "runtime_directory_invalid", "the user runtime directory is not physical"
        )
    try:
        metadata = os.lstat(path)
    except OSError as error:
        raise HarnessError(
            "runtime_directory_unavailable", "the user runtime directory is unavailable"
        ) from error
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or metadata.st_mode & 0o077
    ):
        raise HarnessError(
            "runtime_directory_not_private",
            "the user runtime directory must be owner-bound and private",
        )
    return metadata


def _trusted_program(name: str) -> pathlib.Path:
    for directory in (pathlib.Path("/usr/bin"), pathlib.Path("/bin")):
        candidate = directory / name
        try:
            metadata = os.stat(candidate)
        except OSError:
            continue
        if stat.S_ISREG(metadata.st_mode) and os.access(candidate, os.X_OK):
            return candidate
    raise HarnessError("dependency_unavailable", "a required trusted host program is unavailable")


def build_preflight(binary: str, expected_sha256: str) -> dict[str, Any]:
    """Perform only read-only inspection.  No subprocess or temp path is created."""

    if sys.platform != "linux" or os.name != "posix":
        raise HarnessError("linux_required", "the R9 exercise requires Linux")
    source = inspect_source_binary(binary, expected_sha256)
    runtime_value = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.geteuid()}")
    runtime_dir = pathlib.Path(runtime_value)
    runtime_metadata = _inspect_private_runtime_directory(runtime_dir)
    bus_path = runtime_dir / "bus"
    try:
        bus_metadata = os.lstat(bus_path)
    except OSError as error:
        raise HarnessError(
            "systemd_user_bus_unavailable", "the systemd user bus is unavailable"
        ) from error
    if not stat.S_ISSOCK(bus_metadata.st_mode) or bus_metadata.st_uid != os.geteuid():
        raise HarnessError(
            "systemd_user_bus_invalid", "the systemd user bus endpoint is invalid"
        )
    controllers_path = pathlib.Path("/sys/fs/cgroup/cgroup.controllers")
    try:
        controllers = set(controllers_path.read_text(encoding="ascii").split())
    except (OSError, UnicodeError) as error:
        raise HarnessError(
            "cgroup_v2_unavailable", "the cgroup v2 controller surface is unavailable"
        ) from error
    if not {"cpu", "memory", "pids"}.issubset(controllers):
        raise HarnessError(
            "cgroup_controllers_incomplete",
            "cpu, memory, and pids cgroup controllers are required",
        )
    systemd_run = _trusted_program("systemd-run")
    systemctl = _trusted_program("systemctl")
    shell = pathlib.Path("/bin/sh")
    sleep = pathlib.Path("/bin/sleep")
    if not shell.exists() or not os.access(shell, os.X_OK):
        raise HarnessError("shell_unavailable", "the trusted POSIX shell is unavailable")
    if not sleep.exists() or not os.access(sleep, os.X_OK):
        raise HarnessError("sleep_unavailable", "the trusted sleep program is unavailable")
    try:
        available_bytes = os.statvfs(runtime_dir).f_bavail * os.statvfs(runtime_dir).f_frsize
    except OSError as error:
        raise HarnessError(
            "runtime_capacity_unavailable", "runtime filesystem capacity is unavailable"
        ) from error
    if available_bytes < source["size"] + 64 * 1024 * 1024:
        raise HarnessError(
            "runtime_capacity_insufficient", "runtime filesystem capacity is insufficient"
        )
    return {
        "source": source,
        "runtime_dir": runtime_dir,
        "runtime_dev": runtime_metadata.st_dev,
        "bus_path": bus_path,
        "systemd_run": systemd_run,
        "systemctl": systemctl,
        "shell": shell,
        "sleep": sleep,
        "public": {
            "ready": True,
            "linux": True,
            "source_physical_regular": True,
            "source_digest_matches": True,
            "source_owner_is_current_user": source["owner_is_current_user"],
            "source_group_or_other_writable": source["group_or_other_writable"],
            "source_owner_executable": source["owner_executable"],
            "source_owner_mode_used_as_trust_upgrade": False,
            "marker_present": True,
            "private_runtime_directory": True,
            "systemd_user_bus_present": True,
            "cgroup_v2_cpu_memory_pids_present": True,
            "trusted_systemd_tools_present": bool(systemd_run and systemctl),
            "trusted_posix_standin_present": True,
            "binary_sha256": source["sha256"],
        },
    }


def _mkdir_private(path: pathlib.Path) -> None:
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700, follow_symlinks=False)
    metadata = os.lstat(path)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise HarnessError("private_directory_failed", "a private trial directory was not secured")


def create_work_root(preflight: Mapping[str, Any]) -> pathlib.Path:
    runtime_dir = pathlib.Path(preflight["runtime_dir"])
    try:
        value = tempfile.mkdtemp(prefix=WORK_ROOT_PREFIX, dir=runtime_dir)
        root = pathlib.Path(value)
        os.chmod(root, 0o700, follow_symlinks=False)
    except OSError as error:
        raise HarnessError("work_root_failed", "the isolated trial root could not be created") from error
    metadata = os.lstat(root)
    if (
        root.parent != runtime_dir
        or not root.name.startswith(WORK_ROOT_PREFIX)
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_dev != preflight["runtime_dev"]
    ):
        raise HarnessError("work_root_invalid", "the isolated trial root failed validation")
    return root


def _sync_directory(path: pathlib.Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def copy_pinned_binary(
    source: pathlib.Path, destination: pathlib.Path, expected_sha256: str
) -> dict[str, Any]:
    source_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    destination_flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        source_fd = os.open(source, source_flags)
        destination_fd = os.open(destination, destination_flags, 0o600)
    except OSError as error:
        for fd_name in ("source_fd", "destination_fd"):
            fd = locals().get(fd_name)
            if isinstance(fd, int):
                os.close(fd)
        raise HarnessError("binary_copy_failed", "the private binary copy could not be created") from error
    digest = hashlib.sha256()
    total = 0
    try:
        source_metadata = os.fstat(source_fd)
        if not stat.S_ISREG(source_metadata.st_mode):
            raise HarnessError("binary_copy_source_invalid", "the binary copy source changed")
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BINARY_BYTES:
                raise HarnessError("binary_too_large", "the pinned binary exceeds the size bound")
            digest.update(chunk)
            view = memoryview(chunk)
            while view:
                written = os.write(destination_fd, view)
                view = view[written:]
        os.fsync(destination_fd)
        os.fchmod(destination_fd, 0o700)
        os.fsync(destination_fd)
        copied_metadata = os.fstat(destination_fd)
    finally:
        os.close(source_fd)
        os.close(destination_fd)
    if digest.hexdigest() != expected_sha256 or total != source_metadata.st_size:
        raise HarnessError("binary_copy_digest_mismatch", "the private binary copy is not exact")
    _sync_directory(destination.parent)
    post_source = inspect_source_binary(str(source), expected_sha256)
    if post_source["sha256"] != expected_sha256:
        raise HarnessError("binary_changed_after_copy", "the source binary changed during copy")
    fingerprint = {
        "dev": copied_metadata.st_dev,
        "ino": copied_metadata.st_ino,
        "size": copied_metadata.st_size,
        "mtime_ns": copied_metadata.st_mtime_ns,
        "sha256": expected_sha256,
    }
    validate_trial_binary(destination, expected_sha256, fingerprint)
    return fingerprint


def validate_trial_binary(
    path: pathlib.Path, expected_sha256: str, fingerprint: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    try:
        metadata = os.lstat(path)
    except OSError as error:
        raise HarnessError("trial_binary_unavailable", "the private binary copy is unavailable") from error
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise HarnessError("trial_binary_not_private", "the private binary copy is not owner-bound 0700")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        digest, size, marker_present = _sha256_fd(fd)
    finally:
        os.close(fd)
    observed = {
        "dev": opened.st_dev,
        "ino": opened.st_ino,
        "size": size,
        "mtime_ns": opened.st_mtime_ns,
        "sha256": digest,
    }
    if digest != expected_sha256 or size != metadata.st_size or not marker_present:
        raise HarnessError("trial_binary_digest_mismatch", "the private binary copy changed")
    if fingerprint is not None and any(observed[key] != fingerprint[key] for key in observed):
        raise HarnessError("trial_binary_fingerprint_changed", "the private binary copy changed")
    return observed


def build_isolated_environment(
    root: pathlib.Path, preflight: Mapping[str, Any], timeout_seconds: int
) -> dict[str, str]:
    """Build from constants only; ambient secrets are never inherited."""

    paths = {
        "home": root / "home",
        "tmp": root / "tmp",
        "data": root / "xdg-data",
        "config": root / "xdg-config",
        "cache": root / "xdg-cache",
        "state": root / "xdg-state",
        "workspace": root / "workspace",
        "spool": root / "spool",
    }
    for path in paths.values():
        _mkdir_private(path)
    env = {
        "HOME": str(paths["home"]),
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TMPDIR": str(paths["tmp"]),
        "XDG_RUNTIME_DIR": str(preflight["runtime_dir"]),
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={preflight['bus_path']}",
        "XDG_DATA_HOME": str(paths["data"]),
        "XDG_CONFIG_HOME": str(paths["config"]),
        "XDG_CACHE_HOME": str(paths["cache"]),
        "XDG_STATE_HOME": str(paths["state"]),
        "AGENT_BRIDGE_DB": str(root / "state.db"),
        "AGENT_BRIDGE_STATE_DIR": str(paths["state"]),
        "AGENT_BRIDGE_REPO": str(paths["workspace"]),
        "AGENT_BRIDGE_BODY_TELEMETRY": "1",
        "AGENT_BRIDGE_CGROUP_CUSTODY": "on",
        "AGENT_BRIDGE_CGROUP_RUNTIME_MAX_SEC": "60",
        "AGENT_BRIDGE_CGROUP_RECEIPT_DIR": str(paths["spool"]),
        "AGENT_BRIDGE_AGENT_RUNTIME": "claude-code",
        "AGENT_BRIDGE_CLAUDE_BIN": "/bin/sh",
        "AGENT_BRIDGE_EMBED_BACKEND": "hash",
        "AGENT_BRIDGE_DIM_GUARD_STRICT": "0",
        "AGENT_BRIDGE_TOOLSET": "profile",
        "AGENT_BRIDGE_TOOL_PROFILE": "all",
        "AGENT_BRIDGE_TERMINAL": "pty",
        "AGENT_BRIDGE_HEADLESS": "1",
        "AGENT_BRIDGE_CLIENT": "r9-installed-receipt-restart-harness",
        "AGENT_BRIDGE_MCP_SOURCE": "r9-installed-receipt-restart-harness",
        "AGENT_BRIDGE_MAX_BLOCKING_THREADS": "32",
        "AB_ALLOW_AGENT_SPAWN": "true",
        "AB_ALLOW_SHELL_EXEC": "false",
        "AB_ALLOW_TERMINAL_WRITE": "false",
        "AB_ALLOW_BROWSER": "false",
        "RUST_LOG": "info",
        "NO_COLOR": "1",
    }
    # Keep the accepted CLI bound visible to tests without introducing a
    # variable whose value depends on ambient state.
    if not (MIN_TIMEOUT_SECONDS <= timeout_seconds <= MAX_TIMEOUT_SECONDS):
        raise HarnessError("timeout_invalid", "the timeout is outside the accepted bound")
    if set(env) != MCP_ENV_KEYS:
        raise HarnessError("environment_allowlist_invalid", "the MCP environment allowlist was invalid")
    return env


def _write_private_file(path: pathlib.Path, payload: bytes, mode: int) -> None:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        fd = os.open(path, flags, mode)
    except FileExistsError:
        raise
    except OSError as error:
        raise HarnessError("private_file_failed", "a private trial file could not be created") from error
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fchmod(fd, mode)
        os.fsync(fd)
        metadata = os.fstat(fd)
    finally:
        os.close(fd)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != mode
        or metadata.st_size != len(payload)
    ):
        raise HarnessError("private_file_invalid", "a private trial file failed validation")
    _sync_directory(path.parent)


def create_standin_script(path: pathlib.Path) -> None:
    payload = b"""#!/bin/sh
set -eu
printf 'r9-standin-attempt-v1\\n' >> "$AB_R9_ATTEMPTS_FILE"
if [ "${AGENT_BRIDGE_WORKLOAD_RECEIPT_BINDING+x}" = x ]; then
    exit 90
fi
umask 077
if ! (set -C; printf 'started\\n' > "$AB_R9_STARTED_FILE") 2>/dev/null; then
    exit 91
fi
while [ ! -f "$AB_R9_RELEASE_FILE" ]; do
    /bin/sleep 0.05
done
exit 0
"""
    _write_private_file(path, payload, 0o700)


def create_release_marker(path: pathlib.Path) -> bool:
    try:
        _write_private_file(path, b"release\n", 0o600)
        return True
    except FileExistsError:
        return False


def _bounded_read_private_file(
    path: pathlib.Path,
    *,
    maximum: int,
    expected_mode: int,
    expected_kind: str = "regular",
) -> bytes:
    try:
        metadata = os.lstat(path)
    except OSError as error:
        raise HarnessError("private_file_unavailable", "a required private trial file is unavailable") from error
    kind_ok = stat.S_ISREG(metadata.st_mode) if expected_kind == "regular" else False
    if (
        not kind_ok
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != expected_mode
        or metadata.st_size > maximum
    ):
        raise HarnessError("private_file_invalid", "a required private trial file is invalid")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        payload = bytearray()
        while True:
            chunk = os.read(fd, min(64 * 1024, maximum + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > maximum:
                raise HarnessError("private_file_oversized", "a private trial file exceeds its bound")
    finally:
        os.close(fd)
    if (opened.st_dev, opened.st_ino, opened.st_size) != (
        metadata.st_dev,
        metadata.st_ino,
        len(payload),
    ):
        raise HarnessError("private_file_changed", "a private trial file changed during inspection")
    return bytes(payload)


class BoundedLinePump:
    """Drain one child pipe without retaining unbounded or oversized output."""

    def __init__(self, stream: Any, *, line_limit: int, total_limit: int) -> None:
        self._stream = stream
        self._line_limit = line_limit
        self._total_limit = total_limit
        self._condition = threading.Condition()
        self._lines: list[str] = []
        self._total = 0
        self._error: str | None = None
        self._eof = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            while True:
                raw = self._stream.readline(self._line_limit + 1)
                if not raw:
                    break
                oversized = len(raw) > self._line_limit
                if oversized and not raw.endswith(b"\n"):
                    while raw and not raw.endswith(b"\n"):
                        raw = self._stream.readline(self._line_limit + 1)
                with self._condition:
                    self._total += len(raw)
                    if oversized:
                        self._error = self._error or "line_limit_exceeded"
                    elif self._total > self._total_limit:
                        self._error = self._error or "stream_limit_exceeded"
                    else:
                        try:
                            line = raw.decode("utf-8", "strict").rstrip("\r\n")
                        except UnicodeDecodeError:
                            self._error = self._error or "invalid_utf8"
                        else:
                            self._lines.append(line)
                    self._condition.notify_all()
        except BaseException:
            with self._condition:
                self._error = self._error or "reader_failure"
                self._condition.notify_all()
        finally:
            with self._condition:
                self._eof = True
                self._condition.notify_all()

    def snapshot(self) -> tuple[list[str], bool, str | None]:
        with self._condition:
            return list(self._lines), self._eof, self._error

    def wait_for(
        self,
        predicate: Callable[[str], bool],
        deadline: Deadline,
        *,
        start_index: int = 0,
    ) -> str:
        while True:
            with self._condition:
                if self._error is not None:
                    raise HarnessError("child_output_invalid", "child output exceeded its safety contract")
                for line in self._lines[start_index:]:
                    if predicate(line):
                        return line
                if self._eof:
                    raise HarnessError("child_output_missing", "required child evidence was not observed")
                self._condition.wait(timeout=min(0.1, deadline.remaining()))

    def join(self, timeout: float = 2.0) -> None:
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise HarnessError("child_reader_stuck", "a bounded child output reader did not finish")
        try:
            self._stream.close()
        except OSError:
            pass
        _, _, error = self.snapshot()
        if error is not None:
            raise HarnessError("child_output_invalid", "child output exceeded its safety contract")


class McpClient:
    def __init__(
        self,
        binary: pathlib.Path,
        env: Mapping[str, str],
        expected_sha256: str,
        fingerprint: Mapping[str, Any],
        deadline: Deadline,
    ) -> None:
        validate_trial_binary(binary, expected_sha256, fingerprint)
        self.stdout: BoundedLinePump | None = None
        self.stderr: BoundedLinePump | None = None
        try:
            self.proc = subprocess.Popen(
                [str(binary), "mcp"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=dict(env),
                cwd=env["HOME"],
                close_fds=True,
                start_new_session=True,
                text=False,
                bufsize=0,
            )
        except OSError as error:
            raise HarnessError("mcp_start_failed", "the pinned MCP process could not start") from error
        assert self.proc.stdout is not None
        assert self.proc.stderr is not None
        self.stdout = BoundedLinePump(
            self.proc.stdout,
            line_limit=MAX_PROTOCOL_LINE_BYTES,
            total_limit=MAX_PROTOCOL_STREAM_BYTES,
        )
        self.stderr = BoundedLinePump(
            self.proc.stderr,
            line_limit=MAX_STDERR_LINE_BYTES,
            total_limit=MAX_STDERR_STREAM_BYTES,
        )
        self._next_id = 1
        self._stdout_cursor = 0
        try:
            self._initialize(deadline)
        except BaseException:
            self.force_kill()
            raise

    def _send(self, value: Mapping[str, Any]) -> None:
        if self.proc.stdin is None or self.proc.stdin.closed:
            raise HarnessError("mcp_stdin_closed", "the MCP request channel is closed")
        payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(payload) > MAX_JSON_BYTES:
            raise HarnessError("mcp_request_oversized", "an MCP request exceeded its bound")
        try:
            self.proc.stdin.write(payload)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise HarnessError("mcp_write_failed", "the MCP request could not be written") from error

    def _rpc(
        self, method: str, params: Mapping[str, Any] | None, deadline: Deadline
    ) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        request: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            request["params"] = dict(params)
        self._send(request)
        while True:
            if self.stdout is None:
                raise HarnessError("mcp_stdout_invalid", "the MCP stdout reader was unavailable")
            lines, eof, error = self.stdout.snapshot()
            if error is not None:
                raise HarnessError("mcp_stdout_invalid", "MCP stdout exceeded its protocol bound")
            while self._stdout_cursor < len(lines):
                line = lines[self._stdout_cursor]
                self._stdout_cursor += 1
                try:
                    message = strict_json_loads(line, maximum=MAX_PROTOCOL_LINE_BYTES)
                except (ValueError, UnicodeError, json.JSONDecodeError) as parse_error:
                    raise HarnessError("mcp_protocol_invalid", "MCP stdout was not strict JSON") from parse_error
                if not isinstance(message, dict):
                    raise HarnessError("mcp_protocol_invalid", "an MCP message was not an object")
                if message.get("id") != request_id:
                    continue
                if "error" in message:
                    raise HarnessError("mcp_rpc_error", "an MCP RPC returned an error")
                result = message.get("result")
                if not isinstance(result, dict):
                    raise HarnessError("mcp_result_invalid", "an MCP RPC result was invalid")
                return result
            if eof or self.proc.poll() is not None:
                raise HarnessError("mcp_exited_early", "the MCP process exited before responding")
            time.sleep(min(0.01, deadline.remaining()))

    def _initialize(self, deadline: Deadline) -> None:
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "r9-installed-receipt-restart-harness",
                    "version": "1",
                },
            },
            deadline,
        )
        server = result.get("serverInfo")
        if not isinstance(server, dict) or server.get("name") != "agent-bridge":
            raise HarnessError("mcp_identity_invalid", "the MCP server identity was unexpected")
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        tools_result = self._rpc("tools/list", {}, deadline)
        tools = tools_result.get("tools")
        names = {
            row.get("name")
            for row in tools
            if isinstance(tools, list) and isinstance(row, dict)
        } if isinstance(tools, list) else set()
        if not {"agent_spawn", "agent_session_wait"}.issubset(names):
            raise HarnessError("mcp_tools_missing", "required MCP tools were not exposed")

    def call_tool(self, name: str, arguments: Mapping[str, Any], deadline: Deadline) -> dict[str, Any]:
        result = self._rpc(
            "tools/call", {"name": name, "arguments": dict(arguments)}, deadline
        )
        if result.get("isError") is True:
            raise HarnessError("mcp_tool_error", "a required MCP tool returned an error")
        content = result.get("content")
        if not isinstance(content, list) or len(content) != 1:
            raise HarnessError("mcp_tool_result_invalid", "an MCP tool result was malformed")
        block = content[0]
        if not isinstance(block, dict) or block.get("type") != "text" or not isinstance(block.get("text"), str):
            raise HarnessError("mcp_tool_result_invalid", "an MCP tool result was malformed")
        try:
            payload = strict_json_loads(block["text"], maximum=MAX_PROTOCOL_LINE_BYTES)
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            raise HarnessError("mcp_tool_json_invalid", "an MCP tool returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise HarnessError("mcp_tool_json_invalid", "an MCP tool payload was not an object")
        return payload

    def wait_stderr(self, marker: str, deadline: Deadline) -> str:
        if self.stderr is None:
            raise HarnessError("mcp_stderr_invalid", "the MCP stderr reader was unavailable")
        return self.stderr.wait_for(lambda line: marker in line, deadline)

    def stderr_marker_count(self, marker: str) -> int:
        # Counts are acceptance evidence only after the child has exited and
        # the stderr pump has observed EOF. This avoids a first-match/drain
        # race that could otherwise make a duplicate line arrive later.
        if self.stderr is None:
            raise HarnessError("mcp_stderr_invalid", "the MCP stderr reader was unavailable")
        lines, eof, error = self.stderr.snapshot()
        if self.proc.poll() is None or not eof:
            raise HarnessError("mcp_stderr_not_drained", "the MCP stderr stream was not fully drained")
        if error is not None:
            raise HarnessError("child_output_invalid", "child output exceeded its safety contract")
        return sum(marker in line for line in lines)

    def kill_with_sigkill(self) -> None:
        if self.proc.poll() is not None:
            raise HarnessError("mcp1_not_live_at_crash", "the first MCP was not live at the crash point")
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
            status = self.proc.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise HarnessError("mcp1_sigkill_failed", "the first MCP could not be SIGKILLed") from error
        if status != -signal.SIGKILL:
            raise HarnessError("mcp1_sigkill_unverified", "the first MCP SIGKILL was not verified")
        self._close_pipes_and_join()

    def close_clean(self) -> None:
        if self.proc.stdin is not None and not self.proc.stdin.closed:
            self.proc.stdin.close()
        try:
            status = self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired as error:
            raise HarnessError("mcp2_eof_timeout", "the restarted MCP did not stop after EOF") from error
        if status != 0:
            raise HarnessError("mcp2_exit_invalid", "the restarted MCP exit status was not clean")
        self._close_pipes_and_join()

    def force_kill(self) -> None:
        if self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                self.proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if self.proc.stdin is not None and not self.proc.stdin.closed:
            try:
                self.proc.stdin.close()
            except OSError:
                pass
        if self.stdout is not None:
            try:
                self.stdout.join()
            except HarnessError:
                pass
        if self.stderr is not None:
            try:
                self.stderr.join()
            except HarnessError:
                pass

    def _close_pipes_and_join(self) -> None:
        if self.proc.stdin is not None and not self.proc.stdin.closed:
            try:
                self.proc.stdin.close()
            except OSError:
                pass
        if self.stdout is None or self.stderr is None:
            raise HarnessError("child_reader_missing", "a child output reader was unavailable")
        self.stdout.join()
        self.stderr.join()


def _validate_owner_private_entry(path: pathlib.Path, expected_mode: int) -> os.stat_result:
    try:
        metadata = os.lstat(path)
    except OSError as error:
        raise HarnessError("receipt_entry_unavailable", "the durable receipt entry is unavailable") from error
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != expected_mode
    ):
        raise HarnessError("receipt_entry_invalid", "the durable receipt entry is not private")
    return metadata


def find_and_validate_manifest(
    spool: pathlib.Path, expected_span_id: str
) -> tuple[pathlib.Path, dict[str, Any]]:
    try:
        names = sorted(os.listdir(spool))
    except OSError as error:
        raise HarnessError("spool_scan_failed", "the durable receipt spool could not be inspected") from error
    pending = [name for name in names if name.startswith("receipt-")]
    acknowledged = [name for name in names if name.startswith(".acked-")]
    unexpected = [name for name in names if name != ".spool.lock" and name not in pending]
    if len(pending) != 1 or acknowledged or unexpected:
        raise HarnessError("manifest_entry_count_invalid", "the durable receipt manifest entry was not unique")
    receipt_id = pending[0][len("receipt-") :]
    if RECEIPT_ID_RE.fullmatch(receipt_id) is None:
        raise HarnessError("receipt_identity_invalid", "the durable receipt identity was malformed")
    entry = spool / pending[0]
    _validate_owner_private_entry(entry, 0o700)
    raw = _bounded_read_private_file(
        entry / "manifest.json", maximum=MAX_JSON_BYTES, expected_mode=0o600
    )
    try:
        manifest = strict_json_loads(raw)
    except (ValueError, UnicodeError, json.JSONDecodeError) as error:
        raise HarnessError("manifest_json_invalid", "the durable receipt manifest was invalid") from error
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema",
        "receipt_id",
        "span_id",
        "runtime",
        "unit",
        "nonce",
    }:
        raise HarnessError("manifest_shape_invalid", "the durable receipt manifest shape was invalid")
    if (
        manifest["schema"] != 2
        or manifest["receipt_id"] != receipt_id
        or manifest["span_id"] != expected_span_id
        or manifest["runtime"] != "claude-code"
        or not isinstance(manifest["unit"], str)
        or UNIT_RE.fullmatch(manifest["unit"]) is None
        or not isinstance(manifest["nonce"], str)
        or NONCE_RE.fullmatch(manifest["nonce"]) is None
    ):
        raise HarnessError("manifest_binding_invalid", "the durable receipt manifest binding was invalid")
    if (entry / "receipt.json").exists():
        raise HarnessError("receipt_sealed_before_release", "the workload receipt sealed before release")
    lock = entry / "producer.lock"
    lock_metadata = os.lstat(lock)
    if (
        not stat.S_ISREG(lock_metadata.st_mode)
        or stat.S_ISLNK(lock_metadata.st_mode)
        or lock_metadata.st_uid != os.geteuid()
        or stat.S_IMODE(lock_metadata.st_mode) != 0o600
        or lock_metadata.st_size != 0
    ):
        raise HarnessError("producer_lock_invalid", "the durable producer lock was invalid")
    return entry, manifest


def set_spool_mode(spool: pathlib.Path, mode: int) -> None:
    try:
        before = os.lstat(spool)
        if not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(before.st_mode):
            raise OSError(errno.ENOTDIR, "not a physical directory")
        os.chmod(spool, mode, follow_symlinks=False)
        after = os.lstat(spool)
    except OSError as error:
        raise HarnessError("spool_mode_change_failed", "the isolated spool mode could not be changed") from error
    if (
        after.st_uid != os.geteuid()
        or after.st_dev != before.st_dev
        or after.st_ino != before.st_ino
        or stat.S_IMODE(after.st_mode) != mode
    ):
        raise HarnessError("spool_mode_unverified", "the isolated spool mode change was not verified")


def wait_for_marker(path: pathlib.Path, deadline: Deadline) -> None:
    while True:
        try:
            payload = _bounded_read_private_file(
                path, maximum=64, expected_mode=0o600
            )
        except HarnessError as error:
            if error.code not in {"private_file_unavailable", "private_file_changed"}:
                raise
        else:
            if payload == b"":
                deadline.sleep()
                continue
            if payload != b"started\n":
                raise HarnessError("standin_marker_invalid", "the stand-in start marker was invalid")
            return
        deadline.sleep()


def validate_standin_execution(attempts: pathlib.Path, marker: pathlib.Path) -> None:
    attempt_payload = _bounded_read_private_file(
        attempts, maximum=256, expected_mode=0o600
    )
    marker_payload = _bounded_read_private_file(
        marker, maximum=64, expected_mode=0o600
    )
    if attempt_payload != STANDIN_ATTEMPT_TOKEN or marker_payload != b"started\n":
        raise HarnessError(
            "standin_repeat_invalid", "the stand-in execution count was invalid"
        )


RECEIPT_KEYS = frozenset(
    {"schema", "receipt_id", "span_id", "nonce", "unit", "resources"}
)
RAW_WORKLOAD_REQUIRED_KEYS = frozenset(
    {
        "status",
        "source",
        "scope",
        "controllers",
        "cpu_usage_usec",
        "cpu_user_usec",
        "cpu_system_usec",
        "memory_peak_bytes",
        "populated_zero_observed",
        "start_before_exec",
        "complete_for_cpu_memory_workload_tree",
        "complete_for_pids_workload_tree",
        "generation_count",
        "captured_generation_count",
    }
)
RAW_WORKLOAD_OPTIONAL_KEYS = frozenset(
    {"pids_peak", "oom_events", "oom_kill_events", "incomplete_reasons"}
)
TASK_RESOURCE_SPAN_KEYS = frozenset(
    {
        "schema_version",
        "span_id",
        "task_kind",
        "state",
        "started_at_unix_ms",
        "ended_at_unix_ms",
        "duration_ms",
        "checkpoint_count",
        "sampling_gaps",
        "before_pressure",
        "after_pressure",
        "memory_available_delta_bytes",
        "storage_available_delta_bytes",
        "process_resident_delta_bytes",
        "task_process_scope",
        "task_process_capture_complete",
        "task_process_count_before",
        "task_process_count_after",
        "task_process_resident_delta_bytes",
        "task_process_sampling_gaps",
        "task_process_binding_status",
        "task_process_binding_reason",
        "task_process_baseline_phase",
        "task_process_whole_task_prefix_covered",
        "task_process_terminal_status",
        "task_process_endpoint_semantics",
        "task_terminal_resources",
        "task_workload_resources",
        "abandonment_reason",
    }
)
TASK_TERMINAL_RESOURCE_KEYS = frozenset(
    {
        "schema_version",
        "accounting_status",
        "source",
        "scope",
        "descendant_coverage",
        "workload_lifetime_covered",
        "spawned_attempt_count",
        "captured_attempt_count",
        "known_user_cpu_us",
        "known_system_cpu_us",
        "known_peak_resident_bytes",
        "complete_for_spawned_attempts",
        "complete_for_workload_tree",
        "terminal_condition",
        "peak_resident_semantics",
    }
)
TASK_WORKLOAD_RESOURCE_KEYS = frozenset(
    {
        "schema_version",
        "accounting_status",
        "source",
        "scope",
        "controllers",
        "workload_lifetime_covered",
        "generation_count",
        "captured_generation_count",
        "known_total_cpu_us",
        "known_user_cpu_us",
        "known_system_cpu_us",
        "known_peak_memory_bytes",
        "known_peak_pids",
        "known_oom_event_count",
        "known_oom_kill_count",
        "start_before_exec",
        "final_populated_zero",
        "complete_for_cpu_memory_workload_tree",
        "complete_for_pids_workload_tree",
        "durable_receipts",
        "io_accounting_status",
        "terminal_condition",
        "failure_reason",
        "trust_boundary",
    }
)
DURABLE_RECEIPT_REF_KEYS = frozenset({"receipt_id", "sha256"})
SCHEDULING_FACT_KEYS = frozenset(
    {"schema_version", "session_id", "runtime_id", "span_id", "advice"}
)
SCHEDULING_ADVICE_KEYS = frozenset(
    {
        "schema_version",
        "mode",
        "read_only",
        "blocked",
        "execution_changed",
        "changes_routing",
        "changes_parallelism",
        "pressure",
        "workload_class",
        "requested_parallelism",
        "suggested_max_parallelism",
        "recommendation",
    }
)
DESCRIPTOR_KEYS = frozenset({"object", "affordance"})
DESCRIPTOR_OBJECT_KEYS = frozenset(
    {"object_type", "source_adapter", "label", "object_id"}
)
DESCRIPTOR_AFFORDANCE_KEYS = frozenset(
    {"action_type", "risk_level", "requires_gate", "expected_effect"}
)


def _is_strict_int(
    value: Any, *, minimum: int = MIN_I64, maximum: int = MAX_I64
) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _is_optional_strict_int(
    value: Any, *, minimum: int = MIN_I64, maximum: int = MAX_I64
) -> bool:
    return value is None or _is_strict_int(value, minimum=minimum, maximum=maximum)


def _typed_json_equal(value: Any, expected: Any) -> bool:
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(value) == set(expected) and all(
            _typed_json_equal(value[key], child) for key, child in expected.items()
        )
    if isinstance(expected, list):
        return len(value) == len(expected) and all(
            _typed_json_equal(child, expected_child)
            for child, expected_child in zip(value, expected, strict=True)
        )
    return value == expected


def _normalized_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
    return (
        any(token in normalized for token in ("prompt", "command", "transcript"))
        or "path" in normalized
        or "nonce" in normalized
        or normalized in {"args", "arguments", "cwd", "unit", "pid", "pgid", "pidfd"}
        or normalized.endswith("pid")
        or normalized.endswith("unit")
    )


def _assert_no_sensitive_keys(value: Any, code: str) -> None:
    if isinstance(value, dict):
        if any(not isinstance(key, str) or _normalized_sensitive_key(key) for key in value):
            raise HarnessError(code, "committed evidence contained a private field")
        for child in value.values():
            _assert_no_sensitive_keys(child, code)
    elif isinstance(value, list):
        for child in value:
            _assert_no_sensitive_keys(child, code)


def _validate_raw_workload_resources(resources: Any) -> dict[str, Any]:
    if not isinstance(resources, dict):
        raise HarnessError("receipt_schema_invalid", "the terminal workload receipt schema was invalid")
    keys = set(resources)
    if (
        not RAW_WORKLOAD_REQUIRED_KEYS.issubset(keys)
        or not keys.issubset(RAW_WORKLOAD_REQUIRED_KEYS | RAW_WORKLOAD_OPTIONAL_KEYS)
    ):
        raise HarnessError("receipt_resources_shape_invalid", "the workload receipt resource shape was invalid")
    controllers = resources["controllers"]
    counters = (
        "cpu_usage_usec",
        "cpu_user_usec",
        "cpu_system_usec",
        "memory_peak_bytes",
    )
    optional_counters = ("pids_peak", "oom_events", "oom_kill_events")
    reasons = resources.get("incomplete_reasons", [])
    if (
        resources["status"] != "complete"
        or resources["source"] != "linux_cgroup_v2_systemd_delegated_scope"
        or resources["scope"] != "delegated_session_workload_tree"
        or type(controllers) is not list
        or any(type(controller) is not str for controller in controllers)
        or controllers != sorted(set(controllers))
        or not set(controllers).issubset({"cpu", "memory", "pids"})
        or not {"cpu", "memory"}.issubset(set(controllers))
        or any(
            not _is_strict_int(resources[key], minimum=0, maximum=MAX_U64)
            for key in counters
        )
        or any(
            key in resources
            and not _is_strict_int(resources[key], minimum=0, maximum=MAX_U64)
            for key in optional_counters
        )
        or resources["populated_zero_observed"] is not True
        or resources["start_before_exec"] is not True
        or resources["complete_for_cpu_memory_workload_tree"] is not True
        or type(resources["complete_for_pids_workload_tree"]) is not bool
        or not _is_strict_int(resources["generation_count"], minimum=1, maximum=MAX_U32)
        or not _is_strict_int(resources["captured_generation_count"], minimum=1, maximum=MAX_U32)
        or resources["generation_count"] != 1
        or resources["captured_generation_count"] != 1
        or type(reasons) is not list
        or len(reasons) > 32
        or any(type(reason) is not str or not reason or len(reason) > 256 for reason in reasons)
    ):
        raise HarnessError("receipt_resources_incomplete", "the workload receipt was not complete")
    pids_complete = "pids" in controllers and "pids_peak" in resources
    expected_reasons = (
        ["pids controller was not delegated"]
        if "pids" not in controllers
        else (["pids.peak terminal counter is unavailable"] if "pids_peak" not in resources else [])
    )
    if (
        resources["complete_for_pids_workload_tree"] is not pids_complete
        or reasons != expected_reasons
    ):
        raise HarnessError("receipt_resources_incomplete", "the workload receipt was not complete")
    return resources


def validate_terminal_workload_receipt(
    receipt: Any, manifest: Mapping[str, Any]
) -> dict[str, Any]:
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_KEYS:
        raise HarnessError("receipt_shape_invalid", "the terminal workload receipt shape was invalid")
    if any(receipt.get(key) != manifest[key] for key in ("receipt_id", "span_id", "nonce", "unit")):
        raise HarnessError("receipt_binding_invalid", "the terminal workload receipt binding was invalid")
    if not _is_strict_int(receipt["schema"], minimum=2, maximum=2):
        raise HarnessError("receipt_schema_invalid", "the terminal workload receipt schema was invalid")
    return _validate_raw_workload_resources(receipt["resources"])


def wait_for_receipt(
    entry: pathlib.Path, manifest: Mapping[str, Any], deadline: Deadline
) -> tuple[dict[str, Any], str]:
    receipt_path = entry / "receipt.json"
    while True:
        try:
            raw = _bounded_read_private_file(
                receipt_path, maximum=MAX_JSON_BYTES, expected_mode=0o600
            )
        except HarnessError as error:
            if error.code != "private_file_unavailable":
                raise
            deadline.sleep()
            continue
        try:
            receipt = strict_json_loads(raw)
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            raise HarnessError("receipt_json_invalid", "the terminal workload receipt was invalid") from error
        validate_terminal_workload_receipt(receipt, manifest)
        return receipt, "sha256:" + hashlib.sha256(raw).hexdigest()


LEDGER_COLUMNS = (
    "schema_version",
    "receipt_id",
    "span_id",
    "recorded_at",
    "receipt_sha256",
    "commit_kind",
    "redacted_facts_json",
    "record_sha256",
)
EVENT_COLUMNS = (
    "id",
    "ts",
    "actor",
    "source",
    "action",
    "target",
    "verdict_status",
    "verdict_method",
    "evidence",
    "facts",
    "descriptor",
)


def _sqlite_uri(path: pathlib.Path) -> str:
    return "file:" + urllib.parse.quote(str(path), safe="/") + "?mode=ro"


def read_database_snapshot(path: pathlib.Path) -> dict[str, tuple[tuple[Any, ...], ...]]:
    try:
        connection = sqlite3.connect(
            _sqlite_uri(path), uri=True, timeout=0.2, isolation_level=None
        )
    except sqlite3.Error as error:
        raise ProbePending from error
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA busy_timeout=200")
        # Pin schema inspection and both tables to one SQLite read snapshot.
        connection.execute("BEGIN")
        quick = connection.execute("PRAGMA quick_check").fetchall()
        if quick != [("ok",)]:
            raise HarnessError("database_integrity_failed", "the isolated SQLite store failed quick_check")
        ledger_shape = tuple(
            row[1]
            for row in connection.execute("PRAGMA table_info('workload_receipt_commits')")
        )
        event_shape = tuple(
            row[1] for row in connection.execute("PRAGMA table_info('semantic_events')")
        )
        if ledger_shape != LEDGER_COLUMNS or event_shape != EVENT_COLUMNS:
            raise HarnessError("database_schema_invalid", "the isolated receipt/event schema was unexpected")
        ledger_query = (
            "SELECT " + ",".join(LEDGER_COLUMNS) + " FROM workload_receipt_commits ORDER BY receipt_id"
        )
        event_query = (
            "SELECT " + ",".join(EVENT_COLUMNS) + " FROM semantic_events ORDER BY id"
        )
        return {
            "ledger": tuple(connection.execute(ledger_query).fetchall()),
            "events": tuple(connection.execute(event_query).fetchall()),
        }
    except sqlite3.OperationalError as error:
        if "locked" in str(error).lower() or "busy" in str(error).lower():
            raise ProbePending from error
        raise HarnessError("database_read_failed", "the isolated SQLite store could not be read") from error
    except sqlite3.Error as error:
        raise HarnessError("database_read_failed", "the isolated SQLite store could not be read") from error
    finally:
        connection.close()


def _row(columns: Sequence[str], values: Sequence[Any]) -> dict[str, Any]:
    return dict(zip(columns, values, strict=True))


def _strict_json_field(value: Any, code: str) -> Any:
    if not isinstance(value, str):
        raise HarnessError(code, "a committed JSON evidence field was invalid")
    try:
        return strict_json_loads(value, maximum=MAX_PROTOCOL_LINE_BYTES)
    except (ValueError, UnicodeError, json.JSONDecodeError) as error:
        raise HarnessError(code, "a committed JSON evidence field was invalid") from error


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise HarnessError("canonical_json_failed", "committed JSON could not be canonicalized") from error


def _expected_workload_usage(
    resources: Mapping[str, Any], manifest: Mapping[str, Any], receipt_sha256: str
) -> dict[str, Any]:
    reasons = resources.get("incomplete_reasons", [])
    return {
        "schema_version": "agent_bridge.task_workload_resources.v1",
        "accounting_status": resources["status"],
        "source": resources["source"],
        "scope": resources["scope"],
        "controllers": resources["controllers"],
        "workload_lifetime_covered": resources["populated_zero_observed"],
        "generation_count": resources["generation_count"],
        "captured_generation_count": resources["captured_generation_count"],
        "known_total_cpu_us": resources.get("cpu_usage_usec"),
        "known_user_cpu_us": resources.get("cpu_user_usec"),
        "known_system_cpu_us": resources.get("cpu_system_usec"),
        "known_peak_memory_bytes": resources.get("memory_peak_bytes"),
        "known_peak_pids": resources.get("pids_peak"),
        "known_oom_event_count": resources.get("oom_events"),
        "known_oom_kill_count": resources.get("oom_kill_events"),
        "start_before_exec": resources["start_before_exec"],
        "final_populated_zero": resources["populated_zero_observed"],
        "complete_for_cpu_memory_workload_tree": resources[
            "complete_for_cpu_memory_workload_tree"
        ],
        "complete_for_pids_workload_tree": resources[
            "complete_for_pids_workload_tree"
        ],
        "durable_receipts": [
            {"receipt_id": manifest["receipt_id"], "sha256": receipt_sha256}
        ],
        "io_accounting_status": "unknown_not_delegated",
        "terminal_condition": "all_generations_populated_zero",
        "failure_reason": "; ".join(reasons) if reasons else None,
        "trust_boundary": "same_uid_non_adversarial_cgroup_membership",
    }


def _validate_task_terminal_resources(
    value: Any, resources: Mapping[str, Any]
) -> None:
    if not isinstance(value, dict) or set(value) != TASK_TERMINAL_RESOURCE_KEYS:
        raise HarnessError(
            "live_terminal_resources_shape_invalid",
            "terminal child resource facts had an unexpected shape",
        )
    _assert_no_sensitive_keys(value, "live_terminal_resources_private")
    if (
        value["schema_version"] != "agent_bridge.task_terminal_resources.v0"
        or value["accounting_status"] != "complete"
        or value["source"] != "linux_raw_waitid_wnowait_rusage"
        or value["scope"] != "waited_child_generations"
        or value["descendant_coverage"] != "not_proven"
        or value["workload_lifetime_covered"] is not False
        or not _is_strict_int(value["spawned_attempt_count"], minimum=1, maximum=MAX_U32)
        or not _is_strict_int(value["captured_attempt_count"], minimum=1, maximum=MAX_U32)
        or value["spawned_attempt_count"] != resources["generation_count"]
        or value["captured_attempt_count"] != resources["captured_generation_count"]
        or any(
            not _is_strict_int(value[key], minimum=0, maximum=MAX_U64)
            for key in (
                "known_user_cpu_us",
                "known_system_cpu_us",
                "known_peak_resident_bytes",
            )
        )
        or value["complete_for_spawned_attempts"] is not True
        or value["complete_for_workload_tree"] is not False
        or value["terminal_condition"]
        != "all_spawned_children_observed_before_reap"
        or value["peak_resident_semantics"]
        != "max_ru_maxrss_across_attempts_not_concurrent_tree_peak"
    ):
        raise HarnessError(
            "live_terminal_resources_invalid",
            "terminal child resource facts were invalid",
        )


def _validate_task_workload_resources(
    value: Any,
    resources: Mapping[str, Any],
    manifest: Mapping[str, Any],
    receipt_sha256: str,
) -> None:
    if not isinstance(value, dict) or set(value) != TASK_WORKLOAD_RESOURCE_KEYS:
        raise HarnessError(
            "live_workload_facts_shape_invalid",
            "live workload accounting facts had an unexpected shape",
        )
    _assert_no_sensitive_keys(value, "live_workload_facts_private")
    expected = _expected_workload_usage(resources, manifest, receipt_sha256)
    durable = value["durable_receipts"]
    if (
        type(durable) is not list
        or len(durable) != 1
        or not isinstance(durable[0], dict)
        or set(durable[0]) != DURABLE_RECEIPT_REF_KEYS
        or not isinstance(durable[0].get("receipt_id"), str)
        or RECEIPT_ID_RE.fullmatch(durable[0].get("receipt_id", "")) is None
        or not isinstance(durable[0].get("sha256"), str)
        or not durable[0]["sha256"].startswith("sha256:")
        or SHA256_RE.fullmatch(durable[0]["sha256"][7:]) is None
        or not _typed_json_equal(value, expected)
    ):
        raise HarnessError(
            "live_workload_facts_invalid", "live workload accounting facts were invalid"
        )


def _validate_task_resource_span_facts(
    facts: Any,
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
    receipt_sha256: str,
) -> None:
    if not isinstance(facts, dict) or set(facts) != TASK_RESOURCE_SPAN_KEYS:
        raise HarnessError(
            "live_ledger_facts_shape_invalid", "the live workload ledger facts shape was invalid"
        )
    _assert_no_sensitive_keys(facts, "live_ledger_facts_private")
    started = facts["started_at_unix_ms"]
    ended = facts["ended_at_unix_ms"]
    duration = facts["duration_ms"]
    pressure_values = {"unknown", "nominal", "elevated", "high", "critical"}
    signed_deltas = (
        "memory_available_delta_bytes",
        "storage_available_delta_bytes",
        "process_resident_delta_bytes",
    )
    if (
        facts["schema_version"] != "agent_bridge.task_resource_span.v4"
        or facts["span_id"] != manifest["span_id"]
        or facts["task_kind"] != "agent_spawn"
        or facts["state"] != "closed"
        or not _is_strict_int(started, minimum=0, maximum=MAX_UNIX_SECONDS * 1000)
        or not _is_strict_int(ended, minimum=0, maximum=MAX_UNIX_SECONDS * 1000)
        or not _is_strict_int(duration, minimum=0, maximum=MAX_I64)
        or ended < started
        or duration != ended - started
        or not _is_strict_int(facts["checkpoint_count"], minimum=0, maximum=8)
        or facts["checkpoint_count"] != 0
        or not _is_strict_int(facts["sampling_gaps"], minimum=0, maximum=MAX_U32)
        or facts["sampling_gaps"] != 0
        or type(facts["before_pressure"]) is not str
        or facts["before_pressure"] not in pressure_values
        or type(facts["after_pressure"]) is not str
        or facts["after_pressure"] not in pressure_values
        or any(not _is_optional_strict_int(facts[key]) for key in signed_deltas)
        or facts["task_process_scope"]
        != "best_effort_linux_same_user_process_tree"
        or facts["task_process_capture_complete"] is not False
        or not _is_strict_int(
            facts["task_process_count_before"], minimum=1, maximum=MAX_U32
        )
        or facts["task_process_count_after"] is not None
        or facts["task_process_resident_delta_bytes"] is not None
        or not _is_strict_int(
            facts["task_process_sampling_gaps"], minimum=1, maximum=MAX_U32
        )
        or facts["task_process_sampling_gaps"] != 1
        or facts["task_process_binding_status"] != "attached"
        or facts["task_process_binding_reason"] is not None
        or facts["task_process_baseline_phase"] != "post_spawn"
        or facts["task_process_whole_task_prefix_covered"] is not False
        or facts["task_process_terminal_status"] != "root_unavailable"
        or facts["task_process_endpoint_semantics"]
        != "procfs_sample_attempt_at_finish"
        or facts["abandonment_reason"] is not None
    ):
        raise HarnessError(
            "live_ledger_facts_invalid", "the live workload ledger facts were invalid"
        )
    resources = validate_terminal_workload_receipt(receipt, manifest)
    _validate_task_terminal_resources(facts["task_terminal_resources"], resources)
    _validate_task_workload_resources(
        facts["task_workload_resources"], resources, manifest, receipt_sha256
    )


def _expected_descriptor(
    *, object_type: str, label: str, object_id: str, expected_effect: str
) -> dict[str, Any]:
    return {
        "object": {
            "object_type": object_type,
            "source_adapter": "body_telemetry",
            "label": label,
            "object_id": object_id,
        },
        "affordance": {
            "action_type": "observe",
            "risk_level": "low",
            "requires_gate": False,
            "expected_effect": expected_effect,
        },
    }


def _validate_descriptor(value: Any, expected: Mapping[str, Any], code: str) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != DESCRIPTOR_KEYS
        or not isinstance(value.get("object"), dict)
        or set(value["object"]) != DESCRIPTOR_OBJECT_KEYS
        or not isinstance(value.get("affordance"), dict)
        or set(value["affordance"]) != DESCRIPTOR_AFFORDANCE_KEYS
        or not _typed_json_equal(value, expected)
    ):
        raise HarnessError(code, "a body event descriptor was invalid")
    _assert_no_sensitive_keys(value, code)


def _validate_scheduling_event(
    event: Mapping[str, Any], manifest: Mapping[str, Any], session_id: str
) -> None:
    evidence = _strict_json_field(
        event["evidence"], "scheduling_event_evidence_invalid"
    )
    facts = _strict_json_field(event["facts"], "scheduling_event_facts_invalid")
    descriptor = _strict_json_field(
        event["descriptor"], "scheduling_event_descriptor_invalid"
    )
    if (
        event["actor"] != "mcp"
        or event["source"] != "body_telemetry"
        or event["action"] != "scheduling_advice_observed"
        or event["target"] != manifest["span_id"]
        or event["verdict_status"] != "unknown"
        or event["verdict_method"] != "shadow_advice_has_no_causal_outcome_claim"
        or not _typed_json_equal(
            evidence,
            {
                "advice_computed": True,
                "causal_quality_evaluable": False,
                "execution_changed": False,
            },
        )
        or not isinstance(facts, dict)
        or set(facts) != SCHEDULING_FACT_KEYS
        or facts["schema_version"] != "agent_bridge.body_scheduling_advice.v0"
        or facts["session_id"] != session_id
        or facts["runtime_id"] != "claude-code"
        or facts["span_id"] != manifest["span_id"]
        or not isinstance(facts["advice"], dict)
        or set(facts["advice"]) != SCHEDULING_ADVICE_KEYS
    ):
        raise HarnessError("scheduling_event_invalid", "the body scheduling event was invalid")
    _assert_no_sensitive_keys(evidence, "scheduling_event_private")
    _assert_no_sensitive_keys(facts, "scheduling_event_private")
    advice = facts["advice"]
    pressure = advice["pressure"]
    recommendations = {
        "unknown": "observe_only",
        "nominal": "start_as_requested",
        "elevated": "prefer_single_heavy_task",
        "high": "defer_optional_heavy_work",
        "critical": "request_operator_review_before_heavy_work",
    }
    if type(pressure) is not str or pressure not in recommendations:
        raise HarnessError("scheduling_advice_invalid", "the scheduling advice was invalid")
    expected_advice = {
        "schema_version": "agent_bridge.body_scheduling_advice.v0",
        "mode": "shadow_only",
        "read_only": True,
        "blocked": False,
        "execution_changed": False,
        "changes_routing": False,
        "changes_parallelism": False,
        "pressure": pressure,
        "workload_class": "heavy",
        "requested_parallelism": 1,
        "suggested_max_parallelism": 1,
        "recommendation": recommendations[pressure],
    }
    if not _typed_json_equal(advice, expected_advice):
        raise HarnessError("scheduling_advice_invalid", "the scheduling advice was invalid")
    _validate_descriptor(
        descriptor,
        _expected_descriptor(
            object_type="body_scheduling_advice",
            label="heavy",
            object_id=manifest["span_id"],
            expected_effect=(
                "record a compact shadow scheduling recommendation for later evaluation"
            ),
        ),
        "scheduling_event_descriptor_invalid",
    )


def _validate_terminal_event(
    event: Mapping[str, Any], facts: Mapping[str, Any], manifest: Mapping[str, Any]
) -> None:
    evidence = _strict_json_field(event["evidence"], "live_event_evidence_invalid")
    event_facts = _strict_json_field(event["facts"], "live_event_facts_invalid")
    descriptor = _strict_json_field(
        event["descriptor"], "live_event_descriptor_invalid"
    )
    expected_evidence = {
        "before_present": True,
        "after_present": True,
        "checkpoint_count": facts["checkpoint_count"],
        "sampling_gaps": facts["sampling_gaps"],
        "workload_cpu_memory_tree_complete": True,
        "durable_receipt_count": 1,
        "durable_commit_required": True,
    }
    if (
        event["actor"] != "mcp"
        or event["source"] != "body_telemetry"
        or event["action"] != "task_span_closed"
        or event["target"] != manifest["span_id"]
        or event["verdict_status"] != "verified"
        or event["verdict_method"]
        != "before_after_body_observation_with_delegated_cpu_memory_workload_tree"
        or not _typed_json_equal(evidence, expected_evidence)
        or not _typed_json_equal(event_facts, facts)
    ):
        raise HarnessError("live_event_invalid", "the live body event projection was invalid")
    _assert_no_sensitive_keys(evidence, "live_event_private")
    _assert_no_sensitive_keys(event_facts, "live_event_private")
    _validate_descriptor(
        descriptor,
        _expected_descriptor(
            object_type="task_resource_span",
            label="agent_spawn",
            object_id=manifest["span_id"],
            expected_effect="record a bounded task resource-span receipt",
        ),
        "live_event_descriptor_invalid",
    )


def validate_live_commit_snapshot(
    snapshot: Mapping[str, Sequence[Sequence[Any]]],
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
    receipt_sha256: str,
    session_id: str,
) -> None:
    ledger_rows = snapshot["ledger"]
    event_rows = snapshot["events"]
    if not ledger_rows:
        raise ProbePending
    if len(ledger_rows) != 1:
        raise HarnessError("live_ledger_count_invalid", "the live workload ledger row count was invalid")
    ledger = _row(LEDGER_COLUMNS, ledger_rows[0])
    if (
        ledger["schema_version"] != "agent_bridge.workload_receipt_commit.v1"
        or ledger["receipt_id"] != manifest["receipt_id"]
        or ledger["span_id"] != manifest["span_id"]
        or ledger["receipt_sha256"] != receipt_sha256
        or ledger["commit_kind"] != "live_body_span"
        or not _is_strict_int(
            ledger["recorded_at"], minimum=0, maximum=MAX_UNIX_SECONDS
        )
        or not isinstance(ledger["record_sha256"], str)
        or not ledger["record_sha256"].startswith("sha256:")
        or SHA256_RE.fullmatch(ledger["record_sha256"][7:]) is None
    ):
        raise HarnessError("live_ledger_invalid", "the live workload ledger row was invalid")
    facts = _strict_json_field(ledger["redacted_facts_json"], "live_ledger_facts_invalid")
    if (
        not isinstance(facts, dict)
        or _canonical_json(facts) != ledger["redacted_facts_json"]
    ):
        raise HarnessError("live_ledger_facts_invalid", "the live workload ledger facts were invalid")
    _validate_task_resource_span_facts(facts, manifest, receipt, receipt_sha256)
    record_claim = {
        "schema_version": ledger["schema_version"],
        "receipt_id": ledger["receipt_id"],
        "span_id": ledger["span_id"],
        "recorded_at": ledger["recorded_at"],
        "receipt_sha256": ledger["receipt_sha256"],
        "commit_kind": ledger["commit_kind"],
        "redacted_facts": facts,
    }
    expected_record_sha256 = "sha256:" + hashlib.sha256(
        _canonical_json(record_claim).encode("utf-8")
    ).hexdigest()
    if ledger["record_sha256"] != expected_record_sha256:
        raise HarnessError("live_ledger_record_digest_invalid", "the live ledger record digest was invalid")
    events = [_row(EVENT_COLUMNS, values) for values in event_rows]
    if len(events) < 2:
        raise ProbePending
    if len(events) != 2:
        raise HarnessError("live_event_count_invalid", "the live body event row count was invalid")
    for event in events:
        if (
            not _is_strict_int(event["id"], minimum=1, maximum=MAX_I64)
            or not _is_strict_int(event["ts"], minimum=0, maximum=MAX_UNIX_SECONDS)
        ):
            raise HarnessError("live_event_identity_invalid", "a live body event identity was invalid")
    target_events = [event for event in events if event["target"] == manifest["span_id"]]
    actions = [event["action"] for event in target_events]
    if sorted(actions) != ["scheduling_advice_observed", "task_span_closed"]:
        raise HarnessError("live_event_actions_invalid", "the live body event actions were invalid")
    terminal = next(event for event in target_events if event["action"] == "task_span_closed")
    scheduling = next(
        event for event in target_events if event["action"] == "scheduling_advice_observed"
    )
    _validate_scheduling_event(scheduling, manifest, session_id)
    _validate_terminal_event(terminal, facts, manifest)
    if (
        terminal["ts"] != ledger["recorded_at"]
        or scheduling["ts"] > terminal["ts"]
        or scheduling["id"] >= terminal["id"]
    ):
        raise HarnessError("live_event_order_invalid", "the live body event order was invalid")
    if any(event["action"] == "workload_receipt_reconciled" for event in events):
        raise HarnessError("unexpected_reconciliation_event", "a reconstruction event appeared before restart")


def wait_for_live_commit(
    database: pathlib.Path,
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
    receipt_sha256: str,
    session_id: str,
    deadline: Deadline,
) -> dict[str, tuple[tuple[Any, ...], ...]]:
    while True:
        try:
            snapshot = read_database_snapshot(database)
            validate_live_commit_snapshot(
                snapshot, manifest, receipt, receipt_sha256, session_id
            )
            return snapshot
        except ProbePending:
            deadline.sleep()


def assert_producer_lock_released(entry: pathlib.Path) -> None:
    lock_path = entry / "producer.lock"
    flags = os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(lock_path, flags)
    except OSError as error:
        raise HarnessError("producer_lock_open_failed", "the producer lock could not be inspected") from error
    try:
        metadata = os.fstat(fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_size != 0
        ):
            raise HarnessError("producer_lock_invalid", "the producer lock was invalid")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise HarnessError("producer_lock_still_held", "the producer lock was still held") from error
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        os.close(fd)


def assert_pending_spool(spool: pathlib.Path, manifest: Mapping[str, Any]) -> None:
    names = sorted(os.listdir(spool))
    expected = sorted([".spool.lock", f"receipt-{manifest['receipt_id']}"])
    if names != expected:
        raise HarnessError("pending_spool_invalid", "the pre-restart durable spool state was invalid")


def _validate_spool_root_metadata(
    metadata: os.stat_result, expected_fingerprint: tuple[int, int] | None
) -> None:
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or (
            expected_fingerprint is not None
            and (metadata.st_dev, metadata.st_ino) != expected_fingerprint
        )
    ):
        raise HarnessError("spool_root_invalid", "the durable spool root was invalid")


def capture_spool_fingerprint(spool: pathlib.Path) -> tuple[int, int]:
    try:
        metadata = os.lstat(spool)
    except OSError as error:
        raise HarnessError("spool_root_unavailable", "the durable spool root was unavailable") from error
    _validate_spool_root_metadata(metadata, None)
    return metadata.st_dev, metadata.st_ino


def assert_residual_spool_empty(
    spool: pathlib.Path, expected_fingerprint: tuple[int, int]
) -> None:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        path_metadata = os.lstat(spool)
        _validate_spool_root_metadata(path_metadata, expected_fingerprint)
        directory_fd = os.open(spool, flags)
    except OSError as error:
        raise HarnessError("spool_root_unavailable", "the durable spool root was unavailable") from error
    try:
        opened = os.fstat(directory_fd)
        _validate_spool_root_metadata(opened, expected_fingerprint)
        if (opened.st_dev, opened.st_ino) != (
            path_metadata.st_dev,
            path_metadata.st_ino,
        ):
            raise HarnessError("spool_root_changed", "the durable spool root identity changed")
        names = sorted(os.listdir(directory_fd))
        if names != [".spool.lock"]:
            raise HarnessError("residual_receipt_present", "durable receipt residue remained after restart")
        lock_metadata = os.stat(
            ".spool.lock", dir_fd=directory_fd, follow_symlinks=False
        )
        lock_fd = os.open(
            ".spool.lock",
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_fd,
        )
        try:
            opened_lock = os.fstat(lock_fd)
        finally:
            os.close(lock_fd)
    except OSError as error:
        raise HarnessError("spool_final_inspection_failed", "the durable spool final state was unavailable") from error
    finally:
        os.close(directory_fd)
    if (
        not stat.S_ISREG(lock_metadata.st_mode)
        or stat.S_ISLNK(lock_metadata.st_mode)
        or lock_metadata.st_uid != os.geteuid()
        or stat.S_IMODE(lock_metadata.st_mode) != 0o600
        or lock_metadata.st_size != 0
        or (opened_lock.st_dev, opened_lock.st_ino, opened_lock.st_size)
        != (lock_metadata.st_dev, lock_metadata.st_ino, lock_metadata.st_size)
    ):
        raise HarnessError("spool_lock_invalid", "the durable spool lock was invalid")


def _parse_unique_log_counter(line: str, field: str) -> int | None:
    matches = re.findall(
        rf"(?<!\S){re.escape(field)}=(\d+)(?=\s|$)", line
    )
    return int(matches[0]) if len(matches) == 1 else None


def validate_duplicate_reconciliation_log(line: str) -> None:
    expected = {
        "scanned": 1,
        "inserted": 0,
        "duplicate": 1,
        "conflicts": 0,
        "acknowledged": 1,
        "already_acknowledged": 0,
        "acknowledgement_failures": 0,
        "unresolved": 0,
        "active_producers": 0,
        "invalid": 0,
        "commit_failures": 0,
    }
    if any(
        _parse_unique_log_counter(line, key) != value
        for key, value in expected.items()
    ):
        raise HarnessError("startup_duplicate_log_invalid", "startup Duplicate evidence was invalid")


def _run_systemctl(
    systemctl: pathlib.Path,
    env: Mapping[str, str],
    args: Sequence[str],
    timeout: float,
) -> subprocess.CompletedProcess[bytes]:
    try:
        completed = subprocess.run(
            [str(systemctl), "--user", *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(env),
            close_fds=True,
            start_new_session=True,
            timeout=max(0.1, min(5.0, timeout)),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise HarnessError("systemctl_failed", "the exact trial scope could not be inspected") from error
    if len(completed.stdout) > 4096 or len(completed.stderr) > 4096:
        raise HarnessError("systemctl_output_invalid", "systemctl output exceeded its bound")
    return completed


def capture_matching_scope_baseline(
    systemctl: pathlib.Path, env: Mapping[str, str], deadline: Deadline
) -> frozenset[str]:
    """Capture every pre-spawn matching user scope with a strict bounded parser."""

    completed = _run_systemctl(
        systemctl,
        env,
        [
            "list-units",
            "--all",
            "--type=scope",
            "--plain",
            "--no-legend",
            "--no-pager",
            "--",
            "agent-bridge-agent-*.scope",
        ],
        deadline.remaining(),
    )
    if completed.returncode != 0:
        raise HarnessError("scope_baseline_failed", "the pre-spawn scope baseline was unavailable")
    try:
        text = completed.stdout.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise HarnessError("scope_baseline_invalid", "the pre-spawn scope baseline was invalid") from error
    units: set[str] = set()
    lines = text.splitlines()
    if len(lines) > 128:
        raise HarnessError("scope_baseline_oversized", "the pre-spawn scope baseline exceeded its bound")
    for line in lines:
        if not line or len(line.encode("utf-8")) > 512 or line != line.strip():
            raise HarnessError("scope_baseline_invalid", "the pre-spawn scope baseline was invalid")
        fields = line.split()
        if fields and fields[0] == "●":
            fields = fields[1:]
        if len(fields) < 4:
            raise HarnessError("scope_baseline_invalid", "the pre-spawn scope baseline was invalid")
        unit, load_state, active_state, sub_state = fields[:4]
        if (
            UNIT_RE.fullmatch(unit) is None
            or load_state
            not in {"stub", "loaded", "not-found", "bad-setting", "error", "merged", "masked"}
            or re.fullmatch(r"[a-z][a-z-]{1,31}", active_state) is None
            or re.fullmatch(r"[a-z][a-z-]{1,31}", sub_state) is None
            or unit in units
        ):
            raise HarnessError("scope_baseline_invalid", "the pre-spawn scope baseline was invalid")
        units.add(unit)
    return frozenset(units)


def scope_load_state(
    systemctl: pathlib.Path, env: Mapping[str, str], unit: str, deadline: Deadline
) -> str:
    if UNIT_RE.fullmatch(unit) is None:
        raise HarnessError("scope_identity_invalid", "the exact trial scope identity was invalid")
    completed = _run_systemctl(
        systemctl,
        env,
        ["show", "--property=LoadState", "--value", "--", unit],
        deadline.remaining(),
    )
    try:
        value = completed.stdout.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as error:
        raise HarnessError("scope_state_invalid", "the exact trial scope state was invalid") from error
    if completed.returncode != 0 or value not in {
        "loaded",
        "stub",
        "not-found",
        "bad-setting",
        "error",
        "merged",
        "masked",
    }:
        raise HarnessError("scope_state_invalid", "the exact trial scope state was invalid")
    return value


def claim_cleanup_scope(
    unit: str, baseline: frozenset[str], observed_load_state: str
) -> str:
    """Issue cleanup authority only for this spawn's new, observed-loaded scope."""

    if UNIT_RE.fullmatch(unit) is None:
        raise HarnessError("scope_identity_invalid", "the exact trial scope identity was invalid")
    if unit in baseline:
        raise HarnessError("scope_preexisting", "the manifest scope existed before the trial spawn")
    if observed_load_state != "loaded":
        raise HarnessError("scope_not_loaded", "the manifest scope was not observed loaded after spawn")
    return unit


def exact_scope_absent(
    systemctl: pathlib.Path, env: Mapping[str, str], unit: str, deadline: Deadline
) -> None:
    while True:
        if scope_load_state(systemctl, env, unit, deadline) == "not-found":
            return
        deadline.sleep(0.05)


def _stop_exact_scope(
    systemctl: pathlib.Path,
    env: Mapping[str, str],
    unit: str,
    cleanup_owned_unit: str | None,
    deadline: Deadline,
) -> bool:
    # The string itself is not authority. Only the claim minted from the
    # pre-spawn baseline + post-spawn loaded observation permits a stop.
    if UNIT_RE.fullmatch(unit) is None or cleanup_owned_unit != unit:
        return True
    try:
        if scope_load_state(systemctl, env, unit, deadline) == "not-found":
            return True
        completed = _run_systemctl(
            systemctl, env, ["stop", "--", unit], deadline.remaining()
        )
        if completed.returncode != 0:
            return False
        exact_scope_absent(systemctl, env, unit, deadline)
    except HarnessError:
        return False
    return True


def _wait_for_initial_empty_snapshot(
    database: pathlib.Path, deadline: Deadline
) -> dict[str, tuple[tuple[Any, ...], ...]]:
    while True:
        try:
            snapshot = read_database_snapshot(database)
        except ProbePending:
            deadline.sleep()
            continue
        if snapshot["ledger"] or snapshot["events"]:
            raise HarnessError("isolated_store_not_empty", "the isolated store was not initially empty")
        return snapshot


def _validate_spawn_payload(payload: Mapping[str, Any]) -> tuple[str, str]:
    session_id = payload.get("id")
    runtime_id = payload.get("runtime_id")
    body = payload.get("body_task_span")
    if (
        not isinstance(session_id, str)
        or SESSION_ID_RE.fullmatch(session_id) is None
        or runtime_id != "claude-code"
        or not isinstance(body, dict)
        or body.get("state") != "active"
        or body.get("completion") != "agent_session_wait"
        or body.get("automatic_completion") != "session_terminal_observer"
        or payload.get("body_scheduling_event_recorded") is not True
    ):
        raise HarnessError("spawn_binding_invalid", "the automatic body-span spawn binding was invalid")
    span_id = body.get("span_id")
    binding = body.get("process_binding")
    if (
        not isinstance(span_id, str)
        or SPAN_ID_RE.fullmatch(span_id) is None
        or not isinstance(binding, dict)
        or binding.get("status") != "attached"
        or binding.get("scope") != "local_workload_root"
    ):
        raise HarnessError("spawn_custody_invalid", "the delegated body-span custody binding was invalid")
    return session_id, span_id


def _validate_wait_payload(payload: Mapping[str, Any]) -> None:
    if payload.get("timed_out") is not False:
        raise HarnessError("session_wait_timed_out", "the stand-in workload did not finish in time")
    session = payload.get("session")
    if not isinstance(session, dict) or session.get("runtime_id") != "claude-code":
        raise HarnessError("session_wait_invalid", "the terminal agent session row was invalid")
    exit_code = session.get("exit_code")
    if not _is_strict_int(exit_code, minimum=0, maximum=0):
        raise HarnessError("standin_exit_invalid", "the deterministic stand-in did not exit cleanly")


def cleanup_work_root(
    root: pathlib.Path,
    preflight: Mapping[str, Any],
    spool: pathlib.Path | None,
    release: pathlib.Path | None,
    clients: Iterable[McpClient],
    env: Mapping[str, str] | None,
    manifest_unit: str | None,
    cleanup_owned_unit: str | None,
    scope_baseline: frozenset[str] | None,
    scope_absence_proven: bool,
) -> bool:
    ok = True
    if spool is not None:
        try:
            if os.path.lexists(spool):
                set_spool_mode(spool, 0o700)
        except HarnessError:
            ok = False
    if release is not None:
        try:
            if not os.path.lexists(release):
                create_release_marker(release)
        except (HarnessError, OSError):
            ok = False
    for client in clients:
        try:
            client.force_kill()
        except BaseException:
            ok = False
    scope_cleanup_safe = True
    if env is not None and scope_baseline is not None and not scope_absence_proven:
        cleanup_deadline = Deadline(10)
        systemctl = pathlib.Path(preflight["systemctl"])
        if manifest_unit is not None:
            scope_cleanup_safe = _stop_exact_scope(
                systemctl,
                env,
                manifest_unit,
                cleanup_owned_unit,
                cleanup_deadline,
            )
        try:
            remaining = capture_matching_scope_baseline(
                systemctl, env, cleanup_deadline
            )
        except HarnessError:
            scope_cleanup_safe = False
        else:
            # Unknown post-baseline units are never stopped: they may belong
            # to a concurrent actor.  Holding the trial root is safer than
            # claiming cleanup while a trial-created scope could remain.
            if not remaining.issubset(scope_baseline):
                scope_cleanup_safe = False
    if not scope_cleanup_safe:
        return False
    try:
        metadata = os.lstat(root)
        if (
            root.parent != preflight["runtime_dir"]
            or not root.name.startswith(WORK_ROOT_PREFIX)
            or not stat.S_ISDIR(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or metadata.st_dev != preflight["runtime_dev"]
        ):
            return False
        shutil.rmtree(root)
        if os.path.lexists(root):
            return False
    except FileNotFoundError:
        pass
    except OSError:
        ok = False
    return ok


def execute_acceptance(
    preflight: Mapping[str, Any], expected_sha256: str, timeout_seconds: int
) -> dict[str, Any]:
    deadline = Deadline(timeout_seconds)
    root = create_work_root(preflight)
    spool: pathlib.Path | None = None
    release: pathlib.Path | None = None
    env: dict[str, str] | None = None
    unit: str | None = None
    cleanup_owned_unit: str | None = None
    scope_baseline: frozenset[str] | None = None
    scope_absence_proven = False
    clients: list[McpClient] = []
    primary_error: BaseException | None = None
    report: dict[str, Any] | None = None
    try:
        binary = root / "agent-bridge.real"
        fingerprint = copy_pinned_binary(
            pathlib.Path(preflight["source"]["path"]), binary, expected_sha256
        )
        env = build_isolated_environment(root, preflight, timeout_seconds)
        spool = pathlib.Path(env["AGENT_BRIDGE_CGROUP_RECEIPT_DIR"])
        spool_fingerprint = capture_spool_fingerprint(spool)
        database = pathlib.Path(env["AGENT_BRIDGE_DB"])
        workspace = pathlib.Path(env["AGENT_BRIDGE_REPO"])
        standin = root / "standin.sh"
        started = root / "standin.started"
        attempts = root / "standin.attempts"
        release = root / "standin.release"
        _write_private_file(attempts, b"", 0o600)
        create_standin_script(standin)

        mcp1 = McpClient(binary, env, expected_sha256, fingerprint, deadline)
        clients.append(mcp1)
        _wait_for_initial_empty_snapshot(database, deadline)
        scope_baseline = capture_matching_scope_baseline(
            pathlib.Path(preflight["systemctl"]), env, deadline
        )
        spawn = mcp1.call_tool(
            "agent_spawn",
            {
                "cwd": str(workspace),
                "prompt": str(standin),
                "backend": "claude-code",
                "interactive": False,
                "env": {
                    "AB_R9_ATTEMPTS_FILE": str(attempts),
                    "AB_R9_STARTED_FILE": str(started),
                    "AB_R9_RELEASE_FILE": str(release),
                },
            },
            deadline,
        )
        session_id, span_id = _validate_spawn_payload(spawn)
        wait_for_marker(started, deadline)
        entry, manifest = find_and_validate_manifest(spool, span_id)
        unit = manifest["unit"]
        cleanup_owned_unit = claim_cleanup_scope(
            unit,
            scope_baseline,
            scope_load_state(
                pathlib.Path(preflight["systemctl"]), env, unit, deadline
            ),
        )

        # The workload is still blocked.  0500 preserves traversal into its
        # already-created 0700 entry while the root's required 0700 invariant
        # makes every live ACK cleanup attempt fail closed.
        set_spool_mode(spool, 0o500)
        create_release_marker(release)
        waited = mcp1.call_tool(
            "agent_session_wait",
            {
                "id": session_id,
                "timeout_secs": max(1, min(60, math.ceil(deadline.remaining()))),
            },
            deadline,
        )
        _validate_wait_payload(waited)
        receipt, receipt_sha256 = wait_for_receipt(entry, manifest, deadline)
        before_restart = wait_for_live_commit(
            database,
            manifest,
            receipt,
            receipt_sha256,
            session_id,
            deadline,
        )
        mcp1.wait_stderr(LIVE_ACK_WARNING, deadline)
        assert_pending_spool(spool, manifest)
        assert_producer_lock_released(entry)

        # This is deliberately described at the protocol-observable boundary:
        # Store is committed, no ACK has succeeded, and the pending receipt is
        # still present.  It makes no instruction-level claim about calls.
        mcp1.kill_with_sigkill()
        if mcp1.stderr_marker_count(LIVE_ACK_WARNING) != 1:
            raise HarnessError("live_ack_warning_count_invalid", "live ACK failure evidence was not unique")
        set_spool_mode(spool, 0o700)
        validate_trial_binary(binary, expected_sha256, fingerprint)

        mcp2 = McpClient(binary, env, expected_sha256, fingerprint, deadline)
        clients.append(mcp2)
        startup_line = mcp2.wait_stderr(STARTUP_RECONCILIATION_LOG, deadline)
        validate_duplicate_reconciliation_log(startup_line)
        mcp2.close_clean()
        if mcp2.stderr_marker_count(STARTUP_RECONCILIATION_LOG) != 1:
            raise HarnessError("startup_log_count_invalid", "startup Duplicate evidence was not unique")

        # EOF and stderr drain are part of the restart barrier.  Only now is
        # the Store read considered final: shutdown work cannot add or rewrite
        # a receipt projection after this comparison.
        after_restart = read_database_snapshot(database)
        validate_live_commit_snapshot(
            after_restart, manifest, receipt, receipt_sha256, session_id
        )
        if before_restart != after_restart:
            raise HarnessError("restart_rows_changed", "ledger or semantic-event rows changed on restart")
        after_events = [_row(EVENT_COLUMNS, values) for values in after_restart["events"]]
        if any(event["action"] == "workload_receipt_reconciled" for event in after_events):
            raise HarnessError("reconstructed_event_present", "restart reconstructed a semantic event")
        assert_residual_spool_empty(spool, spool_fingerprint)
        validate_standin_execution(attempts, started)
        exact_scope_absent(
            pathlib.Path(preflight["systemctl"]), env, unit, deadline
        )
        scope_absence_proven = True
        # Absence is now proven; revoke stop authority so a hypothetical later
        # same-name unit can never be targeted during ordinary final cleanup.
        cleanup_owned_unit = None
        validate_trial_binary(binary, expected_sha256, fingerprint)
        inspect_source_binary(str(preflight["source"]["path"]), expected_sha256)
        report = {
            "private_exact_byte_copy_verified": True,
            "body_telemetry_channel_verified": True,
            "delegated_cgroup_receipt_verified": True,
            "store_commit_before_ack_cleanup_failure_verified": True,
            "crash_point": CRASH_POINT,
            "mcp1_sigkill_verified": True,
            "startup_duplicate_count": 1,
            "ledger_rows_before_restart": len(before_restart["ledger"]),
            "ledger_rows_after_restart": len(after_restart["ledger"]),
            "semantic_event_rows_before_restart": len(before_restart["events"]),
            "semantic_event_rows_after_restart": len(after_restart["events"]),
            "rows_unchanged_across_restart": True,
            "workload_reconciled_event_count": 0,
            "pending_receipts_before_restart": 1,
            "residual_receipt_entries_after_restart": 0,
            "producer_lock_released_before_crash": True,
            "exact_scope_absent_after_restart": True,
            "standin_execution_count": 1,
        }
    except BaseException as error:
        primary_error = error
    cleanup_ok = cleanup_work_root(
        root,
        preflight,
        spool,
        release,
        reversed(clients),
        env,
        unit,
        cleanup_owned_unit,
        scope_baseline,
        scope_absence_proven,
    )
    if not cleanup_ok:
        raise HarnessError("cleanup_incomplete", "the isolated trial cleanup was incomplete")
    if primary_error is not None:
        raise primary_error
    assert report is not None
    return report


def _packet_has_forbidden_keys(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key in PRIVATE_OUTPUT_FORBIDDEN_KEYS
            or _packet_has_forbidden_keys(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_packet_has_forbidden_keys(child) for child in value)
    return False


def public_packet(
    *,
    verdict: str,
    executed: bool,
    preflight: Mapping[str, Any] | None = None,
    acceptance: Mapping[str, Any] | None = None,
    error: HarnessError | None = None,
) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "schema": SCHEMA,
        "verdict": verdict,
        "executed": executed,
    }
    if preflight is not None:
        packet["preflight"] = dict(preflight)
    if acceptance is not None:
        packet["acceptance"] = dict(acceptance)
    if error is not None:
        packet["error"] = {"code": error.code, "message": error.safe_message}
    if _packet_has_forbidden_keys(packet):
        raise HarnessError("privacy_boundary_failed", "the public packet failed its privacy boundary")
    return packet


def build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--binary")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--execute-r9-installed-restart")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument("--help", action="store_true")
    return parser


def run(argv: Sequence[str]) -> tuple[int, dict[str, Any]]:
    execution_requested = False
    try:
        args = build_parser().parse_args(list(argv))
        if args.help:
            return 0, {
                "schema": SCHEMA,
                "verdict": "USAGE",
                "executed": False,
                "required": ["--binary", "--expected-sha256"],
                "optional_live_gate": {
                    "argument": "--execute-r9-installed-restart",
                    "exact_value": EXECUTION_CONFIRMATION,
                },
                "default_mode": "read_only_preflight",
            }
        if args.binary is None or args.expected_sha256 is None:
            raise HarnessError("missing_required_arguments", "binary and expected SHA-256 are required")
        if not (MIN_TIMEOUT_SECONDS <= args.timeout_seconds <= MAX_TIMEOUT_SECONDS):
            raise HarnessError("timeout_invalid", "the timeout is outside the accepted bound")
        preflight = build_preflight(args.binary, args.expected_sha256)
        if args.execute_r9_installed_restart is None:
            return 0, public_packet(
                verdict="PREFLIGHT_READY",
                executed=False,
                preflight=preflight["public"],
            )
        if args.execute_r9_installed_restart != EXECUTION_CONFIRMATION:
            raise HarnessError(
                "execution_confirmation_rejected",
                "the live exercise requires the exact confirmation value",
            )
        execution_requested = True
        acceptance = execute_acceptance(
            preflight, args.expected_sha256, args.timeout_seconds
        )
        return 0, public_packet(
            verdict="PASS",
            executed=True,
            preflight=preflight["public"],
            acceptance=acceptance,
        )
    except HarnessError as error:
        return (
            1 if execution_requested else error.exit_code,
            public_packet(verdict="HOLD", executed=execution_requested, error=error),
        )
    except BaseException:
        error = HarnessError("internal_error", "the harness encountered an internal error")
        return (
            1 if execution_requested else 2,
            public_packet(verdict="HOLD", executed=execution_requested, error=error),
        )


def main(argv: Sequence[str] | None = None) -> int:
    status, packet = run(sys.argv[1:] if argv is None else argv)
    encoded = json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    sys.stdout.write(encoded + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
