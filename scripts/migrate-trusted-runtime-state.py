#!/usr/bin/python3
"""Fail-closed migration of legacy Agent Bridge state into a trusted root.

Production entry point (the interpreter flags are part of the trust boundary):

    /usr/bin/python3 -I -B migrate-trusted-runtime-state.py \
        preflight|migrate|verify --deploy-root /private/agent-bridge

The tool deliberately never controls a service.  An operator must quiesce the
complete fixed unit set before every command, and a successful migration leaves
that unit set quiesced.  ``preflight`` and ``verify`` perform no filesystem
mutation.  ``migrate`` is the only writing command and requires a confirmation
string bound to the publisher candidate and pending-admission digest.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator, Sequence
from urllib.parse import quote


PLAN_SCHEMA = "agent_bridge.trusted_runtime_state_migration_plan.v1"
RECEIPT_SCHEMA = "agent_bridge.trusted_runtime_state_migration_receipt.v1"
RESULT_SCHEMA = "agent_bridge.trusted_runtime_state_migration_result.v1"
RECEIPT_DOMAIN = b"agent-bridge/trusted-runtime-state-migration/receipt/v1\0"
MANIFEST_DOMAIN = b"agent-bridge/trusted-runtime-state-migration/manifest/v1\0"
SOURCE_MANIFEST_DOMAIN = b"agent-bridge/trusted-runtime-state-migration/source-manifest/v1\0"
TRANSACTION_DOMAIN = b"agent-bridge/trusted-runtime-state-migration/transaction/v1\0"
MAPPINGS_DOMAIN = b"agent-bridge/trusted-runtime-state-migration/mappings/v1\0"

GITLAB_REMOTE_URL = "git@gitlab.com:pallasting/agent-bridge.git"
PENDING_KEYS = (
    "schema",
    "lease_id",
    "challenge",
    "real_path",
    "shared_targets",
    "candidate_commit",
    "installed_binary_sha256",
    "installed_binary_inode",
    "installed_binary_mode",
    "installed_assets_sha256",
    "installed_at",
    "fresh_mcp",
    "force_reinstall",
    "force_reason",
)

RUNTIME_LEAVES = (
    "home",
    "data",
    "cache",
    "xdg-state",
    "tmp",
    "workload-tmp",
    "workload-receipts",
)
MIGRATABLE_TARGET_LEAVES = frozenset(("home", "data", "cache", "xdg-state"))
SQLITE_TARGET = "data/agent-bridge/state.db"
SQLITE_FAMILY_SUFFIXES = ("", "-wal", "-shm", "-journal")
SQLITE_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")

UNITS = (
    "agent-bridge-daemon.service",
    "agent-bridge-daemon-http.service",
    "agent-bridge-palace.service",
    "agent-bridge-sync.service",
    "agent-bridge-sync.timer",
    "agent-bridge-memory-decay-unused.service",
    "agent-bridge-memory-decay-unused.timer",
    "agent-bridge-distill.service",
    "agent-bridge-distill.timer",
    "agent-bridge-digest.service",
    "agent-bridge-digest.timer",
    "agent-bridge-day2-audit.service",
    "agent-bridge-day2-audit.timer",
)

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
UTC_TIME = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
SAFE_TARGET_COMPONENT = re.compile(r"^[A-Za-z0-9._-]+$")

MAX_PLAN_BYTES = 1024 * 1024
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
HARD_MAX_FILES = 1_000_000
HARD_MAX_BYTES = 1 << 40  # 1 TiB is an implementation safety ceiling.
BACKUP_BUSY_DEADLINE_SECONDS = 10.0


class MigrationError(RuntimeError):
    """Expected fail-closed rejection."""


@dataclass(frozen=True)
class FileIdentity:
    dev: int
    ino: int
    uid: int
    mode: int

    def as_json(self) -> dict[str, int]:
        return {"dev": self.dev, "ino": self.ino, "mode": self.mode, "uid": self.uid}


@dataclass(frozen=True)
class SourceFile:
    source: str
    target: str
    dev: int
    ino: int
    uid: int
    mode: int
    nlink: int
    size: int
    sha256: str
    validation: str


@dataclass(frozen=True)
class SourceDirectory:
    source: str
    target: str
    dev: int
    ino: int
    uid: int
    mode: int


@dataclass
class PreparedPlan:
    raw: dict[str, Any]
    raw_sha256: str
    identity: FileIdentity
    source_files: list[SourceFile]
    source_directories: list[SourceDirectory]
    target_dirs: set[str]
    sqlite_source: str
    estimated_files: int
    estimated_bytes: int
    source_manifest_digest: str
    mappings_digest: str
    sqlite_preflight_integrity: str


@dataclass
class Context:
    command: str
    root: str
    root_identity: FileIdentity
    script_path: str
    pending_path: str
    pending_identity: FileIdentity
    pending: dict[str, str]
    pending_sha256: str
    plan_path: str
    plan: PreparedPlan
    receipt_path: str
    lock_path: str
    lock_fd: int
    owns_lock_fd: bool


def fail(message: str) -> "NoReturn":  # type: ignore[name-defined]
    raise MigrationError(message)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def domain_digest(domain: bytes, value: Any) -> str:
    return sha256_bytes(domain + canonical_json(value))


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mode_bits(st: os.stat_result) -> int:
    return stat.S_IMODE(st.st_mode)


def identity_from_stat(st: os.stat_result) -> FileIdentity:
    return FileIdentity(st.st_dev, st.st_ino, st.st_uid, mode_bits(st))


def checked_lstat(path: str, label: str) -> os.stat_result:
    try:
        return os.lstat(path)
    except OSError as exc:
        fail(f"cannot inspect {label}: {exc.strerror}")


def require_directory(
    path: str,
    label: str,
    *,
    exact_mode: int | None = None,
    owned: bool = True,
) -> os.stat_result:
    st = checked_lstat(path, label)
    if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
        fail(f"{label} must be a physical directory")
    if owned and st.st_uid != os.geteuid():
        fail(f"{label} must be owned by the effective user")
    if exact_mode is not None and mode_bits(st) != exact_mode:
        fail(f"{label} mode must be exact 0{exact_mode:o}")
    return st


def require_regular(
    path: str,
    label: str,
    *,
    exact_mode: int | None = None,
    owned: bool = True,
    single_link: bool = True,
) -> os.stat_result:
    st = checked_lstat(path, label)
    if not stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode):
        fail(f"{label} must be a physical regular file")
    if owned and st.st_uid != os.geteuid():
        fail(f"{label} must be owned by the effective user")
    if single_link and st.st_nlink != 1:
        fail(f"{label} must have exactly one hard link")
    if exact_mode is not None and mode_bits(st) != exact_mode:
        fail(f"{label} mode must be exact 0{exact_mode:o}")
    return st


def require_legacy_directory(path: str, label: str) -> os.stat_result:
    st = require_directory(path, label, owned=False)
    if st.st_uid not in (0, os.geteuid()):
        fail(f"{label} owner must be root or the effective user")
    return st


def require_legacy_regular(path: str, label: str) -> os.stat_result:
    st = require_regular(path, label, owned=False)
    if st.st_uid not in (0, os.geteuid()):
        fail(f"{label} owner must be root or the effective user")
    return st


def validate_absolute_lexical(path: str, label: str) -> str:
    if not isinstance(path, str) or not path or "\x00" in path:
        fail(f"{label} must be a non-empty path string")
    if not os.path.isabs(path):
        fail(f"{label} must be absolute")
    if path == "/" or os.path.normpath(path) != path or path.endswith("/"):
        fail(f"{label} must be a canonical non-root path")
    return path


def validate_physical_path_components(path: str, label: str) -> None:
    current = "/"
    parts = path.split("/")[1:]
    for part in parts:
        current = os.path.join(current, part)
        st = checked_lstat(current, label)
        if stat.S_ISLNK(st.st_mode):
            fail(f"{label} must not traverse a symlink")


def validate_root(raw: str) -> tuple[str, FileIdentity]:
    root = validate_absolute_lexical(raw, "deployment root")
    validate_physical_path_components(root, "deployment root")
    if os.path.realpath(root) != root:
        fail("deployment root must be a physical canonical path")
    root_st = require_directory(root, "deployment root", exact_mode=0o700)

    # Ancestors may be owned by root or the caller.  A writable ancestor is
    # accepted only when it is the conventional root-owned sticky boundary.
    ancestor = os.path.dirname(root)
    while True:
        st = require_directory(ancestor, "deployment-root ancestor", owned=False)
        if st.st_uid not in (0, os.geteuid()):
            fail("deployment-root ancestor has an untrusted owner")
        mode = mode_bits(st)
        if mode & 0o022 and not (st.st_uid == 0 and mode & stat.S_ISVTX):
            fail("deployment-root ancestor is group/other writable")
        if ancestor == "/":
            break
        ancestor = os.path.dirname(ancestor)
    return root, identity_from_stat(root_st)


def private_subdir(root: str, relative: str, label: str) -> os.stat_result:
    current = root
    for part in relative.split("/"):
        if not part or part in (".", ".."):
            fail(f"invalid private directory path for {label}")
        current = os.path.join(current, part)
        require_directory(current, label, exact_mode=0o700)
    return checked_lstat(current, label)


def read_regular_bytes(
    path: str,
    label: str,
    *,
    exact_mode: int,
    maximum: int,
    owned: bool = True,
) -> tuple[bytes, FileIdentity]:
    st = require_regular(path, label, exact_mode=exact_mode, owned=owned)
    if st.st_size > maximum:
        fail(f"{label} exceeds the bounded size limit")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    if hasattr(os, "O_NOATIME"):
        flags |= os.O_NOATIME
    try:
        fd = os.open(path, flags)
    except PermissionError:
        # O_NOATIME can be denied by unusual filesystems even for the owner.
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        fst = os.fstat(fd)
        if (fst.st_dev, fst.st_ino) != (st.st_dev, st.st_ino):
            fail(f"{label} identity changed while opening")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > maximum:
                fail(f"{label} exceeds the bounded size limit")
            chunks.append(chunk)
        end = os.fstat(fd)
        if (end.st_dev, end.st_ino, end.st_size) != (st.st_dev, st.st_ino, st.st_size):
            fail(f"{label} changed while reading")
        return b"".join(chunks), identity_from_stat(end)
    finally:
        os.close(fd)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json_bytes(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8", "strict")
        return json.loads(text, object_pairs_hook=strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        fail(f"{label} is not strict JSON: {exc}")


def require_exact_keys(value: Any, keys: Iterable[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    expected = set(keys)
    actual = set(value)
    if actual != expected:
        unknown = sorted(actual - expected)
        missing = sorted(expected - actual)
        detail = []
        if unknown:
            detail.append("unknown=" + ",".join(unknown))
        if missing:
            detail.append("missing=" + ",".join(missing))
        fail(f"{label} keys are not exact ({'; '.join(detail)})")
    return value


def require_int(value: Any, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        fail(f"{label} must be an integer in [{minimum}, {maximum}]")
    return value


def sha256_file(path: str, *, expected: os.stat_result | None = None) -> str:
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    if hasattr(os, "O_NOATIME"):
        flags |= os.O_NOATIME
    try:
        fd = os.open(path, flags)
    except PermissionError:
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    digest = hashlib.sha256()
    try:
        before = os.fstat(fd)
        if expected is not None and (before.st_dev, before.st_ino, before.st_size) != (
            expected.st_dev,
            expected.st_ino,
            expected.st_size,
        ):
            fail("file identity changed before hashing")
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            fail("file changed while hashing")
    finally:
        os.close(fd)
    return digest.hexdigest()


def parse_pending(root: str) -> tuple[str, dict[str, str], str, FileIdentity]:
    private_subdir(root, "publisher-state", "publisher state root")
    private_subdir(root, "publisher-state/deploy", "publisher deploy state")
    path = os.path.join(root, "publisher-state/deploy/pending-admission.meta")
    raw, identity = read_regular_bytes(
        path, "publisher pending admission", exact_mode=0o600, maximum=64 * 1024
    )
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeDecodeError:
        fail("publisher pending admission must be ASCII")
    lines = text.splitlines(keepends=True)
    if len(lines) != len(PENDING_KEYS) or any(not line.endswith("\n") for line in lines):
        fail("publisher pending admission must contain exactly 14 newline-terminated fields")
    values: dict[str, str] = {}
    for line, expected_key in zip(lines, PENDING_KEYS):
        prefix = expected_key + "="
        value_line = line[:-1]
        if not value_line.startswith(prefix):
            fail("publisher pending admission schema/order is unknown")
        value = value_line[len(prefix) :]
        if "\r" in value or "\x00" in value:
            fail("publisher pending admission contains an unsafe value")
        values[expected_key] = value

    if values["schema"] != "agent_bridge.publisher_pending_admission.v0":
        fail("publisher pending admission schema mismatch")
    if not SAFE_ID.fullmatch(values["lease_id"]):
        fail("publisher lease id is invalid")
    if not HEX64.fullmatch(values["challenge"]):
        fail("publisher challenge is invalid")
    if not HEX40.fullmatch(values["candidate_commit"]):
        fail("publisher candidate is invalid")
    for key in ("installed_binary_sha256", "installed_assets_sha256"):
        if not HEX64.fullmatch(values[key]):
            fail(f"publisher field {key} is invalid")
    if not values["installed_binary_inode"].isdigit():
        fail("publisher binary inode is invalid")
    if values["installed_binary_mode"] != "755":
        fail("publisher binary mode must be exact 0755")
    if not UTC_TIME.fullmatch(values["installed_at"]):
        fail("publisher install timestamp is invalid")
    if values["fresh_mcp"] != "unverified":
        fail("publisher candidate is not awaiting fresh MCP admission")
    if values["force_reinstall"] not in ("0", "1"):
        fail("publisher force flag is invalid")
    if any(ord(ch) < 0x20 or ord(ch) > 0x7E for ch in values["force_reason"]):
        fail("publisher force reason contains non-printable bytes")

    real = os.path.join(root, "bin/agent-bridge.real")
    adapter = os.path.join(root, "share/ab-tts/audio_embody.py")
    assets = os.path.join(root, "lib/agent-bridge/scripts")
    wrapper = os.path.join(root, "bin/agent-bridge")
    if values["real_path"] != real:
        fail("publisher pending admission names another binary")
    expected_shared = "|".join((real, adapter, assets, wrapper))
    if values["shared_targets"] != expected_shared:
        fail("publisher pending admission shared targets mismatch")
    binary_st = require_regular(real, "publisher-installed binary", exact_mode=0o755)
    if str(binary_st.st_ino) != values["installed_binary_inode"]:
        fail("publisher-installed binary inode drifted")
    if sha256_file(real, expected=binary_st) != values["installed_binary_sha256"]:
        fail("publisher-installed binary digest drifted")
    return path, values, sha256_bytes(raw), identity


def running_script_path() -> str:
    return os.path.realpath(__file__)


def clean_git(root: str, repo: str, args: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    env = {
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "HOME": os.path.join(root, "runtime-state/home"),
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
    }
    command = (
        "/usr/bin/git",
        "--no-pager",
        "-c",
        "core.attributesFile=/dev/null",
        "-c",
        "core.hooksPath=/dev/null",
        "-C",
        repo,
        *args,
    )
    try:
        result = subprocess.run(
            command,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        fail("trusted source git operation failed")
    if result.returncode != 0:
        fail("trusted source git operation failed")
    return result


def validate_source_candidate(root: str, candidate: str) -> str:
    private_subdir(root, "source", "trusted source root")
    repo = os.path.join(root, "source/agent-bridge")
    require_directory(repo, "trusted source repository", exact_mode=0o700)
    require_directory(os.path.join(repo, ".git"), "trusted git metadata", exact_mode=0o700)
    private_subdir(root, "source/agent-bridge/scripts", "trusted source scripts")
    expected_script = os.path.join(repo, "scripts/migrate-trusted-runtime-state.py")
    require_regular(expected_script, "trusted migration script", exact_mode=0o700)
    if running_script_path() != expected_script:
        fail("migration must run from the fixed trusted source path")

    for relative in (
        ".git/info/attributes",
        ".git/info/grafts",
        ".git/objects/info/alternates",
        ".git/objects/info/http-alternates",
    ):
        path = os.path.join(repo, relative)
        if os.path.lexists(path):
            fail("trusted source repository contains a forbidden local override")

    head = clean_git(root, repo, ("rev-parse", "--verify", "HEAD^{commit}")).stdout.decode().strip()
    remote = clean_git(
        root, repo, ("rev-parse", "--verify", "refs/remotes/gitlab/master^{commit}")
    ).stdout.decode().strip()
    if head != candidate or remote != candidate:
        fail("trusted source authority does not equal the publisher candidate")
    urls = clean_git(root, repo, ("config", "--local", "--get-all", "remote.gitlab.url")).stdout
    url_lines = [line.decode("ascii", "strict") for line in urls.splitlines() if line]
    if url_lines != [GITLAB_REMOTE_URL]:
        fail("trusted source GitLab URL is not exact")
    candidate_bytes = clean_git(
        root,
        repo,
        (
            "show",
            "--no-textconv",
            "--no-ext-diff",
            f"{candidate}:scripts/migrate-trusted-runtime-state.py",
        ),
    ).stdout
    installed, _ = read_regular_bytes(
        expected_script, "trusted migration script", exact_mode=0o700, maximum=8 * 1024 * 1024
    )
    if installed != candidate_bytes:
        fail("trusted migration script bytes do not match the publisher candidate")
    return expected_script


def validate_target_relative(value: Any, kind: str) -> str:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        fail("mapping target must be a non-empty relative POSIX path")
    if os.path.normpath(value) != value or value.endswith("/"):
        fail("mapping target must be canonical")
    parts = value.split("/")
    if any(part in ("", ".", "..") or not SAFE_TARGET_COMPONENT.fullmatch(part) for part in parts):
        fail("mapping target contains an unsafe component")
    if parts[0] not in MIGRATABLE_TARGET_LEAVES:
        fail("mapping target enters a reconstructed or security-sensitive runtime leaf")
    lower = parts[-1].lower()
    if is_lock_or_wal_name(lower):
        fail("mapping target may not copy a lock or SQLite WAL/SHM file")
    if kind == "sqlite":
        if value != SQLITE_TARGET:
            fail("SQLite destination is fixed at data/agent-bridge/state.db")
    elif lower.endswith((".db", ".sqlite", ".sqlite3")) or value == SQLITE_TARGET:
        fail("database files may only be migrated by the SQLite mapping")
    return value


def is_lock_or_wal_name(name: str) -> bool:
    lower = name.lower()
    return (
        lower == ".lock"
        or lower.endswith(".lock")
        or lower.endswith("-wal")
        or lower.endswith("-shm")
        or lower.endswith("-journal")
        or "-mj" in lower
    )


def parse_plan(root: str, pending: dict[str, str], pending_sha: str) -> tuple[str, dict[str, Any], str, FileIdentity]:
    private_subdir(root, "config", "trusted config root")
    private_subdir(root, "config/agent-bridge", "trusted Agent Bridge config")
    path = os.path.join(root, "config/agent-bridge/state-migration.json")
    raw_bytes, identity = read_regular_bytes(
        path, "state migration plan", exact_mode=0o600, maximum=MAX_PLAN_BYTES
    )
    raw = parse_json_bytes(raw_bytes, "state migration plan")
    plan = require_exact_keys(
        raw,
        (
            "schema",
            "candidate_commit",
            "pending_admission_sha256",
            "inventory_roots",
            "mappings",
            "limits",
        ),
        "state migration plan",
    )
    if plan["schema"] != PLAN_SCHEMA:
        fail("state migration plan schema mismatch")
    if plan["candidate_commit"] != pending["candidate_commit"]:
        fail("state migration plan candidate does not match pending admission")
    if plan["pending_admission_sha256"] != pending_sha:
        fail("state migration plan pending digest does not match")
    if not isinstance(plan["inventory_roots"], list) or not plan["inventory_roots"]:
        fail("state migration plan requires at least one inventory root")
    if not isinstance(plan["mappings"], list) or not plan["mappings"]:
        fail("state migration plan requires at least one mapping")
    limits = require_exact_keys(
        plan["limits"],
        ("max_files", "max_bytes", "max_file_bytes", "reserve_bytes"),
        "state migration limits",
    )
    require_int(limits["max_files"], "max_files", 1, HARD_MAX_FILES)
    require_int(limits["max_bytes"], "max_bytes", 1, HARD_MAX_BYTES)
    require_int(limits["max_file_bytes"], "max_file_bytes", 1, HARD_MAX_BYTES)
    require_int(limits["reserve_bytes"], "reserve_bytes", 0, HARD_MAX_BYTES)
    if limits["max_file_bytes"] > limits["max_bytes"]:
        fail("max_file_bytes may not exceed max_bytes")

    inventory_paths: set[str] = set()
    for index, item in enumerate(plan["inventory_roots"]):
        inv = require_exact_keys(item, ("path", "leaves"), f"inventory root {index}")
        path_value = validate_absolute_lexical(inv["path"], f"inventory root {index} path")
        if path_value.startswith(root + "/") or path_value == root:
            fail("legacy inventory root must remain outside the trusted deployment root")
        if path_value in inventory_paths:
            fail("duplicate inventory root")
        inventory_paths.add(path_value)
        if not isinstance(inv["leaves"], list):
            fail("inventory leaves must be a list")
        names: set[str] = set()
        for leaf_index, leaf_item in enumerate(inv["leaves"]):
            leaf = require_exact_keys(
                leaf_item, ("name", "decision"), f"inventory leaf {index}:{leaf_index}"
            )
            name = leaf["name"]
            if (
                not isinstance(name, str)
                or name in ("", ".", "..")
                or "/" in name
                or "\x00" in name
            ):
                fail("inventory leaf name must be one immediate path component")
            if name in names:
                fail("duplicate inventory leaf decision")
            names.add(name)
            if leaf["decision"] not in (
                "retain",
                "retire",
                "reconstruct",
                "ignore-infrastructure",
            ):
                fail("inventory leaf decision is unknown")

    sqlite_count = 0
    mapping_pairs: set[tuple[str, str, str]] = set()
    mapping_targets: list[str] = []
    for index, item in enumerate(plan["mappings"]):
        mapping = require_exact_keys(
            item, ("kind", "source", "target", "validation"), f"mapping {index}"
        )
        kind = mapping["kind"]
        if kind not in ("regular", "tree", "sqlite"):
            fail("mapping kind must be regular, tree, or sqlite")
        source = validate_absolute_lexical(mapping["source"], f"mapping {index} source")
        target = validate_target_relative(mapping["target"], kind)
        validation = mapping["validation"]
        allowed_validation = ("sqlite",) if kind == "sqlite" else ("none", "json", "jsonl")
        if validation not in allowed_validation:
            fail("mapping validation is incompatible with its kind")
        pair = (kind, source, target)
        if pair in mapping_pairs:
            fail("duplicate migration mapping")
        mapping_pairs.add(pair)
        for existing_target in mapping_targets:
            if (
                target == existing_target
                or target.startswith(existing_target + "/")
                or existing_target.startswith(target + "/")
            ):
                fail("mapping destinations overlap or duplicate")
        mapping_targets.append(target)
        if kind == "sqlite":
            sqlite_count += 1
    if sqlite_count != 1:
        fail("state migration plan must contain exactly one SQLite mapping")
    return path, plan, sha256_bytes(raw_bytes), identity


def find_inventory_decision(plan: dict[str, Any], source: str) -> tuple[str, str]:
    matches: list[tuple[int, str, str]] = []
    for inventory in plan["inventory_roots"]:
        root = inventory["path"]
        if source == root or not source.startswith(root + "/"):
            continue
        relative = source[len(root) + 1 :]
        immediate = relative.split("/", 1)[0]
        decision = next(
            (leaf["decision"] for leaf in inventory["leaves"] if leaf["name"] == immediate),
            None,
        )
        if decision is not None:
            matches.append((len(root), root, decision))
    if not matches:
        fail("mapping source is not covered by an inventory leaf")
    matches.sort(reverse=True)
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        fail("mapping source has ambiguous inventory ownership")
    return matches[0][1], matches[0][2]


def validate_inventory(plan: dict[str, Any]) -> None:
    mapped_leaves: dict[tuple[str, str], list[str]] = {}
    for mapping in plan["mappings"]:
        inventory_root, decision = find_inventory_decision(plan, mapping["source"])
        relative = mapping["source"][len(inventory_root) + 1 :]
        leaf = relative.split("/", 1)[0]
        if relative != leaf:
            fail("mapping source must equal its retained immediate inventory leaf")
        if decision != "retain":
            fail("only inventory leaves marked retain may be mapped")
        mapped_leaves.setdefault((inventory_root, leaf), []).append(mapping["kind"])

    for index, inventory in enumerate(plan["inventory_roots"]):
        root = inventory["path"]
        validate_physical_path_components(root, f"inventory root {index}")
        require_legacy_directory(root, f"inventory root {index}")
        try:
            actual = {entry.name for entry in os.scandir(root)}
        except OSError as exc:
            fail(f"cannot enumerate inventory root {index}: {exc.strerror}")
        declared = {leaf["name"] for leaf in inventory["leaves"]}
        unknown = actual - declared
        required = {
            leaf["name"]
            for leaf in inventory["leaves"]
            if leaf["decision"] != "reconstruct"
        }
        if unknown or not required.issubset(actual):
            fail("inventory root has an unknown, missing, or newly appeared immediate leaf")
        for leaf in inventory["leaves"]:
            key = (root, leaf["name"])
            mappings = mapped_leaves.get(key, [])
            if leaf["decision"] == "retain" and len(mappings) != 1:
                fail("every retained inventory leaf requires exactly one root mapping")
            if leaf["decision"] != "retain" and mappings:
                fail("non-retained inventory leaf may not be mapped")
            if leaf["decision"] == "retain":
                leaf_path = os.path.join(root, leaf["name"])
                leaf_st = checked_lstat(leaf_path, "retained inventory leaf")
                if stat.S_ISDIR(leaf_st.st_mode) and not stat.S_ISLNK(leaf_st.st_mode):
                    if mappings != ["tree"]:
                        fail("retained directory leaf requires one tree mapping")
                elif stat.S_ISREG(leaf_st.st_mode) and not stat.S_ISLNK(leaf_st.st_mode):
                    if mappings[0] not in ("regular", "sqlite"):
                        fail("retained regular leaf requires one regular/sqlite mapping")
                else:
                    fail("retained inventory leaf must be a physical regular file or directory")


def validate_json_file(path: str, mode: str) -> None:
    if mode == "none":
        return
    st = require_legacy_regular(path, "structured sidecar source")
    if st.st_size > MAX_PLAN_BYTES * 64:
        fail("structured sidecar is too large to parse safely")
    raw, _ = read_regular_bytes(
        path,
        "structured sidecar source",
        exact_mode=mode_bits(st),
        maximum=st.st_size + 1,
        owned=False,
    )
    if mode == "json":
        parse_json_bytes(raw, "JSON sidecar")
        return
    if mode != "jsonl":
        fail("unknown sidecar validation mode")
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        parse_json_bytes(line, f"JSONL sidecar line {line_number}")


def validate_source_file(path: str, label: str, max_file_bytes: int) -> tuple[os.stat_result, str]:
    st = require_legacy_regular(path, label)
    if st.st_size > max_file_bytes:
        fail(f"{label} exceeds max_file_bytes")
    name = os.path.basename(path)
    if is_lock_or_wal_name(name):
        fail(f"{label} is a lock or SQLite WAL/SHM file and may not be copied")
    if name.lower().endswith((".db", ".sqlite", ".sqlite3")):
        fail(f"{label} looks like a database and may not be raw-copied")
    return st, sha256_file(path, expected=st)


def walk_source_tree(
    path: str, max_file_bytes: int
) -> tuple[list[tuple[str, os.stat_result]], list[tuple[str, os.stat_result, str]]]:
    root_st = require_legacy_directory(path, "sidecar tree source")
    directories: list[tuple[str, os.stat_result]] = [("", root_st)]
    files: list[tuple[str, os.stat_result, str]] = []
    stack: list[tuple[str, str]] = [(path, "")]
    while stack:
        absolute, relative = stack.pop()
        try:
            entries = sorted(os.scandir(absolute), key=lambda entry: entry.name, reverse=True)
        except OSError as exc:
            fail(f"cannot enumerate sidecar tree: {exc.strerror}")
        for entry in entries:
            child_rel = entry.name if not relative else relative + "/" + entry.name
            child = os.path.join(absolute, entry.name)
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError as exc:
                fail(f"cannot inspect sidecar tree entry: {exc.strerror}")
            if st.st_uid not in (0, os.geteuid()):
                fail("sidecar tree entry has an untrusted owner")
            if stat.S_ISLNK(st.st_mode):
                fail("sidecar tree may not contain symlinks")
            if stat.S_ISDIR(st.st_mode):
                directories.append((child_rel, st))
                stack.append((child, child_rel))
            elif stat.S_ISREG(st.st_mode):
                if st.st_nlink != 1:
                    fail("sidecar tree file must have exactly one hard link")
                if st.st_size > max_file_bytes:
                    fail("sidecar tree file exceeds max_file_bytes")
                if is_lock_or_wal_name(entry.name):
                    fail("sidecar tree may not raw-copy lock or SQLite WAL/SHM files")
                if entry.name.lower().endswith((".db", ".sqlite", ".sqlite3")):
                    fail("sidecar tree may not raw-copy database files")
                files.append((child_rel, st, sha256_file(child, expected=st)))
            else:
                fail("sidecar tree may contain only physical directories and regular files")
    files.sort(key=lambda value: value[0])
    directories.sort(key=lambda value: value[0])
    return directories, files


def sqlite_uri(path: str, *, immutable: bool) -> str:
    suffix = "?mode=ro&immutable=1" if immutable else "?mode=ro"
    return "file:" + quote(path, safe="/") + suffix


def sqlite_integrity(path: str, *, immutable: bool) -> None:
    try:
        connection = sqlite3.connect(sqlite_uri(path, immutable=immutable), uri=True, timeout=0.0)
        try:
            connection.execute("PRAGMA query_only=ON")
            rows = connection.execute("PRAGMA integrity_check").fetchall()
        finally:
            connection.close()
    except sqlite3.Error:
        fail("SQLite integrity check could not be completed")
    if rows != [("ok",)]:
        fail("SQLite integrity check did not return exactly ok")


def require_sqlite_family_absent(path: str, label: str) -> None:
    for suffix in SQLITE_SIDECAR_SUFFIXES:
        family = path + suffix
        if os.path.lexists(family):
            fail(f"{label} must have no SQLite {suffix[1:].upper()} sidecar")
    require_sqlite_super_journals_absent(path, label)


def require_sqlite_super_journals_absent(path: str, label: str) -> None:
    parent = os.path.dirname(path)
    prefix = os.path.basename(path) + "-mj"
    try:
        entries = os.scandir(parent)
    except OSError:
        fail(f"cannot enumerate {label} parent for SQLite super-journals")
    with entries:
        if any(entry.name.startswith(prefix) for entry in entries):
            fail(f"{label} must have no SQLite super-journal")


def validate_sqlite_family(
    path: str, max_file_bytes: int, *, stable_source: bool
) -> tuple[int, int, str]:
    db_st = require_legacy_regular(path, "legacy SQLite database")
    if db_st.st_size > max_file_bytes:
        fail("legacy SQLite database exceeds max_file_bytes")
    total = db_st.st_size
    family_present: dict[str, bool] = {}
    for suffix in SQLITE_SIDECAR_SUFFIXES:
        family = path + suffix
        family_present[suffix] = os.path.lexists(family)
        if not os.path.lexists(family):
            continue
        st = require_legacy_regular(family, f"legacy SQLite {suffix[1:].upper()} file")
        if st.st_size > max_file_bytes:
            fail("legacy SQLite family member exceeds max_file_bytes")
        total += st.st_size
    if family_present["-journal"]:
        fail("legacy SQLite rollback journal must be absent before migration")
    require_sqlite_super_journals_absent(path, "legacy SQLite database")
    if stable_source:
        # verify/replay must remain read-only and must not let immutable mode
        # hide a writer-created WAL.  Absence is proven before opening SQLite.
        require_sqlite_family_absent(path, "stable legacy SQLite database")
        sqlite_integrity(path, immutable=True)
        integrity_state = "ok_immutable"
    else:
        # Opening a WAL database even with mode=ro can create or modify -shm.
        # Therefore preflight is byte-passive: logical integrity is deferred
        # until the explicitly confirmed RW checkpoint/backup transaction.
        if family_present["-wal"]:
            integrity_state = "deferred_wal_to_confirmed_migrate"
        else:
            if family_present["-shm"]:
                fail("legacy SQLite SHM may not exist without a WAL")
            sqlite_integrity(path, immutable=True)
            integrity_state = "ok_immutable"
    return 1, total, integrity_state


def prepare_plan(
    plan: dict[str, Any], raw_sha: str, identity: FileIdentity, *, stable_source: bool
) -> PreparedPlan:
    validate_inventory(plan)
    limits = plan["limits"]
    max_file_bytes = limits["max_file_bytes"]
    source_files_by_target: dict[str, SourceFile] = {}
    source_directories_by_target: dict[str, SourceDirectory] = {}
    target_dirs: set[str] = set(RUNTIME_LEAVES)
    sqlite_source = ""
    sqlite_preflight_integrity = ""
    estimated_files = 0
    estimated_bytes = 0
    source_records: list[dict[str, Any]] = []

    def add_parent_dirs(target: str) -> None:
        parts = target.split("/")[:-1]
        current = ""
        for part in parts:
            current = part if not current else current + "/" + part
            if current in source_files_by_target:
                fail("mapping target has a file/directory collision")
            target_dirs.add(current)

    def add_file(source: str, target: str, validation: str, st: os.stat_result, digest: str) -> None:
        nonlocal estimated_files, estimated_bytes
        if target in target_dirs:
            fail("mapping target has a directory/file collision")
        add_parent_dirs(target)
        candidate = SourceFile(
            source,
            target,
            st.st_dev,
            st.st_ino,
            st.st_uid,
            mode_bits(st),
            st.st_nlink,
            st.st_size,
            digest,
            validation,
        )
        existing = source_files_by_target.get(target)
        if existing is not None:
            fail("duplicate sidecar destination is forbidden even for identical bytes")
        source_files_by_target[target] = candidate
        estimated_files += 1
        estimated_bytes += st.st_size
        source_records.append(
            {
                "dev": st.st_dev,
                "ino": st.st_ino,
                "kind": "sidecar",
                "mode": mode_bits(st),
                "nlink": st.st_nlink,
                "sha256": digest,
                "size": st.st_size,
                "source": source,
                "target": target,
                "uid": st.st_uid,
            }
        )

    def add_source_directory(source: str, target: str, st: os.stat_result) -> None:
        if target in source_directories_by_target:
            fail("duplicate sidecar directory destination is forbidden")
        source_directories_by_target[target] = SourceDirectory(
            source,
            target,
            st.st_dev,
            st.st_ino,
            st.st_uid,
            mode_bits(st),
        )
        source_records.append(
            {
                "dev": st.st_dev,
                "ino": st.st_ino,
                "kind": "sidecar_directory",
                "mode": mode_bits(st),
                "source": source,
                "target": target,
                "uid": st.st_uid,
            }
        )

    for mapping in plan["mappings"]:
        kind = mapping["kind"]
        source = mapping["source"]
        target = mapping["target"]
        validation = mapping["validation"]
        validate_physical_path_components(source, "mapping source")
        if kind == "sqlite":
            if sqlite_source:
                fail("multiple SQLite mappings are forbidden")
            count, size, sqlite_preflight_integrity = validate_sqlite_family(
                source, max_file_bytes, stable_source=stable_source
            )
            sqlite_source = source
            estimated_files += count
            estimated_bytes += size
            add_parent_dirs(target)
            source_records.append(
                {
                    "kind": "sqlite",
                    "sha256": sha256_file(source),
                    "size": checked_lstat(source, "legacy SQLite database").st_size,
                    "target": target,
                }
            )
            continue
        if kind == "regular":
            st, digest = validate_source_file(source, "regular sidecar source", max_file_bytes)
            validate_json_file(source, validation)
            add_file(source, target, validation, st, digest)
            continue

        directories, files = walk_source_tree(source, max_file_bytes)
        if target in source_files_by_target:
            fail("mapping target has a file/directory collision")
        target_dirs.add(target)
        add_parent_dirs(target + "/placeholder")
        for relative, directory_st in directories:
            destination = target if not relative else target + "/" + relative
            if destination in source_files_by_target:
                fail("tree mapping directory collides with a target file")
            target_dirs.add(destination)
            source_directory = source if not relative else os.path.join(
                source, *relative.split("/")
            )
            add_source_directory(source_directory, destination, directory_st)
        for relative, st, digest in files:
            source_file = os.path.join(source, *relative.split("/"))
            destination = target + "/" + relative
            validate_json_file(source_file, validation)
            add_file(source_file, destination, validation, st, digest)

    if not sqlite_source:
        fail("prepared plan has no SQLite source")
    if estimated_files > limits["max_files"]:
        fail("migration inventory exceeds max_files")
    if estimated_bytes > limits["max_bytes"]:
        fail("migration inventory exceeds max_bytes")
    source_records.sort(
        key=lambda value: (value["target"], value["kind"], value.get("sha256", ""))
    )
    return PreparedPlan(
        raw=plan,
        raw_sha256=raw_sha,
        identity=identity,
        source_files=sorted(source_files_by_target.values(), key=lambda value: value.target),
        source_directories=sorted(
            source_directories_by_target.values(), key=lambda value: value.target
        ),
        target_dirs=target_dirs,
        sqlite_source=sqlite_source,
        estimated_files=estimated_files,
        estimated_bytes=estimated_bytes,
        source_manifest_digest=domain_digest(SOURCE_MANIFEST_DOMAIN, source_records),
        mappings_digest=domain_digest(MAPPINGS_DOMAIN, plan["mappings"]),
        sqlite_preflight_integrity=sqlite_preflight_integrity,
    )


def refresh_retained_sources(context: Context) -> PreparedPlan:
    """Re-enumerate and rehash every retained source from physical paths."""

    fresh = prepare_plan(
        context.plan.raw,
        context.plan.raw_sha256,
        context.plan.identity,
        stable_source=True,
    )
    if (
        fresh.source_files != context.plan.source_files
        or fresh.source_directories != context.plan.source_directories
        or fresh.target_dirs != context.plan.target_dirs
        or fresh.sqlite_source != context.plan.sqlite_source
        or fresh.mappings_digest != context.plan.mappings_digest
    ):
        fail("retained sidecar identity, metadata, inventory, or digest drifted")
    return fresh


def assert_source_inputs_stable(
    context: Context,
    expected_database: dict[str, Any],
    expected_manifest_digest: str,
) -> None:
    source = context.plan.sqlite_source
    require_sqlite_family_absent(source, "post-checkpoint legacy SQLite database")
    source_st = require_legacy_regular(source, "post-checkpoint legacy SQLite database")
    if db_fact(source, source_st) != expected_database:
        fail("post-checkpoint legacy SQLite database fact drifted")
    sqlite_integrity(source, immutable=True)
    fresh = refresh_retained_sources(context)
    if fresh.source_manifest_digest != expected_manifest_digest:
        fail("post-checkpoint source manifest drifted")


def runtime_skeleton(root: str) -> str:
    path = os.path.join(root, "runtime-state")
    require_directory(path, "runtime-state skeleton", exact_mode=0o700)
    actual = set(os.listdir(path))
    if actual != set(RUNTIME_LEAVES):
        fail("runtime-state must be the publisher's exact empty skeleton")
    for leaf in RUNTIME_LEAVES:
        leaf_path = os.path.join(path, leaf)
        require_directory(leaf_path, f"runtime-state skeleton leaf {leaf}", exact_mode=0o700)
        if os.listdir(leaf_path):
            fail("runtime-state publisher skeleton must be empty before first migration")
    return path


def query_unit_state(unit: str) -> dict[str, str]:
    env = {
        "HOME": "/nonexistent",
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
        "XDG_RUNTIME_DIR": f"/run/user/{os.geteuid()}",
    }
    properties = (
        ("LoadState", "ActiveState", "SubState", "UnitFileState")
        if unit.endswith(".timer")
        else ("LoadState", "ActiveState", "SubState", "MainPID")
    )
    command = (
        "/usr/bin/systemctl",
        "--user",
        "show",
        unit,
        *(f"--property={name}" for name in properties),
        "--no-pager",
    )
    try:
        result = subprocess.run(
            command,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=15,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        fail("cannot query the fixed systemd user-unit gate")
    if result.returncode != 0:
        fail("cannot query the fixed systemd user-unit gate")
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            fail("systemd returned an unknown unit-state shape")
        key, value = line.split("=", 1)
        if key in values or key not in properties:
            fail("systemd returned duplicate or unknown unit-state fields")
        values[key] = value
    if set(values) != set(properties):
        fail("systemd omitted a required unit-state field")
    return values


def collect_quiescence() -> list[dict[str, Any]]:
    baseline: list[dict[str, Any]] = []
    for unit in UNITS:
        values = query_unit_state(unit)
        if values["ActiveState"] != "inactive" or values["SubState"] != "dead":
            fail(f"required unit is not fully quiesced: {unit}")
        if unit.endswith(".timer"):
            timer_shape = (values["LoadState"], values["UnitFileState"])
            timer_disabled = timer_shape in (
                ("loaded", "disabled"),
                ("masked", "masked"),
                ("not-found", ""),
            )
            if not timer_disabled:
                fail(f"required timer remains enabled or triggerable: {unit}")
            baseline.append(
                {
                    "active_state": values["ActiveState"],
                    "load_state": values["LoadState"],
                    "name": unit,
                    "sub_state": values["SubState"],
                    "type": "timer",
                    "unit_file_state": values["UnitFileState"],
                }
            )
        elif values["MainPID"] != "0":
            fail(f"required service still has a MainPID: {unit}")
        else:
            baseline.append(
                {
                    "active_state": values["ActiveState"],
                    "load_state": values["LoadState"],
                    "main_pid": 0,
                    "name": unit,
                    "sub_state": values["SubState"],
                    "type": "service",
                }
            )
    return baseline


def check_quiescence() -> None:
    collect_quiescence()


def db_family_paths(source: str, destination: str) -> set[str]:
    result: set[str] = set()
    for base in (source, destination):
        for suffix in SQLITE_FAMILY_SUFFIXES:
            result.add(base + suffix)
    return result


def read_bounded_proc_at(directory_fd: int, name: str, maximum: int = 64 * 1024) -> bytes:
    if name not in ("status", "cmdline", "cgroup"):
        fail("unknown proc identity file")
    fd = os.open(
        name,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        dir_fd=directory_fd,
    )
    try:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(4096, maximum - total + 1))
            if not chunk:
                return b"".join(chunks)
            total += len(chunk)
            if total > maximum:
                fail("proc identity file exceeds its bounded size")
            chunks.append(chunk)
    finally:
        os.close(fd)


def open_proc_pid_directory(pid: int, proc_root: str = "/proc") -> int:
    root_fd = os.open(
        proc_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        return os.open(
            str(pid),
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=root_fd,
        )
    finally:
        os.close(root_fd)


def proc_identity_from_fd(
    pid: int, directory_fd: int
) -> tuple[dict[str, str], list[bytes], list[str]] | None:
    try:
        status_raw = read_bounded_proc_at(directory_fd, "status")
        cmdline_raw = read_bounded_proc_at(directory_fd, "cmdline")
        cgroup_raw = read_bounded_proc_at(directory_fd, "cgroup")
        status = status_raw.decode("ascii", "strict")
        cgroup = cgroup_raw.decode("ascii", "strict")
        arguments = [part for part in cmdline_raw.split(b"\0") if part]
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError, UnicodeDecodeError):
        return None
    fields: dict[str, str] = {}
    for line in status.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key in fields:
            return None
        fields[key] = value.strip()
    if fields.get("Pid") != str(pid) or fields.get("Tgid") != str(pid):
        return None
    return fields, arguments, cgroup.splitlines()


def is_exact_user_systemd_manager_fd(pid: int, directory_fd: int) -> bool:
    """Recognize the sole Yama-hidden user manager from one pinned proc dir."""

    identity = proc_identity_from_fd(pid, directory_fd)
    if identity is None:
        return False
    fields, arguments, cgroup_lines = identity
    uid_text = str(os.geteuid())
    if (
        fields.get("Name") != "systemd"
        or fields.get("Uid", "").split() != [uid_text] * 4
        or fields.get("PPid") != "1"
    ):
        return False
    if arguments != [b"/usr/lib/systemd/systemd", b"--user"]:
        return False
    expected_cgroup = (
        f"0::/user.slice/user-{uid_text}.slice/user@{uid_text}.service/init.scope"
    )
    return expected_cgroup in cgroup_lines


def is_exact_user_systemd_manager(pid: int, proc_root: str = "/proc") -> bool:
    try:
        directory_fd = open_proc_pid_directory(pid, proc_root)
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        return False
    try:
        return is_exact_user_systemd_manager_fd(pid, directory_fd)
    finally:
        os.close(directory_fd)


def is_exact_user_manager_infrastructure_fd(
    pid: int, directory_fd: int, proc_root: str = "/proc"
) -> bool:
    if is_exact_user_systemd_manager_fd(pid, directory_fd):
        return True
    identity = proc_identity_from_fd(pid, directory_fd)
    if identity is None:
        return False
    fields, arguments, cgroup_lines = identity
    uid_text = str(os.geteuid())
    parent = fields.get("PPid", "")
    if (
        fields.get("Name") != "(sd-pam)"
        or fields.get("Uid", "").split() != [uid_text] * 4
        or not parent.isdigit()
        or arguments != [b"(sd-pam)"]
    ):
        return False
    expected_cgroup = (
        f"0::/user.slice/user-{uid_text}.slice/user@{uid_text}.service/init.scope"
    )
    return expected_cgroup in cgroup_lines and is_exact_user_systemd_manager(
        int(parent), proc_root
    )


def is_exact_user_manager_infrastructure(pid: int, proc_root: str = "/proc") -> bool:
    try:
        directory_fd = open_proc_pid_directory(pid, proc_root)
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        return False
    try:
        return is_exact_user_manager_infrastructure_fd(pid, directory_fd, proc_root)
    finally:
        os.close(directory_fd)


def scan_open_fds(paths: set[str], pid_inventory: Iterable[int] | None = None) -> None:
    wanted = {os.path.normpath(path) for path in paths}
    database_bases = {
        path
        for path in wanted
        if not path.endswith(("-wal", "-shm", "-journal"))
    }
    super_journal_prefixes = {path + "-mj" for path in database_bases}
    own_pid = os.getpid()
    euid = os.geteuid()
    if pid_inventory is None:
        try:
            with os.scandir("/proc") as entries:
                pids = [int(entry.name) for entry in entries if entry.name.isdigit()]
        except OSError:
            fail("cannot enumerate /proc for open database descriptors")
    else:
        pids = list(pid_inventory)
    for pid in pids:
        if type(pid) is not int or pid <= 0:
            fail("injected proc PID inventory is invalid")
        if pid == own_pid:
            continue
        try:
            proc_fd = open_proc_pid_directory(pid)
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            try:
                st = os.stat(f"/proc/{pid}", follow_symlinks=False)
            except (FileNotFoundError, ProcessLookupError):
                continue
            except PermissionError:
                fail("cannot determine the owner of an unreadable proc directory")
            if st.st_uid == euid:
                fail("cannot pin a same-UID proc directory")
            continue
        except OSError:
            fail("cannot pin a proc directory for descriptor inspection")
        try:
            proc_st = os.fstat(proc_fd)
            if proc_st.st_uid != euid:
                continue
            try:
                fd_dir = os.open(
                    "fd",
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=proc_fd,
                )
            except (FileNotFoundError, ProcessLookupError):
                continue
            except PermissionError:
                if is_exact_user_manager_infrastructure_fd(pid, proc_fd):
                    continue
                fail("cannot inspect a non-manager same-UID process descriptor table")
            try:
                with os.scandir(fd_dir) as descriptors:
                    for descriptor in descriptors:
                        try:
                            target = os.readlink(descriptor.name, dir_fd=fd_dir)
                        except (FileNotFoundError, ProcessLookupError):
                            continue
                        except PermissionError:
                            if is_exact_user_manager_infrastructure_fd(pid, proc_fd):
                                continue
                            fail("cannot inspect a non-manager same-UID process descriptor")
                        if target.endswith(" (deleted)"):
                            target = target[: -len(" (deleted)")]
                        if os.path.isabs(target):
                            normalized = os.path.normpath(target)
                            if normalized in wanted or any(
                                normalized.startswith(prefix)
                                for prefix in super_journal_prefixes
                            ):
                                fail(
                                    "an external process still holds a legacy or destination SQLite descriptor"
                                )
            finally:
                os.close(fd_dir)
        finally:
            os.close(proc_fd)


def check_runtime_gates(plan: PreparedPlan, root: str) -> None:
    check_quiescence()
    destination = os.path.join(root, "runtime-state", SQLITE_TARGET)
    scan_open_fds(db_family_paths(plan.sqlite_source, destination))


def free_bytes(path: str) -> int:
    values = os.statvfs(path)
    return values.f_bavail * values.f_frsize


def check_capacity(plan: PreparedPlan, root: str, estimated_bytes: int | None = None) -> None:
    estimate = plan.estimated_bytes if estimated_bytes is None else estimated_bytes
    required = estimate * 2 + plan.raw["limits"]["reserve_bytes"]
    if required > HARD_MAX_BYTES * 3:
        fail("migration capacity requirement exceeds the implementation ceiling")
    if free_bytes(os.path.join(root, "runtime-state")) < required:
        fail("destination filesystem lacks stage plus rollback reserve capacity")


def acquire_lock(path: str, inherited_fd: int | None) -> tuple[int, bool]:
    st = require_regular(path, "publisher kernel lock", exact_mode=0o600)
    if inherited_fd is None:
        try:
            fd = os.open(path, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
        except OSError:
            fail("cannot open publisher kernel lock")
        owns = True
    else:
        if inherited_fd < 3:
            fail("inherited publisher lock fd must be at least 3")
        fd = inherited_fd
        owns = False
    try:
        fst = os.fstat(fd)
    except OSError:
        if owns:
            os.close(fd)
        fail("cannot fstat publisher kernel lock descriptor")
    if not stat.S_ISREG(fst.st_mode):
        if owns:
            os.close(fd)
        fail("publisher kernel lock descriptor is not regular")
    if (
        fst.st_dev,
        fst.st_ino,
        fst.st_uid,
        mode_bits(fst),
    ) != (st.st_dev, st.st_ino, os.geteuid(), 0o600):
        if owns:
            os.close(fd)
        fail("publisher kernel lock descriptor does not match the fixed lock path")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        if owns:
            os.close(fd)
        fail("publisher kernel lock is busy or not inherited from its owner")
    # Re-check after flock; pathname replacement after open is forbidden.
    validate_lock(path, fd)
    return fd, owns


def validate_lock(path: str, fd: int) -> None:
    st = require_regular(path, "publisher kernel lock", exact_mode=0o600)
    try:
        fst = os.fstat(fd)
    except OSError:
        fail("publisher kernel lock descriptor became invalid")
    if (
        fst.st_dev,
        fst.st_ino,
        fst.st_uid,
        mode_bits(fst),
    ) != (st.st_dev, st.st_ino, os.geteuid(), 0o600):
        fail("publisher kernel lock identity drifted")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fail("publisher kernel lock ownership drifted")


def build_context(command: str, deploy_root: str, inherited_lock_fd: int | None) -> Context:
    root, root_identity = validate_root(deploy_root)
    if inherited_lock_fd is not None and command != "verify":
        fail("--inherited-lock-fd is accepted only by verify")
    pending_path, pending, pending_sha, pending_identity = parse_pending(root)
    script_path = validate_source_candidate(root, pending["candidate_commit"])
    plan_path, raw_plan, plan_sha, plan_identity = parse_plan(root, pending, pending_sha)
    receipt_path = os.path.join(root, "publisher-state/migrations/current.json")
    prepared = prepare_plan(
        raw_plan,
        plan_sha,
        plan_identity,
        stable_source=(command == "verify" or os.path.lexists(receipt_path)),
    )
    lock_path = os.path.join(root, "publisher-state/deploy/publisher.kernel.lock")
    lock_fd, owns_lock = acquire_lock(lock_path, inherited_lock_fd)
    context = Context(
        command=command,
        root=root,
        root_identity=root_identity,
        script_path=script_path,
        pending_path=pending_path,
        pending_identity=pending_identity,
        pending=pending,
        pending_sha256=pending_sha,
        plan_path=plan_path,
        plan=prepared,
        receipt_path=receipt_path,
        lock_path=lock_path,
        lock_fd=lock_fd,
        owns_lock_fd=owns_lock,
    )
    try:
        revalidate_bindings(context)
        check_runtime_gates(context.plan, root)
        receipt_already_exists = os.path.lexists(
            os.path.join(root, "publisher-state/migrations/current.json")
        )
        if command == "preflight" or (command == "migrate" and not receipt_already_exists):
            check_capacity(context.plan, root)
    except BaseException:
        if owns_lock:
            os.close(lock_fd)
        raise
    return context


def revalidate_bindings(context: Context) -> None:
    root_st = require_directory(context.root, "deployment root", exact_mode=0o700)
    if identity_from_stat(root_st) != context.root_identity:
        fail("deployment root identity drifted")
    validate_lock(context.lock_path, context.lock_fd)
    pending_path, pending, pending_sha, pending_identity = parse_pending(context.root)
    if (
        pending_path != context.pending_path
        or pending_identity != context.pending_identity
        or pending_sha != context.pending_sha256
        or pending != context.pending
    ):
        fail("publisher pending admission drifted")
    validate_source_candidate(context.root, context.pending["candidate_commit"])
    plan_path, plan, plan_sha, plan_identity = parse_plan(
        context.root, context.pending, context.pending_sha256
    )
    if (
        plan_path != context.plan_path
        or plan_identity != context.plan.identity
        or plan_sha != context.plan.raw_sha256
        or plan != context.plan.raw
    ):
        fail("state migration plan drifted")


def transaction_id(context: Context) -> str:
    material = {
        "candidate_commit": context.pending["candidate_commit"],
        "deploy_root": context.root_identity.as_json(),
        "pending_admission_sha256": context.pending_sha256,
        "plan_sha256": context.plan.raw_sha256,
    }
    return domain_digest(TRANSACTION_DOMAIN, material)


def stable_result(command: str, status: str, **fields: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"command": command, "schema": RESULT_SCHEMA, "status": status}
    result.update(fields)
    return result


def make_private_dir(path: str) -> None:
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        fail("private migration path already exists")
    os.chmod(path, 0o700, follow_symlinks=False)


def ensure_migrations_dir(root: str) -> str:
    parent = os.path.join(root, "publisher-state")
    require_directory(parent, "publisher state root", exact_mode=0o700)
    path = os.path.join(parent, "migrations")
    if not os.path.lexists(path):
        make_private_dir(path)
        fsync_dir(parent)
    require_directory(path, "publisher migration state", exact_mode=0o700)
    return path


def fsync_dir(path: str) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def fsync_regular(path: str) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            fail("refusing to fsync a non-regular or hardlinked stage file")
        os.fsync(fd)
    finally:
        os.close(fd)


def fsync_tree(path: str) -> None:
    require_directory(path, "migration fsync tree", exact_mode=0o700)
    child_directories: list[str] = []
    with os.scandir(path) as entries:
        for entry in entries:
            child = os.path.join(path, entry.name)
            st = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                child_directories.append(child)
            elif stat.S_ISREG(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                fsync_regular(child)
            else:
                fail("migration stage contains a symlink or special file before fsync")
    for child in sorted(child_directories):
        fsync_tree(child)
    fsync_dir(path)


def create_stage(root: str, txid: str) -> str:
    path = os.path.join(root, "runtime-state.migration-stage." + txid[:24])
    if os.path.lexists(path):
        fail("deterministic migration stage already exists; manual recovery is required")
    make_private_dir(path)
    for leaf in RUNTIME_LEAVES:
        make_private_dir(os.path.join(path, leaf))
    fsync_dir(path)
    fsync_dir(root)
    return path


def ensure_stage_directories(stage: str, directories: Iterable[str]) -> None:
    for relative in sorted(set(directories), key=lambda value: (value.count("/"), value)):
        path = os.path.join(stage, *relative.split("/"))
        if os.path.lexists(path):
            require_directory(path, "migration stage directory", exact_mode=0o700)
            continue
        parent = os.path.dirname(path)
        require_directory(parent, "migration stage parent", exact_mode=0o700)
        make_private_dir(path)


def copy_file_exact(source: SourceFile, stage: str) -> None:
    target = os.path.join(stage, *source.target.split("/"))
    parent = os.path.dirname(target)
    require_directory(parent, "migration stage target parent", exact_mode=0o700)
    if os.path.lexists(target):
        fail("duplicate sidecar destination appeared in the private stage")
    source_st = require_legacy_regular(source.source, "sidecar copy source")
    observed_identity = (
        source_st.st_dev,
        source_st.st_ino,
        source_st.st_uid,
        mode_bits(source_st),
        source_st.st_nlink,
        source_st.st_size,
    )
    expected_identity = (
        source.dev,
        source.ino,
        source.uid,
        source.mode,
        source.nlink,
        source.size,
    )
    if (
        observed_identity != expected_identity
        or sha256_file(source.source, expected=source_st) != source.sha256
    ):
        fail("sidecar source drifted after preflight")
    source_fd = os.open(source.source, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    target_fd = os.open(
        target,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
    )
    digest = hashlib.sha256()
    total = 0
    try:
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            view = memoryview(chunk)
            while view:
                written = os.write(target_fd, view)
                view = view[written:]
            digest.update(chunk)
            total += len(chunk)
        os.fchmod(target_fd, 0o600)
        os.fsync(target_fd)
    finally:
        os.close(target_fd)
        os.close(source_fd)
    if total != source.size or digest.hexdigest() != source.sha256:
        fail("sidecar copy digest mismatch")


def sqlite_checkpoint_and_backup(
    source: str, target: str
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    source_st_before = require_legacy_regular(source, "legacy SQLite database")
    source_sha_before = sha256_file(source, expected=source_st_before)
    connection: sqlite3.Connection | None = None
    destination: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(source, timeout=0.0, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=0")
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        if integrity != [("ok",)]:
            fail("legacy SQLite integrity check did not return exactly ok")
        checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if checkpoint is None or len(checkpoint) != 3 or checkpoint[0] != 0:
            fail("legacy SQLite WAL checkpoint was busy")
        check_runtime_gate_during_sqlite()
        destination = sqlite3.connect(target, timeout=0.0, isolation_level=None)
        destination.execute("PRAGMA journal_mode=DELETE")
        deadline = time.monotonic() + BACKUP_BUSY_DEADLINE_SECONDS

        def progress(status: int, _remaining: int, _total: int) -> None:
            if status in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) and time.monotonic() > deadline:
                raise MigrationError("SQLite backup remained busy beyond its bounded deadline")

        connection.backup(destination, pages=256, progress=progress, sleep=0.01)
        target_integrity = destination.execute("PRAGMA integrity_check").fetchall()
        if target_integrity != [("ok",)]:
            fail("staged SQLite integrity check did not return exactly ok")
        destination.close()
        destination = None
        connection.close()
        connection = None
    except MigrationError:
        raise
    except sqlite3.Error:
        fail("SQLite checkpoint or backup failed")
    finally:
        if destination is not None:
            destination.close()
        if connection is not None:
            connection.close()
    os.chmod(target, 0o600, follow_symlinks=False)
    for suffix in SQLITE_SIDECAR_SUFFIXES:
        family = target + suffix
        if os.path.lexists(family):
            fail("staged SQLite backup left a journal/WAL/SHM sidecar")
    require_sqlite_super_journals_absent(target, "staged SQLite backup")
    require_sqlite_family_absent(source, "checkpointed legacy SQLite database")
    sqlite_integrity(source, immutable=True)
    sqlite_integrity(target, immutable=True)
    source_st = require_legacy_regular(source, "checkpointed legacy SQLite database")
    target_st = require_regular(target, "staged SQLite database", exact_mode=0o600)
    source_fact = db_fact(source, source_st)
    target_fact = db_fact(SQLITE_TARGET, target_st, actual_path=target)
    # A replacement during the open/checkpoint window is forbidden even when
    # its bytes happen to match.
    if (source_st_before.st_dev, source_st_before.st_ino) != (source_st.st_dev, source_st.st_ino):
        fail("legacy SQLite database identity drifted during backup")
    return source_sha_before, source_fact, target_fact


# This indirection is intentionally patchable by the isolated stdlib test
# harness.  Production replaces it for the duration of migrate with a closure
# that re-runs the fixed unit and /proc gates.
def check_runtime_gate_during_sqlite() -> None:
    return None


def db_fact(path_label: str, st: os.stat_result, actual_path: str | None = None) -> dict[str, Any]:
    path = actual_path if actual_path is not None else path_label
    return {
        "dev": st.st_dev,
        "ino": st.st_ino,
        "mode": mode_bits(st),
        "path": path_label,
        "sha256": sha256_file(path, expected=st),
        "size": st.st_size,
        "uid": st.st_uid,
    }


def tree_manifest(root: str) -> list[dict[str, Any]]:
    require_directory(root, "manifest root", exact_mode=0o700)
    records: list[dict[str, Any]] = []
    stack: list[tuple[str, str]] = [(root, "")]
    while stack:
        absolute, relative = stack.pop()
        entries = sorted(os.scandir(absolute), key=lambda entry: entry.name, reverse=True)
        for entry in entries:
            child_rel = entry.name if not relative else relative + "/" + entry.name
            child = os.path.join(absolute, entry.name)
            st = entry.stat(follow_symlinks=False)
            if st.st_uid != os.geteuid():
                fail("manifest entry has an untrusted owner")
            if stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                if mode_bits(st) != 0o700:
                    fail("manifest directory mode must be exact 0700")
                records.append(
                    {"mode": 0o700, "path": child_rel, "sha256": "-", "size": 0, "type": "directory"}
                )
                stack.append((child, child_rel))
            elif stat.S_ISREG(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                if st.st_nlink != 1 or mode_bits(st) != 0o600:
                    fail("manifest file must be single-link mode 0600")
                records.append(
                    {
                        "mode": 0o600,
                        "path": child_rel,
                        "sha256": sha256_file(child, expected=st),
                        "size": st.st_size,
                        "type": "file",
                    }
                )
            else:
                fail("manifest tree contains a symlink or special file")
    records.sort(key=lambda value: value["path"])
    return records


def empty_skeleton_manifest(path: str) -> list[dict[str, Any]]:
    manifest = tree_manifest(path)
    expected = [
        {"mode": 0o700, "path": leaf, "sha256": "-", "size": 0, "type": "directory"}
        for leaf in sorted(RUNTIME_LEAVES)
    ]
    if manifest != expected:
        fail("rollback skeleton is not the publisher's exact empty skeleton")
    return manifest


def assert_target_tree_stable(
    runtime_root: str,
    expected_database: dict[str, Any],
    expected_manifest: list[dict[str, Any]],
) -> None:
    database = os.path.join(runtime_root, SQLITE_TARGET)
    require_sqlite_family_absent(database, "migrated target SQLite database")
    database_st = require_regular(
        database, "migrated target SQLite database", exact_mode=0o600
    )
    if db_fact(SQLITE_TARGET, database_st, actual_path=database) != expected_database:
        fail("migrated target SQLite database fact drifted")
    sqlite_integrity(database, immutable=True)
    if tree_manifest(runtime_root) != expected_manifest:
        fail("migrated target manifest drifted")


def rename_exchange(left: str, right: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "renameat2", None)
    if function is None:
        fail("Linux renameat2 is required for atomic runtime-state activation")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    at_fdcwd = -100
    rename_exchange_flag = 2
    result = function(
        at_fdcwd,
        os.fsencode(left),
        at_fdcwd,
        os.fsencode(right),
        rename_exchange_flag,
    )
    if result != 0:
        error = ctypes.get_errno()
        if error in (errno.ENOSYS, errno.EINVAL, errno.EXDEV, errno.EOPNOTSUPP):
            fail("filesystem does not support atomic renameat2 exchange")
        fail("atomic runtime-state exchange failed")


def remove_tree_safe(path: str) -> None:
    st = checked_lstat(path, "private rollback tree")
    if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode) or st.st_uid != os.geteuid():
        fail("refusing to remove an untrusted rollback tree")
    for entry in os.scandir(path):
        child = os.path.join(path, entry.name)
        child_st = entry.stat(follow_symlinks=False)
        if child_st.st_uid != os.geteuid() or stat.S_ISLNK(child_st.st_mode):
            fail("refusing to remove an untrusted rollback entry")
        if stat.S_ISDIR(child_st.st_mode):
            remove_tree_safe(child)
        elif stat.S_ISREG(child_st.st_mode):
            os.unlink(child)
        else:
            fail("refusing to remove a special rollback entry")
    os.rmdir(path)


def write_receipt_temp(path: str, receipt: dict[str, Any]) -> str:
    temp = path + f".tmp.{os.getpid()}"
    if os.path.lexists(temp) or os.path.lexists(path):
        fail("migration receipt or its deterministic temporary path already exists")
    body = dict(receipt)
    body["receipt_digest"] = domain_digest(RECEIPT_DOMAIN, receipt)
    raw = canonical_json(body) + b"\n"
    fd = os.open(
        temp,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
    )
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fchmod(fd, 0o600)
        os.fsync(fd)
    finally:
        os.close(fd)
    return temp


def publish_receipt(temp: str, receipt_path: str) -> None:
    if os.path.lexists(receipt_path):
        fail("migration receipt appeared before atomic publication")
    os.rename(temp, receipt_path)
    fsync_dir(os.path.dirname(receipt_path))


def build_receipt(
    context: Context,
    txid: str,
    runtime_path: str,
    source_database_input_sha256: str,
    source_database: dict[str, Any],
    target_database: dict[str, Any],
    target_manifest: list[dict[str, Any]],
    rollback_path: str,
    rollback_identity: FileIdentity,
    rollback_manifest: list[dict[str, Any]],
    unit_baseline: list[dict[str, Any]],
) -> dict[str, Any]:
    runtime_st = require_directory(runtime_path, "staged runtime-state", exact_mode=0o700)
    return {
        "candidate_commit": context.pending["candidate_commit"],
        "created_at": now_utc(),
        "deploy_root_identity": context.root_identity.as_json(),
        "limits": dict(context.plan.raw["limits"]),
        "mappings_digest": context.plan.mappings_digest,
        "open_fd_baseline": {
            "database_family_open_descriptors": 0,
            "scope": "same_euid_proc_fd_exact_user_manager_infrastructure_exception",
        },
        "pending_admission": {
            "challenge": context.pending["challenge"],
            "lease_id": context.pending["lease_id"],
            "sha256": context.pending_sha256,
        },
        "plan_sha256": context.plan.raw_sha256,
        "rollback_skeleton": {
            "identity": rollback_identity.as_json(),
            "manifest_digest": domain_digest(MANIFEST_DOMAIN, rollback_manifest),
            "path": rollback_path,
        },
        "runtime_state_identity": identity_from_stat(runtime_st).as_json(),
        "schema": RECEIPT_SCHEMA,
        "source_database": source_database,
        "source_database_family": {
            "journal": "absent",
            "shm": "absent",
            "super_journals": "absent",
            "wal": "absent",
        },
        "source_database_input_sha256": source_database_input_sha256,
        "source_manifest_digest": context.plan.source_manifest_digest,
        "status": "complete_quiesced",
        "target_database": target_database,
        "target_manifest": target_manifest,
        "target_manifest_digest": domain_digest(MANIFEST_DOMAIN, target_manifest),
        "transaction_id": txid,
        "unit_baseline": unit_baseline,
    }


RECEIPT_KEYS = (
    "candidate_commit",
    "created_at",
    "deploy_root_identity",
    "limits",
    "mappings_digest",
    "open_fd_baseline",
    "pending_admission",
    "plan_sha256",
    "rollback_skeleton",
    "runtime_state_identity",
    "schema",
    "source_database",
    "source_database_family",
    "source_database_input_sha256",
    "source_manifest_digest",
    "status",
    "target_database",
    "target_manifest",
    "target_manifest_digest",
    "transaction_id",
    "unit_baseline",
    "receipt_digest",
)


def validate_identity_json(value: Any, label: str) -> dict[str, Any]:
    result = require_exact_keys(value, ("dev", "ino", "mode", "uid"), label)
    for key in ("dev", "ino", "mode", "uid"):
        require_int(result[key], f"{label}.{key}", 0, (1 << 63) - 1)
    return result


def validate_db_fact_json(value: Any, label: str) -> dict[str, Any]:
    result = require_exact_keys(
        value, ("dev", "ino", "mode", "path", "sha256", "size", "uid"), label
    )
    for key in ("dev", "ino", "mode", "size", "uid"):
        require_int(result[key], f"{label}.{key}", 0, (1 << 63) - 1)
    if not isinstance(result["path"], str) or not result["path"]:
        fail(f"{label}.path is invalid")
    if not isinstance(result["sha256"], str) or not HEX64.fullmatch(result["sha256"]):
        fail(f"{label}.sha256 is invalid")
    return result


def validate_manifest_json(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        fail(f"{label} must be a list")
    previous = ""
    for index, record_value in enumerate(value):
        record = require_exact_keys(
            record_value, ("mode", "path", "sha256", "size", "type"), f"{label}[{index}]"
        )
        path = record["path"]
        if not isinstance(path, str) or not path or (previous and path <= previous):
            fail(f"{label} paths must be unique and sorted")
        previous = path
        if record["type"] == "directory":
            if record["mode"] != 0o700 or record["size"] != 0 or record["sha256"] != "-":
                fail(f"{label} directory fact is invalid")
        elif record["type"] == "file":
            if record["mode"] != 0o600:
                fail(f"{label} file mode is invalid")
            require_int(record["size"], f"{label} file size", 0, HARD_MAX_BYTES)
            if not isinstance(record["sha256"], str) or not HEX64.fullmatch(record["sha256"]):
                fail(f"{label} file digest is invalid")
        else:
            fail(f"{label} record type is invalid")
    return value


def validate_unit_baseline(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != len(UNITS):
        fail("receipt unit baseline must cover the exact fixed unit set")
    for index, (record_value, expected_name) in enumerate(zip(value, UNITS)):
        if not isinstance(record_value, dict) or record_value.get("type") not in (
            "service",
            "timer",
        ):
            fail("receipt unit baseline has an unknown typed record")
        if record_value["type"] == "service":
            record = require_exact_keys(
                record_value,
                ("active_state", "load_state", "main_pid", "name", "sub_state", "type"),
                f"receipt service baseline {index}",
            )
            if record["main_pid"] != 0:
                fail("receipt service baseline MainPID must be zero")
        else:
            record = require_exact_keys(
                record_value,
                (
                    "active_state",
                    "load_state",
                    "name",
                    "sub_state",
                    "type",
                    "unit_file_state",
                ),
                f"receipt timer baseline {index}",
            )
            if (record["load_state"], record["unit_file_state"]) not in (
                ("loaded", "disabled"),
                ("masked", "masked"),
                ("not-found", ""),
            ):
                fail("receipt timer baseline is enabled, triggerable, or contradictory")
        if (
            record["name"] != expected_name
            or record["active_state"] != "inactive"
            or record["sub_state"] != "dead"
        ):
            fail("receipt unit baseline is not the exact quiesced unit set")
    return value


def load_receipt(path: str) -> tuple[dict[str, Any], FileIdentity]:
    raw, identity = read_regular_bytes(
        path, "state migration receipt", exact_mode=0o600, maximum=MAX_RECEIPT_BYTES
    )
    receipt = require_exact_keys(parse_json_bytes(raw, "state migration receipt"), RECEIPT_KEYS, "state migration receipt")
    if receipt["schema"] != RECEIPT_SCHEMA or receipt["status"] != "complete_quiesced":
        fail("state migration receipt schema/status mismatch")
    if not HEX40.fullmatch(receipt["candidate_commit"]):
        fail("receipt candidate is invalid")
    if not UTC_TIME.fullmatch(receipt["created_at"]):
        fail("receipt timestamp is invalid")
    for key in (
        "mappings_digest",
        "plan_sha256",
        "source_database_input_sha256",
        "source_manifest_digest",
        "target_manifest_digest",
        "transaction_id",
        "receipt_digest",
    ):
        if not isinstance(receipt[key], str) or not HEX64.fullmatch(receipt[key]):
            fail(f"receipt field {key} is invalid")
    validate_identity_json(receipt["deploy_root_identity"], "receipt deploy root identity")
    validate_identity_json(receipt["runtime_state_identity"], "receipt runtime identity")
    pending = require_exact_keys(
        receipt["pending_admission"], ("challenge", "lease_id", "sha256"), "receipt pending admission"
    )
    if not HEX64.fullmatch(pending["challenge"]) or not HEX64.fullmatch(pending["sha256"]) or not SAFE_ID.fullmatch(pending["lease_id"]):
        fail("receipt pending-admission binding is invalid")
    limits = require_exact_keys(
        receipt["limits"], ("max_files", "max_bytes", "max_file_bytes", "reserve_bytes"), "receipt limits"
    )
    for key in limits:
        require_int(limits[key], f"receipt limit {key}", 0, HARD_MAX_BYTES)
    open_fds = require_exact_keys(
        receipt["open_fd_baseline"],
        ("database_family_open_descriptors", "scope"),
        "receipt open-fd baseline",
    )
    if open_fds != {
        "database_family_open_descriptors": 0,
        "scope": "same_euid_proc_fd_exact_user_manager_infrastructure_exception",
    }:
        fail("receipt open-fd baseline is not the exact zero-open-descriptor state")
    rollback = require_exact_keys(
        receipt["rollback_skeleton"], ("identity", "manifest_digest", "path"), "receipt rollback skeleton"
    )
    validate_identity_json(rollback["identity"], "receipt rollback identity")
    if not isinstance(rollback["path"], str) or not HEX64.fullmatch(rollback["manifest_digest"]):
        fail("receipt rollback skeleton fields are invalid")
    validate_db_fact_json(receipt["source_database"], "receipt source database")
    source_family = require_exact_keys(
        receipt["source_database_family"],
        ("journal", "shm", "super_journals", "wal"),
        "receipt source database family",
    )
    if source_family != {
        "journal": "absent",
        "shm": "absent",
        "super_journals": "absent",
        "wal": "absent",
    }:
        fail("receipt source database family is not the stable absent state")
    validate_db_fact_json(receipt["target_database"], "receipt target database")
    validate_manifest_json(receipt["target_manifest"], "receipt target manifest")
    validate_unit_baseline(receipt["unit_baseline"])
    digest = receipt["receipt_digest"]
    unsigned = dict(receipt)
    del unsigned["receipt_digest"]
    if domain_digest(RECEIPT_DOMAIN, unsigned) != digest:
        fail("state migration receipt digest mismatch")
    return receipt, identity


def json_identity_matches(value: dict[str, Any], st: os.stat_result) -> bool:
    return value == identity_from_stat(st).as_json()


def verify_receipt(context: Context) -> dict[str, Any]:
    migrations = os.path.join(context.root, "publisher-state/migrations")
    require_directory(migrations, "publisher migration state", exact_mode=0o700)
    receipt, _identity = load_receipt(context.receipt_path)
    if receipt["candidate_commit"] != context.pending["candidate_commit"]:
        fail("receipt candidate no longer matches pending admission")
    if receipt["pending_admission"] != {
        "challenge": context.pending["challenge"],
        "lease_id": context.pending["lease_id"],
        "sha256": context.pending_sha256,
    }:
        fail("receipt pending-admission binding drifted")
    if receipt["plan_sha256"] != context.plan.raw_sha256:
        fail("receipt plan binding drifted")
    if receipt["deploy_root_identity"] != context.root_identity.as_json():
        fail("receipt deployment-root identity drifted")
    if receipt["limits"] != context.plan.raw["limits"]:
        fail("receipt limits drifted")
    if receipt["mappings_digest"] != context.plan.mappings_digest:
        fail("receipt mapping digest drifted")
    if receipt["source_manifest_digest"] != context.plan.source_manifest_digest:
        fail("receipt source manifest drifted")
    if receipt["transaction_id"] != transaction_id(context):
        fail("receipt transaction identity drifted")

    runtime = os.path.join(context.root, "runtime-state")
    runtime_st = require_directory(runtime, "migrated runtime-state", exact_mode=0o700)
    if not json_identity_matches(receipt["runtime_state_identity"], runtime_st):
        fail("migrated runtime-state inode drifted")
    manifest = tree_manifest(runtime)
    if manifest != receipt["target_manifest"]:
        fail("migrated runtime-state manifest drifted")
    if domain_digest(MANIFEST_DOMAIN, manifest) != receipt["target_manifest_digest"]:
        fail("migrated runtime-state manifest digest drifted")

    target_path = os.path.join(runtime, SQLITE_TARGET)
    target_st = require_regular(target_path, "migrated SQLite database", exact_mode=0o600)
    target_fact = db_fact(SQLITE_TARGET, target_st, actual_path=target_path)
    if target_fact != receipt["target_database"]:
        fail("migrated SQLite database fact drifted")
    sqlite_integrity(target_path, immutable=True)

    source_path = context.plan.sqlite_source
    if receipt["source_database_family"] != {
        "journal": "absent",
        "shm": "absent",
        "super_journals": "absent",
        "wal": "absent",
    }:
        fail("receipt does not bind an absent legacy SQLite sidecar family")
    require_sqlite_family_absent(source_path, "verified legacy SQLite database")
    source_st = require_legacy_regular(source_path, "legacy SQLite database")
    source_fact = db_fact(source_path, source_st)
    if source_fact != receipt["source_database"]:
        fail("legacy SQLite database changed after migration")
    sqlite_integrity(source_path, immutable=True)

    rollback = receipt["rollback_skeleton"]
    expected_rollback = os.path.join(
        context.root, "publisher-state/migrations/rollback-" + receipt["transaction_id"][:24]
    )
    if rollback["path"] != expected_rollback:
        fail("receipt rollback skeleton path is not fixed")
    rollback_st = require_directory(expected_rollback, "rollback skeleton", exact_mode=0o700)
    if not json_identity_matches(rollback["identity"], rollback_st):
        fail("rollback skeleton identity drifted")
    rollback_manifest = empty_skeleton_manifest(expected_rollback)
    if domain_digest(MANIFEST_DOMAIN, rollback_manifest) != rollback["manifest_digest"]:
        fail("rollback skeleton manifest drifted")

    revalidate_bindings(context)
    assert_source_inputs_stable(
        context,
        receipt["source_database"],
        receipt["source_manifest_digest"],
    )
    current_baseline = collect_quiescence()
    if current_baseline != receipt["unit_baseline"]:
        fail("fixed unit baseline drifted after migration")
    destination = os.path.join(context.root, "runtime-state", SQLITE_TARGET)
    scan_open_fds(db_family_paths(context.plan.sqlite_source, destination))
    # Rehash both trust domains after the final quiescence/FD gate.  The
    # earlier validations establish the receipt bindings; these adjacent
    # checks prevent a short-lived writer between those reads and return from
    # being accepted against cached facts.
    assert_source_inputs_stable(
        context,
        receipt["source_database"],
        receipt["source_manifest_digest"],
    )
    assert_target_tree_stable(
        runtime,
        receipt["target_database"],
        receipt["target_manifest"],
    )
    return stable_result(
        "verify",
        "verified",
        receipt_digest=receipt["receipt_digest"],
    )


def command_preflight(context: Context) -> dict[str, Any]:
    if os.path.lexists(context.receipt_path):
        fail("migration receipt already exists; use verify")
    runtime_skeleton(context.root)
    revalidate_bindings(context)
    check_runtime_gates(context.plan, context.root)
    check_capacity(context.plan, context.root)
    return stable_result(
        "preflight",
        "ready_quiesced",
        candidate_commit=context.pending["candidate_commit"],
        estimated_bytes=context.plan.estimated_bytes,
        estimated_files=context.plan.estimated_files,
        pending_admission_sha256=context.pending_sha256,
        plan_sha256=context.plan.raw_sha256,
        sqlite_integrity=context.plan.sqlite_preflight_integrity,
        transaction_id=transaction_id(context),
    )


def migrate(context: Context, confirmation: str | None) -> dict[str, Any]:
    if os.path.lexists(context.receipt_path):
        verified = verify_receipt(context)
        return stable_result(
            "migrate",
            "already_migrated",
            receipt_digest=verified["receipt_digest"],
            transaction_id=transaction_id(context),
        )
    expected_confirmation = (
        "MIGRATE:" + context.pending["candidate_commit"] + ":" + context.pending_sha256
    )
    if confirmation != expected_confirmation:
        fail("migrate confirmation must exactly bind the candidate and pending-admission digest")

    runtime = runtime_skeleton(context.root)
    txid = transaction_id(context)
    stage = ""
    rollback_path = ""
    receipt_temp = ""
    exchanged = False
    moved_rollback = False
    receipt_published = False
    original_gate_hook = globals()["check_runtime_gate_during_sqlite"]

    def full_gate() -> None:
        revalidate_bindings(context)
        check_runtime_gates(context.plan, context.root)

    globals()["check_runtime_gate_during_sqlite"] = full_gate
    try:
        full_gate()
        stage = create_stage(context.root, txid)
        ensure_stage_directories(stage, context.plan.target_dirs)
        for source in context.plan.source_files:
            copy_file_exact(source, stage)

        full_gate()  # immediately before checkpoint
        sqlite_target = os.path.join(stage, SQLITE_TARGET)
        source_database_input_sha256, source_database, target_database = sqlite_checkpoint_and_backup(
            context.plan.sqlite_source, sqlite_target
        )
        full_gate()  # after checkpoint and backup have closed every DB handle
        # WAL checkpointing is the one intentional legacy-source byte change.
        # Bind the receipt to the post-checkpoint source image so standalone
        # verify and idempotent replay observe the same immutable baseline.
        refreshed_sources = refresh_retained_sources(context)
        context.plan.source_manifest_digest = refreshed_sources.source_manifest_digest
        assert_source_inputs_stable(
            context, source_database, context.plan.source_manifest_digest
        )

        manifest = tree_manifest(stage)
        actual_bytes = sum(record["size"] for record in manifest if record["type"] == "file")
        actual_files = sum(1 for record in manifest if record["type"] == "file")
        limits = context.plan.raw["limits"]
        if actual_files > limits["max_files"] or actual_bytes > limits["max_bytes"]:
            fail("staged target exceeds the admitted migration limits")
        check_capacity(context.plan, context.root, actual_bytes)
        # Durability proof is explicit: every staged regular file (including
        # SQLite) and every directory entry is synced bottom-up before exchange.
        fsync_tree(stage)
        fsync_dir(context.root)
        assert_target_tree_stable(stage, target_database, manifest)
        assert_source_inputs_stable(
            context, source_database, context.plan.source_manifest_digest
        )

        migrations = ensure_migrations_dir(context.root)
        rollback_path = os.path.join(migrations, "rollback-" + txid[:24])
        if os.path.lexists(rollback_path):
            fail("deterministic rollback skeleton path already exists")
        # stage's inode will become runtime-state's inode after RENAME_EXCHANGE.
        stage_st = require_directory(stage, "migration stage", exact_mode=0o700)
        placeholder_rollback_identity = identity_from_stat(checked_lstat(runtime, "runtime skeleton"))
        rollback_manifest = empty_skeleton_manifest(runtime)
        receipt_body = build_receipt(
            context,
            txid,
            stage,
            source_database_input_sha256,
            source_database,
            target_database,
            manifest,
            rollback_path,
            placeholder_rollback_identity,
            rollback_manifest,
            collect_quiescence(),
        )
        if receipt_body["runtime_state_identity"] != identity_from_stat(stage_st).as_json():
            fail("staged runtime identity changed before activation")
        receipt_temp = write_receipt_temp(context.receipt_path, receipt_body)

        full_gate()
        assert_source_inputs_stable(
            context, source_database, context.plan.source_manifest_digest
        )
        assert_target_tree_stable(stage, target_database, manifest)
        rename_exchange(runtime, stage)
        exchanged = True
        fsync_dir(context.root)
        full_gate()
        assert_source_inputs_stable(
            context, source_database, context.plan.source_manifest_digest
        )
        assert_target_tree_stable(runtime, target_database, manifest)
        empty_skeleton_manifest(stage)
        os.rename(stage, rollback_path)
        moved_rollback = True
        stage = ""
        fsync_dir(context.root)
        fsync_dir(migrations)
        revalidate_bindings(context)
        check_runtime_gates(context.plan, context.root)
        assert_source_inputs_stable(
            context, source_database, context.plan.source_manifest_digest
        )
        assert_target_tree_stable(runtime, target_database, manifest)
        if collect_quiescence() != receipt_body["unit_baseline"]:
            fail("fixed unit baseline drifted before receipt publication")
        # Atomic rename plus parent fsync is intentionally the final write.
        publish_receipt(receipt_temp, context.receipt_path)
        receipt_temp = ""
        receipt_published = True
        return stable_result(
            "migrate",
            "migrated_quiesced",
            receipt_digest=domain_digest(RECEIPT_DOMAIN, receipt_body),
            transaction_id=txid,
        )
    except BaseException:
        if not receipt_published:
            try:
                if moved_rollback:
                    os.rename(rollback_path, os.path.join(context.root, "runtime-state.migration-stage." + txid[:24]))
                    stage = os.path.join(context.root, "runtime-state.migration-stage." + txid[:24])
                    moved_rollback = False
                if exchanged and stage and os.path.lexists(stage):
                    rename_exchange(runtime, stage)
                    exchanged = False
                    fsync_dir(context.root)
                if stage and os.path.lexists(stage):
                    remove_tree_safe(stage)
                    fsync_dir(context.root)
                if receipt_temp and os.path.lexists(receipt_temp):
                    os.unlink(receipt_temp)
                    fsync_dir(os.path.dirname(receipt_temp))
            except BaseException as rollback_error:
                raise MigrationError(
                    "migration failed and automatic rollback could not be proven; receipt was not published"
                ) from rollback_error
        raise
    finally:
        globals()["check_runtime_gate_during_sqlite"] = original_gate_hook


def execute(
    command: str,
    deploy_root: str,
    *,
    confirmation: str | None = None,
    inherited_lock_fd: int | None = None,
) -> dict[str, Any]:
    previous_umask = os.umask(0o077)
    context: Context | None = None
    try:
        context = build_context(command, deploy_root, inherited_lock_fd)
        if command == "preflight":
            return command_preflight(context)
        if command == "migrate":
            return migrate(context, confirmation)
        if command == "verify":
            return verify_receipt(context)
        fail("unknown migration command")
    finally:
        if context is not None and context.owns_lock_fd:
            os.close(context.lock_fd)
        os.umask(previous_umask)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "migrate", "verify"))
    parser.add_argument("--deploy-root", required=True)
    parser.add_argument("--confirm")
    parser.add_argument("--inherited-lock-fd", type=int)
    args = parser.parse_args(argv)
    if args.command != "migrate" and args.confirm is not None:
        parser.error("--confirm is accepted only by migrate")
    if args.command != "verify" and args.inherited_lock_fd is not None:
        parser.error("--inherited-lock-fd is accepted only by verify")
    return args


def validate_production_interpreter() -> None:
    if sys.executable != "/usr/bin/python3":
        fail("production migration requires the fixed /usr/bin/python3 interpreter")
    if not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        fail("production migration requires /usr/bin/python3 -I -B")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        validate_production_interpreter()
        args = parse_args(sys.argv[1:] if argv is None else argv)
        result = execute(
            args.command,
            args.deploy_root,
            confirmation=args.confirm,
            inherited_lock_fd=args.inherited_lock_fd,
        )
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
        return 0
    except MigrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
