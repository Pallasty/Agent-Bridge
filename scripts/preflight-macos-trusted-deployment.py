#!/usr/bin/env python3
"""Read-only admission preflight for the Darwin trusted deployment backend.

The command deliberately has no repair, creation, permission, or service-control
path.  Missing inputs are reported as blockers so an operator can review the
host before separately authorizing provisioning or migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


SCHEMA = "agent_bridge.darwin_trusted_deployment_preflight.v0"
BACKEND = "darwin-launchd-v0"
DEFAULT_LABELS = (
    "com.pallasting.agent-bridge.daemon",
    "com.pallasting.agent-bridge.daemon-http",
    "com.pallasting.agent-bridge.palace",
)
LOCAL_FILESYSTEMS = {"apfs", "hfs"}
CLOUD_MARKERS = ("/Mobile Documents/", "/Library/CloudStorage/")
SQLITE_SIDECARS = ("-wal", "-shm", "-journal")


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str = ""


Runner = Callable[[Sequence[str]], CommandResult]


def run_command(argv: Sequence[str]) -> CommandResult:
    completed = subprocess.run(
        list(argv), capture_output=True, text=True, timeout=10, check=False
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _check(status: str, facts: dict[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"status": status}
    if facts:
        row["facts"] = facts
    return row


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError("not a singly linked regular file")
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(fd)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
        if identity(before) != identity(after):
            raise ValueError("file changed while hashing")
    finally:
        os.close(fd)
    return digest.hexdigest()


def _physical_ancestors(path: Path) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    current = path
    while True:
        try:
            value = current.lstat()
        except FileNotFoundError:
            blockers.append("ROOT_OR_ANCESTOR_ABSENT")
            current = current.parent
            if current == current.parent:
                break
            continue
        except OSError:
            blockers.append("ROOT_ANCESTOR_UNREADABLE")
            break
        if stat.S_ISLNK(value.st_mode):
            blockers.append("ROOT_TRAVERSES_SYMLINK")
        if not stat.S_ISDIR(value.st_mode):
            blockers.append("ROOT_ANCESTOR_NOT_DIRECTORY")
        mode = stat.S_IMODE(value.st_mode)
        if value.st_uid not in (0, os.geteuid()):
            blockers.append("ROOT_ANCESTOR_UNTRUSTED_OWNER")
        if mode & 0o022 and not (value.st_uid == 0 and mode & 0o1000):
            blockers.append("ROOT_ANCESTOR_REPLACEABLE")
        if current == current.parent:
            break
        current = current.parent
    return not blockers, sorted(set(blockers))


def _root_check(root: Path, runner: Runner) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    raw = str(root)
    if not root.is_absolute() or os.path.normpath(raw) != raw:
        return _check("FAIL", {"exists": False}), ["ROOT_NOT_CANONICAL_ABSOLUTE"]
    if any(marker in raw + "/" for marker in CLOUD_MARKERS):
        blockers.append("ROOT_CLOUD_SYNCHRONIZED")
    physical, ancestor_blockers = _physical_ancestors(root)
    blockers.extend(ancestor_blockers)
    exists = root.exists()
    facts: dict[str, Any] = {"exists": exists, "physical_ancestors": physical}
    if exists:
        value = root.lstat()
        facts.update(
            owner_uid=value.st_uid,
            mode=f"{stat.S_IMODE(value.st_mode):04o}",
            device=value.st_dev,
            inode=value.st_ino,
        )
        if not stat.S_ISDIR(value.st_mode) or stat.S_ISLNK(value.st_mode):
            blockers.append("ROOT_NOT_PHYSICAL_DIRECTORY")
        if value.st_uid != os.geteuid():
            blockers.append("ROOT_OWNER_MISMATCH")
        if stat.S_IMODE(value.st_mode) != 0o700:
            blockers.append("ROOT_MODE_NOT_0700")
        details = runner(("/bin/ls", "-ldeO@", raw))
        facts["metadata_inspection_complete"] = details.returncode == 0
        if details.returncode != 0:
            blockers.append("ROOT_METADATA_UNREADABLE")
        else:
            lines = [line for line in details.stdout.splitlines()[1:] if line.strip()]
            facts["extended_metadata_lines"] = len(lines)
            if lines:
                blockers.append("ROOT_EXTENDED_METADATA_PRESENT")
        fs = runner(("/usr/bin/stat", "-f", "%T", raw))
        filesystem = fs.stdout.strip().lower() if fs.returncode == 0 else None
        facts["filesystem"] = filesystem
        facts["filesystem_local_supported"] = filesystem in LOCAL_FILESYSTEMS
        if filesystem not in LOCAL_FILESYSTEMS:
            blockers.append("ROOT_FILESYSTEM_NOT_LOCAL_SUPPORTED")
        capacity = os.statvfs(root)
        facts["capacity_free_bytes"] = capacity.f_bavail * capacity.f_frsize
    return _check("PASS" if not blockers else "FAIL", facts), sorted(set(blockers))


def _binary_check(path: Path, runner: Runner) -> tuple[dict[str, Any], list[str]]:
    if not path.exists():
        return _check("NOT_PRESENT", {"exists": False}), []
    blockers: list[str] = []
    facts: dict[str, Any] = {"exists": True}
    try:
        value = path.lstat()
        facts.update(
            device=value.st_dev,
            inode=value.st_ino,
            mode=f"{stat.S_IMODE(value.st_mode):04o}",
            sha256=_sha256(path),
        )
    except (OSError, ValueError):
        return _check("FAIL", facts), ["INSTALLED_BINARY_UNSAFE_OR_UNREADABLE"]
    verify = runner(("/usr/bin/codesign", "--verify", "--strict", str(path)))
    display = runner(("/usr/bin/codesign", "-dv", "--verbose=4", str(path)))
    facts["signature_valid"] = verify.returncode == 0
    identity_match = re.search(r"^Identifier=(.+)$", display.stderr, re.MULTILINE)
    facts["signature_identifier"] = identity_match.group(1) if identity_match else None
    if verify.returncode != 0:
        blockers.append("INSTALLED_BINARY_SIGNATURE_INVALID")
    return _check("PASS" if not blockers else "FAIL", facts), blockers


def _launchd_check(labels: Sequence[str], runner: Runner) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    domain = f"gui/{os.geteuid()}"
    for label in labels:
        result = runner(("/bin/launchctl", "print", f"{domain}/{label}"))
        if result.returncode != 0:
            rows.append({"label": label, "loaded": False})
            continue
        program = re.search(r"^\s*program\s*=\s*(.+?)\s*$", result.stdout, re.MULTILINE)
        path = re.search(r"^\s*path\s*=\s*(.+?)\s*$", result.stdout, re.MULTILINE)
        rows.append(
            {
                "label": label,
                "loaded": True,
                "program": program.group(1) if program else None,
                "plist_path": path.group(1) if path else None,
            }
        )
        if not program:
            blockers.append("LAUNCHD_PROGRAM_UNPARSEABLE")
    return _check("PASS" if not blockers else "FAIL", {"services": rows}), sorted(set(blockers))


def _state_check(database: Path, runner: Runner) -> tuple[dict[str, Any], list[str]]:
    family = [database, *(Path(str(database) + suffix) for suffix in SQLITE_SIDECARS)]
    sidecars = [path.name for path in family[1:] if path.exists()]
    unknown_sidecars: list[str] = []
    if database.parent.is_dir():
        known = {path.name for path in family[1:]}
        unknown_sidecars = sorted(
            path.name
            for path in database.parent.glob(database.name + "-*")
            if path.name not in known
        )
    facts: dict[str, Any] = {
        "database_present": database.exists(),
        "sidecars": sidecars,
        "unknown_sidecars": unknown_sidecars,
    }
    blockers: list[str] = []
    if sidecars:
        blockers.append("SQLITE_SIDECAR_PRESENT")
    if unknown_sidecars:
        blockers.append("SQLITE_UNKNOWN_SIDECAR_PRESENT")
    if database.exists():
        holders = runner(("/usr/sbin/lsof", "-n", "-Fpcufn", "--", *(str(path) for path in family)))
        facts["writer_inventory_complete"] = holders.returncode in (0, 1)
        facts["open_descriptor_process_count"] = sum(
            1 for line in holders.stdout.splitlines() if line.startswith("p")
        )
        if holders.returncode not in (0, 1):
            blockers.append("SQLITE_WRITER_INVENTORY_INCOMPLETE")
        elif facts["open_descriptor_process_count"]:
            blockers.append("SQLITE_OPEN_DESCRIPTOR_PRESENT")
    else:
        facts["writer_inventory_complete"] = True
        facts["open_descriptor_process_count"] = 0
    return _check("PASS" if not blockers else "FAIL", facts), blockers


def build_preflight(
    *, root: Path, installed_binary: Path, state_database: Path,
    labels: Sequence[str] = DEFAULT_LABELS, runner: Runner = run_command,
    system: str | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    checks: dict[str, Any] = {}
    actual_system = system or platform.system()
    if actual_system != "Darwin":
        blockers.append("PLATFORM_NOT_DARWIN")
    checks["platform"] = _check("PASS" if actual_system == "Darwin" else "FAIL", {"system": actual_system})
    checks["root"], found = _root_check(root, runner)
    blockers.extend(found)
    checks["installed_binary"], found = _binary_check(installed_binary, runner)
    blockers.extend(found)
    checks["launchd"], found = _launchd_check(labels, runner)
    blockers.extend(found)
    checks["legacy_state"], found = _state_check(state_database, runner)
    blockers.extend(found)
    blockers = sorted(set(blockers))
    return {
        "schema": SCHEMA,
        "backend": BACKEND,
        "read_only": True,
        "action_performed": False,
        "permission_requested": False,
        "verdict": "READY" if not blockers else "HOLD",
        "checks": checks,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deploy-root", type=Path, required=True)
    parser.add_argument("--installed-binary", type=Path, required=True)
    parser.add_argument("--state-database", type=Path, required=True)
    parser.add_argument("--launchd-label", action="append", dest="labels")
    args = parser.parse_args()
    result = build_preflight(
        root=args.deploy_root,
        installed_binary=args.installed_binary,
        state_database=args.state_database,
        labels=tuple(args.labels) if args.labels else DEFAULT_LABELS,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["verdict"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
