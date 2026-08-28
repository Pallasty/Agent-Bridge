#!/usr/bin/env python3
"""Fail-closed, read-only verification of an installed R9 deployment.

The verifier deliberately accepts no deployment or repair mode.  It reports
only bounded status labels, counts, content identifiers, and fixed failure
codes; process identifiers, filesystem paths, and subprocess output never
enter its JSON result.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


SCHEMA = "agent_bridge.r9_installed_deployment_verification.v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(
    r"agent-bridge\s+\S+\s+\([^()\r\n]*;\s*([0-9a-f]{12}|[0-9a-f]{40})\)"
)

SYSTEMCTL = "/usr/bin/systemctl"
SERVICE_UNITS = (
    ("daemon", "agent-bridge-daemon.service"),
    ("daemon_http", "agent-bridge-daemon-http.service"),
    ("palace", "agent-bridge-palace.service"),
)
HEALTH_TARGETS = (("daemon_http", 7878), ("palace", 7979))
RECEIPT_ENV_KEYS = (
    "AGENT_BRIDGE_CGROUP_RECEIPT_DIR",
    "AGENT_BRIDGE_DB",
    "AGENT_BRIDGE_STATE_DIR",
    "XDG_DATA_HOME",
    "HOME",
)
MAX_PROC_ENV_BYTES = 1024 * 1024

# Only non-secret configuration needed by the installed doctor's read-only
# checks is inherited.  In particular, proxy, credential, cloud, SSH, Git,
# dynamic-loader, and arbitrary AGENT_BRIDGE_* variables do not cross the
# verifier-to-child boundary.
SAFE_ENV_PASSTHROUGH = (
    "HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "AGENT_BRIDGE_CLIENT",
    "AGENT_BRIDGE_TOOLSET",
    "AGENT_BRIDGE_TOOL_PROFILE",
    "AB_SUBSTRATE",
    "AB_SUBSTRATE_PROJECTION",
    "AB_SUBSTRATE_SVD_PATH",
    "AB_SYSTEM_CONTROL_AUDIT_DIR",
)
EXPLICIT_ENV_KEYS = frozenset(
    {
        "AGENT_BRIDGE_CGROUP_RECEIPT_DIR",
        "XDG_RUNTIME_DIR",
        "DBUS_SESSION_BUS_ADDRESS",
    }
)

CHECK_NAMES = (
    "input_contract",
    "binary_physical_identity",
    "binary_owner_permissions",
    "binary_content_sha256",
    "binary_version_commit",
    "receipt_root_physical_identity",
    "receipt_root_owner_mode",
    "systemd_user_bus_binding",
    "systemd_units_active",
    "systemd_executable_content_sha256",
    "systemd_receipt_root_binding",
    "loopback_health_exact_ok",
    "doctor_strict_zero",
)

PASS = "PASS"
FAIL = "FAIL"
NOT_RUN = "NOT_RUN"


class CommandObservation:
    """Bounded command outcome used by the production runner and test fakes."""

    def __init__(self, returncode: int, stdout: bytes, stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class HttpObservation:
    """Minimal HTTP outcome; response metadata is intentionally discarded."""

    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body


class CliInputError(Exception):
    """Argument rejection whose public form never echoes caller input."""


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:  # pragma: no cover - argparse plumbing
        raise CliInputError


CommandRunner = Callable[[list[str], int, dict[str, str] | None], CommandObservation]
HealthReader = Callable[[int, str, float], HttpObservation]


def command_environment(
    argv: list[str], explicit_env: dict[str, str] | None = None
) -> dict[str, str]:
    """Build the bounded environment used by version, doctor, and systemctl."""

    env = {
        key: os.environ[key]
        for key in SAFE_ENV_PASSTHROUGH
        if key in os.environ
    }
    env.update(
        {
            "LANG": "C",
            "LC_ALL": "C",
            "NO_COLOR": "1",
            "PAGER": "cat",
            "PATH": "/usr/bin:/bin",
            "SYSTEMD_COLORS": "0",
            "SYSTEMD_PAGER": "",
        }
    )
    if argv and argv[0].startswith("/") and argv[0] != SYSTEMCTL:
        # Bind doctor to the explicitly verified installation rather than an
        # ambient AGENT_BRIDGE_INSTALL_DIR value.
        env["AGENT_BRIDGE_INSTALL_DIR"] = str(Path(argv[0]).parent)
    if explicit_env:
        if set(explicit_env) - EXPLICIT_ENV_KEYS:
            raise ValueError("unsupported explicit child environment key")
        env.update(explicit_env)
    return env


def run_command(
    argv: list[str], timeout: int, explicit_env: dict[str, str] | None = None
) -> CommandObservation:
    """Run one fixed read-only probe without invoking a shell."""

    env = command_environment(argv, explicit_env)
    try:
        completed = subprocess.run(
            argv,
            cwd="/",
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
            close_fds=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return CommandObservation(124, b"", b"")
    return CommandObservation(completed.returncode, completed.stdout, completed.stderr)


def read_loopback_health(port: int, target: str, timeout: float) -> HttpObservation:
    """Read one fixed loopback endpoint without redirects or proxy discovery."""

    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request(
            "GET",
            target,
            headers={"Accept": "text/plain", "Connection": "close"},
        )
        response = connection.getresponse()
        # Three bytes distinguish the exact body b"ok" from any extension.
        return HttpObservation(response.status, response.read(3))
    finally:
        connection.close()


def _path_syntax(raw: str, *, allow_root: bool) -> str | None:
    if not raw.startswith("/"):
        return "NOT_ABSOLUTE"
    if any(ord(character) < 32 or ord(character) == 127 for character in raw):
        return "NON_CANONICAL"
    if raw == "/":
        return None if allow_root else "ROOT_FORBIDDEN"
    if raw.endswith("/") or "//" in raw:
        return "NON_CANONICAL"
    components = raw.split("/")[1:]
    if any(component in {"", ".", ".."} for component in components):
        return "NON_CANONICAL"
    return None


def _physical_metadata(raw: str, *, kind: str) -> tuple[os.stat_result | None, str | None]:
    """lstat every component and reject all symlink traversal."""

    current = Path("/")
    components = raw.split("/")[1:]
    if not components:
        components = []
    try:
        root_metadata = os.lstat(current)
    except OSError:
        return None, "UNAVAILABLE"
    if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode):
        return None, "NON_PHYSICAL_COMPONENT"

    metadata = root_metadata
    for index, component in enumerate(components):
        current = current / component
        try:
            metadata = os.lstat(current)
        except OSError:
            return None, "UNAVAILABLE"
        if stat.S_ISLNK(metadata.st_mode):
            return None, "SYMLINK_COMPONENT"
        if index < len(components) - 1 and not stat.S_ISDIR(metadata.st_mode):
            return None, "NON_DIRECTORY_COMPONENT"

    if kind == "file" and not stat.S_ISREG(metadata.st_mode):
        return None, "NOT_REGULAR_FILE"
    if kind == "directory" and not stat.S_ISDIR(metadata.st_mode):
        return None, "NOT_DIRECTORY"
    if kind == "socket" and not stat.S_ISSOCK(metadata.st_mode):
        return None, "NOT_SOCKET"
    return metadata, None


def _parent_chain_snapshot(
    raw: str, *, euid: int, direct_parent_allows_root: bool
) -> tuple[str | None, tuple[tuple[int, ...], ...]]:
    """Reject ancestors that permit replacement of a verified leaf.

    The direct parent is always required to be non-group/other-writable.  A
    binary's direct parent must be euid-owned; a receipt root may sit directly
    below either an euid- or root-owned directory.  Higher ancestors must be
    euid/root-owned and non-writable.  A root-owned sticky directory (the
    conventional /tmp boundary used by isolated tests) is the sole writable
    higher-ancestor exception because sticky rename rules protect its child.
    """

    current = Path(raw).parent
    direct = True
    snapshots: list[tuple[int, ...]] = []
    while True:
        try:
            metadata = os.lstat(current)
        except OSError:
            reason = "PARENT_UNAVAILABLE" if direct else "ANCESTOR_UNAVAILABLE"
            return reason, tuple(snapshots)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            reason = "PARENT_NON_PHYSICAL" if direct else "ANCESTOR_NON_PHYSICAL"
            return reason, tuple(snapshots)

        snapshots.append(_boundary_fingerprint(metadata))

        mode = stat.S_IMODE(metadata.st_mode)
        if direct:
            allowed_owner = metadata.st_uid == euid or (
                direct_parent_allows_root and metadata.st_uid == 0
            )
            if not allowed_owner:
                return "PARENT_OWNER_MISMATCH", tuple(snapshots)
            if mode & 0o022:
                return "PARENT_GROUP_OR_OTHER_WRITABLE", tuple(snapshots)
        else:
            if metadata.st_uid not in {0, euid}:
                return "ANCESTOR_OWNER_MISMATCH", tuple(snapshots)
            root_sticky_boundary = bool(
                metadata.st_uid == 0
                and mode & stat.S_ISVTX
                and mode & 0o022
            )
            if mode & 0o022 and not root_sticky_boundary:
                return "ANCESTOR_GROUP_OR_OTHER_WRITABLE", tuple(snapshots)

        if current == Path("/"):
            return None, tuple(snapshots)
        current = current.parent
        direct = False


def _parent_chain_security(
    raw: str, *, euid: int, direct_parent_allows_root: bool
) -> str | None:
    reason, _snapshot = _parent_chain_snapshot(
        raw,
        euid=euid,
        direct_parent_allows_root=direct_parent_allows_root,
    )
    return reason


def _boundary_fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    """Identity and authority bits, excluding legitimate directory activity."""

    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_gid,
    )


def _metadata_fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _sha256_regular_file(
    path: Path, *, reject_final_symlink: bool
) -> tuple[str | None, os.stat_result | None]:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    if reject_final_symlink:
        flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None, None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            return None, metadata
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        return digest.hexdigest(), metadata
    except OSError:
        return None, None
    finally:
        os.close(descriptor)


def _read_bounded_proc_environment(path: Path) -> bytes | None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        chunks: list[bytes] = []
        total = 0
        while True:
            remaining = MAX_PROC_ENV_BYTES + 1 - total
            if remaining <= 0:
                return None
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_PROC_ENV_BYTES:
                return None
        return b"".join(chunks)
    except OSError:
        return None
    finally:
        os.close(descriptor)


def _resolved_receipt_root_from_environment(raw: bytes) -> str | None:
    """Resolve only path-setting variables; never retain unrelated values."""

    if not raw or not raw.endswith(b"\0"):
        return None
    relevant_bytes = {key.encode("ascii"): key for key in RECEIPT_ENV_KEYS}
    observed: dict[str, str] = {}
    for entry in raw[:-1].split(b"\0"):
        if not entry or b"=" not in entry:
            return None
        key, value = entry.split(b"=", 1)
        relevant_key = relevant_bytes.get(key)
        if relevant_key is None:
            continue
        if relevant_key in observed or not value:
            return None
        try:
            rendered = value.decode("utf-8", "strict")
        except UnicodeDecodeError:
            return None
        if _path_syntax(rendered, allow_root=True) is not None:
            return None
        observed[relevant_key] = rendered

    if "AGENT_BRIDGE_CGROUP_RECEIPT_DIR" in observed:
        resolved = Path(observed["AGENT_BRIDGE_CGROUP_RECEIPT_DIR"])
    elif "AGENT_BRIDGE_DB" in observed:
        database = Path(observed["AGENT_BRIDGE_DB"])
        # Rust's Path::parent() returns None for the filesystem root.  pathlib
        # instead returns Path("/") again, which would otherwise turn the
        # invalid database value into a false /workload-receipts match.
        if database == Path("/"):
            return None
        resolved = database.parent / "workload-receipts"
    elif "AGENT_BRIDGE_STATE_DIR" in observed:
        resolved = Path(observed["AGENT_BRIDGE_STATE_DIR"]) / "workload-receipts"
    elif "XDG_DATA_HOME" in observed:
        resolved = (
            Path(observed["XDG_DATA_HOME"])
            / "agent-bridge"
            / "workload-receipts"
        )
    elif "HOME" in observed:
        resolved = (
            Path(observed["HOME"])
            / ".local"
            / "share"
            / "agent-bridge"
            / "workload-receipts"
        )
    else:
        return None

    rendered_root = str(resolved)
    if _path_syntax(rendered_root, allow_root=False) is not None:
        return None
    return rendered_root


def _service_receipt_root_matches(environment_path: Path, expected_root: str) -> bool:
    raw = _read_bounded_proc_environment(environment_path)
    if raw is None:
        return False
    return _resolved_receipt_root_from_environment(raw) == expected_root


def _systemd_user_bus_binding(
    *, euid: int, runtime_base: Path
) -> tuple[
    dict[str, str] | None,
    tuple[tuple[int, ...], tuple[int, ...], tuple[tuple[int, ...], ...]] | None,
]:
    """Bind systemctl to the physical private bus for exactly this euid."""

    runtime_dir = runtime_base / str(euid)
    runtime_value = str(runtime_dir)
    if _path_syntax(runtime_value, allow_root=False) is not None:
        return None, None
    runtime_metadata, runtime_reason = _physical_metadata(
        runtime_value, kind="directory"
    )
    if (
        runtime_reason is not None
        or runtime_metadata is None
        or runtime_metadata.st_uid != euid
        or stat.S_IMODE(runtime_metadata.st_mode) != 0o700
    ):
        return None, None
    parent_reason, parent_snapshot = _parent_chain_snapshot(
        runtime_value,
        euid=euid,
        direct_parent_allows_root=True,
    )
    if parent_reason is not None:
        return None, None

    bus = runtime_dir / "bus"
    bus_metadata, bus_reason = _physical_metadata(str(bus), kind="socket")
    if (
        bus_reason is not None
        or bus_metadata is None
        or bus_metadata.st_uid != euid
    ):
        return None, None
    environment = {
        "XDG_RUNTIME_DIR": runtime_value,
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={bus}",
    }
    snapshot = (
        _boundary_fingerprint(runtime_metadata),
        _boundary_fingerprint(bus_metadata),
        parent_snapshot,
    )
    return environment, snapshot


def _safe_command(
    runner: CommandRunner,
    argv: list[str],
    timeout: int,
    explicit_env: dict[str, str] | None = None,
) -> CommandObservation | None:
    try:
        observed = runner(argv, timeout, explicit_env)
    except Exception:
        return None
    if (
        type(getattr(observed, "returncode", None)) is not int
        or not isinstance(getattr(observed, "stdout", None), bytes)
        or not isinstance(getattr(observed, "stderr", None), bytes)
    ):
        return None
    return observed


def _version_matches_commit(stdout: bytes, expected_commit: str) -> bool:
    if len(stdout) > 4096:
        return False
    try:
        rendered = stdout.decode("utf-8").strip()
    except UnicodeDecodeError:
        return False
    match = VERSION_RE.fullmatch(rendered)
    if match is None:
        return False
    observed_commit = match.group(1)
    return observed_commit in {expected_commit[:12], expected_commit}


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise ValueError("non-finite JSON value")


def _strict_doctor_pass(stdout: bytes) -> bool:
    if len(stdout) > 1024 * 1024:
        return False
    try:
        payload = json.loads(
            stdout.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, ValueError, TypeError):
        return False
    doctor_checks = payload.get("checks") if isinstance(payload, dict) else None
    receipt_root_checks = (
        [
            row
            for row in doctor_checks
            if isinstance(row, dict) and row.get("name") == "workload_receipt_root"
        ]
        if isinstance(doctor_checks, list)
        else []
    )
    return bool(
        isinstance(payload, dict)
        and payload.get("ok") is True
        and type(payload.get("fails")) is int
        and payload.get("fails") == 0
        and type(payload.get("warns")) is int
        and payload.get("warns") == 0
        and len(receipt_root_checks) == 1
        and receipt_root_checks[0].get("status") == "ok"
    )


def _query_active_service(
    runner: CommandRunner,
    systemctl: str,
    unit: str,
    systemd_environment: dict[str, str],
) -> int | None:
    observed = _safe_command(
        runner,
        [
            systemctl,
            "--user",
            "show",
            unit,
            "--property=LoadState",
            "--property=ActiveState",
            "--property=MainPID",
            "--no-pager",
        ],
        10,
        systemd_environment,
    )
    if observed is None or observed.returncode != 0 or len(observed.stdout) > 4096:
        return None
    try:
        text = observed.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None
    values: dict[str, str] = {}
    for line in text.splitlines():
        if not line:
            continue
        if "=" not in line:
            return None
        key, value = line.split("=", 1)
        if key in values or key not in {"LoadState", "ActiveState", "MainPID"}:
            return None
        values[key] = value
    if set(values) != {"LoadState", "ActiveState", "MainPID"}:
        return None
    if values["LoadState"] != "loaded" or values["ActiveState"] != "active":
        return None
    rendered_identifier = values["MainPID"]
    if re.fullmatch(r"[1-9][0-9]*", rendered_identifier) is None:
        return None
    return int(rendered_identifier)


def _status_entry(status_value: str) -> dict[str, str]:
    return {"status": status_value}


def _terminal_failure_report(code: str) -> dict[str, Any]:
    """Return a schema-shaped failure without reflecting any caller value."""

    return {
        "schema": SCHEMA,
        "verdict": "FAIL_CLOSED",
        "read_only": True,
        "expected": {"binary_sha256": None, "commit": None},
        "security_boundaries": {
            "installed_binary": {"status": FAIL},
            "production_receipt_root": {"status": FAIL},
        },
        "checks": {name: _status_entry(NOT_RUN) for name in CHECK_NAMES},
        "services": {
            role: {
                "active": NOT_RUN,
                "executable_content_sha256": NOT_RUN,
                "receipt_root_binding": NOT_RUN,
            }
            for role, _unit in SERVICE_UNITS
        },
        "health": {role: NOT_RUN for role, _port in HEALTH_TARGETS},
        "counts": {"required_services": 3, "required_health_endpoints": 2},
        "failures": [code],
    }


def verify_installed_deployment(
    *,
    binary: str,
    expected_sha256: str,
    expected_commit: str,
    receipt_root: str,
    runner: CommandRunner = run_command,
    health_reader: HealthReader = read_loopback_health,
    proc_root: Path = Path("/proc"),
    systemd_runtime_base: Path = Path("/run/user"),
    systemctl: str = SYSTEMCTL,
    euid: int | None = None,
) -> dict[str, Any]:
    """Verify one installed snapshot without creating or mutating state."""

    effective_uid = os.geteuid() if euid is None else euid
    checks = {name: _status_entry(NOT_RUN) for name in CHECK_NAMES}
    failures: list[str] = []

    def fail(check: str, code: str) -> None:
        checks[check] = _status_entry(FAIL)
        if code not in failures:
            failures.append(code)

    def passed(check: str) -> None:
        checks[check] = _status_entry(PASS)

    hash_valid = SHA256_RE.fullmatch(expected_sha256) is not None
    commit_valid = COMMIT_RE.fullmatch(expected_commit) is not None
    binary_syntax = _path_syntax(binary, allow_root=True)
    receipt_syntax = _path_syntax(receipt_root, allow_root=False)
    input_errors = []
    if not hash_valid:
        input_errors.append("EXPECTED_SHA256_INVALID")
    if not commit_valid:
        input_errors.append("EXPECTED_COMMIT_INVALID")
    if binary_syntax is not None:
        input_errors.append(f"BINARY_{binary_syntax}")
    if receipt_syntax is not None:
        input_errors.append(f"RECEIPT_ROOT_{receipt_syntax}")
    if input_errors:
        checks["input_contract"] = _status_entry(FAIL)
        failures.extend(input_errors)
    else:
        passed("input_contract")

    binary_metadata: os.stat_result | None = None
    binary_digest: str | None = None
    binary_fingerprint: tuple[int, ...] | None = None
    binary_parent_snapshot: tuple[tuple[int, ...], ...] | None = None
    if binary_syntax is not None:
        fail("binary_physical_identity", f"BINARY_{binary_syntax}")
    else:
        binary_metadata, binary_reason = _physical_metadata(binary, kind="file")
        if binary_reason is not None or binary_metadata is None:
            fail("binary_physical_identity", f"BINARY_{binary_reason or 'UNAVAILABLE'}")
        else:
            passed("binary_physical_identity")
            if binary_metadata.st_uid != effective_uid:
                fail("binary_owner_permissions", "BINARY_OWNER_MISMATCH")
            elif stat.S_IMODE(binary_metadata.st_mode) & 0o7000:
                fail("binary_owner_permissions", "BINARY_SPECIAL_MODE_BITS")
            elif stat.S_IMODE(binary_metadata.st_mode) & 0o022:
                fail(
                    "binary_owner_permissions",
                    "BINARY_GROUP_OR_OTHER_WRITABLE",
                )
            else:
                binary_parent_reason, observed_binary_parents = _parent_chain_snapshot(
                    binary,
                    euid=effective_uid,
                    direct_parent_allows_root=False,
                )
                if binary_parent_reason is not None:
                    fail(
                        "binary_owner_permissions",
                        f"BINARY_{binary_parent_reason}",
                    )
                else:
                    binary_parent_snapshot = observed_binary_parents
                    passed("binary_owner_permissions")

            if hash_valid:
                binary_digest, opened_metadata = _sha256_regular_file(
                    Path(binary), reject_final_symlink=True
                )
                if binary_digest is None or opened_metadata is None:
                    fail("binary_content_sha256", "BINARY_CONTENT_UNAVAILABLE")
                elif _metadata_fingerprint(opened_metadata) != _metadata_fingerprint(
                    binary_metadata
                ):
                    fail("binary_content_sha256", "BINARY_CHANGED_DURING_HASH")
                elif binary_digest != expected_sha256:
                    fail("binary_content_sha256", "BINARY_SHA256_MISMATCH")
                else:
                    binary_fingerprint = _metadata_fingerprint(opened_metadata)
                    passed("binary_content_sha256")

    binary_is_safe_and_bound = all(
        checks[name]["status"] == PASS
        for name in (
            "binary_physical_identity",
            "binary_owner_permissions",
            "binary_content_sha256",
        )
    )
    if binary_is_safe_and_bound and commit_valid:
        version = _safe_command(runner, [binary, "--version"], 10)
        if (
            version is None
            or version.returncode != 0
            or not _version_matches_commit(version.stdout, expected_commit)
        ):
            fail("binary_version_commit", "BINARY_VERSION_COMMIT_MISMATCH")
        else:
            passed("binary_version_commit")

    receipt_boundary_fingerprint: tuple[int, ...] | None = None
    receipt_parent_snapshot: tuple[tuple[int, ...], ...] | None = None
    if receipt_syntax is not None:
        fail("receipt_root_physical_identity", f"RECEIPT_ROOT_{receipt_syntax}")
    else:
        receipt_metadata, receipt_reason = _physical_metadata(
            receipt_root, kind="directory"
        )
        if receipt_reason is not None or receipt_metadata is None:
            fail(
                "receipt_root_physical_identity",
                f"RECEIPT_ROOT_{receipt_reason or 'UNAVAILABLE'}",
            )
        else:
            passed("receipt_root_physical_identity")
            if receipt_metadata.st_uid != effective_uid:
                fail("receipt_root_owner_mode", "RECEIPT_ROOT_OWNER_MISMATCH")
            elif stat.S_IMODE(receipt_metadata.st_mode) != 0o700:
                fail("receipt_root_owner_mode", "RECEIPT_ROOT_MODE_NOT_0700")
            else:
                receipt_parent_reason, observed_receipt_parents = _parent_chain_snapshot(
                    receipt_root,
                    euid=effective_uid,
                    direct_parent_allows_root=True,
                )
                if receipt_parent_reason is not None:
                    fail(
                        "receipt_root_owner_mode",
                        f"RECEIPT_ROOT_{receipt_parent_reason}",
                    )
                else:
                    receipt_boundary_fingerprint = _boundary_fingerprint(
                        receipt_metadata
                    )
                    receipt_parent_snapshot = observed_receipt_parents
                    passed("receipt_root_owner_mode")

    systemd_environment, systemd_bus_snapshot = _systemd_user_bus_binding(
        euid=effective_uid,
        runtime_base=systemd_runtime_base,
    )
    if systemd_environment is None or systemd_bus_snapshot is None:
        fail("systemd_user_bus_binding", "SYSTEMD_USER_BUS_BINDING_UNSAFE")
    else:
        passed("systemd_user_bus_binding")

    service_results: dict[str, dict[str, str]] = {}
    initial_service_identifiers: dict[str, int] = {}
    for role, unit in SERVICE_UNITS:
        row = {
            "active": NOT_RUN,
            "executable_content_sha256": NOT_RUN,
            "receipt_root_binding": NOT_RUN,
        }
        service_results[role] = row
        if systemd_environment is None:
            continue
        first_identifier = _query_active_service(
            runner, systemctl, unit, systemd_environment
        )
        if first_identifier is None:
            row["active"] = FAIL
            failures.append(f"SERVICE_{role.upper()}_NOT_ACTIVE")
            continue
        initial_service_identifiers[role] = first_identifier
        row["active"] = PASS
        process_root = proc_root / str(first_identifier)
        receipt_binding_matches = _service_receipt_root_matches(
            process_root / "environ", receipt_root
        )

        process_digest: str | None = None
        executable_target = ""
        final_executable_target = ""
        if hash_valid and binary_digest == expected_sha256:
            executable_link = process_root / "exe"
            try:
                executable_target = os.readlink(executable_link)
            except OSError:
                pass
            if executable_target == binary:
                process_digest, _process_metadata = _sha256_regular_file(
                    executable_link, reject_final_symlink=False
                )

        second_identifier = _query_active_service(
            runner, systemctl, unit, systemd_environment
        )
        if second_identifier != first_identifier:
            row["active"] = FAIL
            failures.append(f"SERVICE_{role.upper()}_IDENTITY_UNSTABLE")
            row["executable_content_sha256"] = FAIL
            row["receipt_root_binding"] = FAIL
            continue

        receipt_binding_matches = receipt_binding_matches and (
            _service_receipt_root_matches(process_root / "environ", receipt_root)
        )
        if hash_valid and binary_digest == expected_sha256:
            try:
                final_executable_target = os.readlink(process_root / "exe")
            except OSError:
                final_executable_target = ""

        if receipt_binding_matches:
            row["receipt_root_binding"] = PASS
        else:
            failures.append(f"SERVICE_{role.upper()}_RECEIPT_ROOT_BINDING_INVALID")
            row["receipt_root_binding"] = FAIL

        if not hash_valid or binary_digest != expected_sha256:
            continue
        if not executable_target:
            failures.append(f"SERVICE_{role.upper()}_EXECUTABLE_UNAVAILABLE")
            row["executable_content_sha256"] = FAIL
        elif executable_target.endswith(" (deleted)"):
            failures.append(f"SERVICE_{role.upper()}_EXECUTABLE_DELETED")
            row["executable_content_sha256"] = FAIL
        elif executable_target != binary:
            failures.append(f"SERVICE_{role.upper()}_EXECUTABLE_TARGET_MISMATCH")
            row["executable_content_sha256"] = FAIL
        elif final_executable_target.endswith(" (deleted)"):
            failures.append(f"SERVICE_{role.upper()}_EXECUTABLE_DELETED")
            row["executable_content_sha256"] = FAIL
        elif final_executable_target != binary:
            failures.append(f"SERVICE_{role.upper()}_EXECUTABLE_TARGET_UNSTABLE")
            row["executable_content_sha256"] = FAIL
        elif process_digest != expected_sha256 or process_digest != binary_digest:
            failures.append(f"SERVICE_{role.upper()}_EXECUTABLE_SHA256_MISMATCH")
            row["executable_content_sha256"] = FAIL
        else:
            row["executable_content_sha256"] = PASS

    health_results: dict[str, str] = {}
    for role, port in HEALTH_TARGETS:
        status_value = FAIL
        try:
            observed_health = health_reader(port, "/healthz", 3.0)
            if (
                type(getattr(observed_health, "status", None)) is int
                and observed_health.status == 200
                and getattr(observed_health, "body", None) == b"ok"
            ):
                status_value = PASS
        except Exception:
            pass
        health_results[role] = status_value
        if status_value == FAIL:
            failures.append(f"HEALTH_{role.upper()}_NOT_EXACT_OK")
    if all(value == PASS for value in health_results.values()):
        passed("loopback_health_exact_ok")
    else:
        checks["loopback_health_exact_ok"] = _status_entry(FAIL)

    receipt_is_safe = (
        checks["receipt_root_physical_identity"]["status"] == PASS
        and checks["receipt_root_owner_mode"]["status"] == PASS
    )
    if (
        checks["binary_version_commit"]["status"] == PASS
        and receipt_is_safe
        and systemd_environment is not None
    ):
        doctor_environment = dict(systemd_environment)
        doctor_environment["AGENT_BRIDGE_CGROUP_RECEIPT_DIR"] = receipt_root
        doctor = _safe_command(
            runner,
            [binary, "doctor", "--json"],
            60,
            doctor_environment,
        )
        if (
            doctor is None
            or doctor.returncode != 0
            or not _strict_doctor_pass(doctor.stdout)
        ):
            fail("doctor_strict_zero", "DOCTOR_NOT_STRICT_ZERO")
        else:
            passed("doctor_strict_zero")

    # Health and Doctor can take long enough for an earlier service observation
    # to become stale.  Perform two whole-set sweeps, rather than two adjacent
    # samples of one service at a time, so a service changed while either of the
    # other services is inspected is observed in the second sweep.  Each sweep
    # binds the original MainPID, one bounded environment read, and the exact
    # executable path/content.  Public failures retain only the fixed service
    # role and never expose a PID, path, or environment.
    final_service_observations: dict[
        str, list[tuple[bool, bool, str, str | None]]
    ] = {role: [] for role, _unit in SERVICE_UNITS}
    if systemd_environment is not None:
        for _sweep in range(2):
            for role, unit in SERVICE_UNITS:
                original_identifier = initial_service_identifiers.get(role)
                if original_identifier is None:
                    continue

                observed_identifier = _query_active_service(
                    runner, systemctl, unit, systemd_environment
                )
                identity_matches = observed_identifier == original_identifier
                receipt_binding_matches = False
                executable_target = ""
                process_digest: str | None = None
                if identity_matches:
                    process_root = proc_root / str(original_identifier)
                    receipt_binding_matches = _service_receipt_root_matches(
                        process_root / "environ", receipt_root
                    )
                    if hash_valid and binary_digest == expected_sha256:
                        executable_link = process_root / "exe"
                        try:
                            executable_target = os.readlink(executable_link)
                        except OSError:
                            pass
                        if executable_target == binary:
                            process_digest, _process_metadata = (
                                _sha256_regular_file(
                                    executable_link,
                                    reject_final_symlink=False,
                                )
                            )
                final_service_observations[role].append(
                    (
                        identity_matches,
                        receipt_binding_matches,
                        executable_target,
                        process_digest,
                    )
                )

        for role, _unit in SERVICE_UNITS:
            row = service_results[role]
            observations = final_service_observations[role]
            if not observations:
                continue
            if len(observations) != 2 or not all(
                observation[0] for observation in observations
            ):
                row["active"] = FAIL
                row["executable_content_sha256"] = FAIL
                row["receipt_root_binding"] = FAIL
                failures.append(f"SERVICE_{role.upper()}_LATE_IDENTITY_UNSTABLE")
                continue

            if not all(observation[1] for observation in observations):
                row["receipt_root_binding"] = FAIL
                failures.append(
                    f"SERVICE_{role.upper()}_LATE_RECEIPT_ROOT_BINDING_INVALID"
                )

            if not hash_valid or binary_digest != expected_sha256:
                continue
            executable_failure: str | None = None
            for _identity_matches, _receipt_matches, target, digest in observations:
                if not target:
                    executable_failure = "LATE_EXECUTABLE_UNAVAILABLE"
                elif target.endswith(" (deleted)"):
                    executable_failure = "LATE_EXECUTABLE_DELETED"
                elif target != binary:
                    executable_failure = "LATE_EXECUTABLE_TARGET_MISMATCH"
                elif digest != expected_sha256 or digest != binary_digest:
                    executable_failure = "LATE_EXECUTABLE_SHA256_MISMATCH"
                if executable_failure is not None:
                    break
            if executable_failure is not None:
                row["executable_content_sha256"] = FAIL
                failures.append(
                    f"SERVICE_{role.upper()}_{executable_failure}"
                )

    service_aggregates = (
        ("systemd_units_active", "active"),
        ("systemd_executable_content_sha256", "executable_content_sha256"),
        ("systemd_receipt_root_binding", "receipt_root_binding"),
    )
    for check_name, service_field in service_aggregates:
        statuses = [row[service_field] for row in service_results.values()]
        if all(value == PASS for value in statuses):
            passed(check_name)
        elif any(value == FAIL for value in statuses):
            checks[check_name] = _status_entry(FAIL)

    # Re-read the installed binary after all executable probes.  This turns a
    # concurrent atomic replacement into a fail-closed result instead of a
    # mixed-time acceptance snapshot.
    if binary_is_safe_and_bound:
        assert binary_fingerprint is not None
        assert binary_parent_snapshot is not None
        final_metadata, final_reason = _physical_metadata(binary, kind="file")
        final_digest, final_opened_metadata = _sha256_regular_file(
            Path(binary), reject_final_symlink=True
        )
        final_parent_reason, final_binary_parents = _parent_chain_snapshot(
            binary,
            euid=effective_uid,
            direct_parent_allows_root=False,
        )
        if final_reason is not None or final_metadata is None:
            fail(
                "binary_physical_identity",
                "BINARY_PHYSICAL_IDENTITY_CHANGED_DURING_VERIFICATION",
            )
        if (
            final_parent_reason is not None
            or final_binary_parents != binary_parent_snapshot
        ):
            fail(
                "binary_owner_permissions",
                "BINARY_PARENT_CHANGED_DURING_VERIFICATION",
            )
        if (
            final_metadata is None
            or final_opened_metadata is None
            or final_digest != expected_sha256
            or (
                final_metadata is not None
                and _metadata_fingerprint(final_metadata) != binary_fingerprint
            )
            or _metadata_fingerprint(final_opened_metadata) != binary_fingerprint
        ):
            fail("binary_content_sha256", "BINARY_CHANGED_DURING_VERIFICATION")

    if receipt_boundary_fingerprint is not None:
        assert receipt_parent_snapshot is not None
        final_receipt_metadata, final_receipt_reason = _physical_metadata(
            receipt_root, kind="directory"
        )
        final_receipt_parent_reason, final_receipt_parents = _parent_chain_snapshot(
            receipt_root,
            euid=effective_uid,
            direct_parent_allows_root=True,
        )
        if (
            final_receipt_reason is not None
            or final_receipt_metadata is None
            or (
                final_receipt_metadata is not None
                and final_receipt_metadata.st_dev
                != receipt_boundary_fingerprint[0]
            )
            or (
                final_receipt_metadata is not None
                and final_receipt_metadata.st_ino
                != receipt_boundary_fingerprint[1]
            )
        ):
            fail(
                "receipt_root_physical_identity",
                "RECEIPT_ROOT_CHANGED_DURING_VERIFICATION",
            )
        if (
            final_receipt_metadata is None
            or _boundary_fingerprint(final_receipt_metadata)
            != receipt_boundary_fingerprint
            or final_receipt_parent_reason is not None
            or final_receipt_parents != receipt_parent_snapshot
        ):
            fail(
                "receipt_root_owner_mode",
                "RECEIPT_ROOT_BOUNDARY_CHANGED_DURING_VERIFICATION",
            )

    if systemd_bus_snapshot is not None:
        final_systemd_environment, final_systemd_bus_snapshot = (
            _systemd_user_bus_binding(
                euid=effective_uid,
                runtime_base=systemd_runtime_base,
            )
        )
        if (
            final_systemd_environment != systemd_environment
            or final_systemd_bus_snapshot != systemd_bus_snapshot
        ):
            fail(
                "systemd_user_bus_binding",
                "SYSTEMD_USER_BUS_BINDING_CHANGED_DURING_VERIFICATION",
            )

    binary_boundary = (
        PASS
        if checks["binary_physical_identity"]["status"] == PASS
        and checks["binary_owner_permissions"]["status"] == PASS
        else FAIL
    )
    receipt_boundary = (
        PASS
        if checks["receipt_root_physical_identity"]["status"] == PASS
        and checks["receipt_root_owner_mode"]["status"] == PASS
        else FAIL
    )

    all_pass = all(entry["status"] == PASS for entry in checks.values())
    if not all_pass and not failures:
        failures.append("VERIFICATION_INCOMPLETE")

    return {
        "schema": SCHEMA,
        "verdict": "PASS" if all_pass else "FAIL_CLOSED",
        "read_only": True,
        "expected": {
            "binary_sha256": expected_sha256 if hash_valid else None,
            "commit": expected_commit if commit_valid else None,
        },
        "security_boundaries": {
            "installed_binary": {"status": binary_boundary},
            "production_receipt_root": {"status": receipt_boundary},
        },
        "checks": checks,
        "services": service_results,
        "health": health_results,
        "counts": {"required_services": 3, "required_health_endpoints": 2},
        "failures": failures,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        description="Read-only verification of an installed Agent-Bridge R9 deployment"
    )
    parser.add_argument("--binary", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--receipt-root", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except CliInputError:
        print(
            json.dumps(
                _terminal_failure_report("INVALID_ARGUMENTS"),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    try:
        report = verify_installed_deployment(
            binary=args.binary,
            expected_sha256=args.expected_sha256,
            expected_commit=args.expected_commit,
            receipt_root=args.receipt_root,
        )
    except Exception:
        report = _terminal_failure_report("INTERNAL_VERIFICATION_ERROR")
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    if report["verdict"] == "PASS":
        return 0
    return 2 if "INTERNAL_VERIFICATION_ERROR" in report["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
