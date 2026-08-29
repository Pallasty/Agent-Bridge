#!/usr/bin/python3
"""Create one private Agent Bridge deployment root from explicit inputs.

The default ``plan`` command is read-only.  ``provision`` is the only writing
command and requires the exact confirmation emitted by ``plan``.  ``verify``
independently validates the immutable bootstrap receipt before the trusted
wrapper or publisher is allowed to mutate the root.

This is a bootstrap-custody tool, not publication authority.  The copied Git
repository is only a seed for the publisher's later authenticated GitLab
fetch.  No service, timer, database, systemd unit, credential value, or legacy
state is read or changed by this tool.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator, NoReturn, Sequence


MANIFEST_SCHEMA = "agent_bridge.trusted_deployment_root_provisioning_manifest.v1"
RECEIPT_SCHEMA = "agent_bridge.trusted_deployment_root_provisioning_receipt.v1"
RESULT_SCHEMA = "agent_bridge.trusted_deployment_root_provisioning_result.v1"
REMOTE_URL = "git@gitlab.com:pallasting/agent-bridge.git"
AGENT_AUTH_SCHEMA = "agent_bridge.gitlab_agent_authentication.v1"
PLAN_DOMAIN = b"agent-bridge/trusted-root-provisioning/plan/v1\0"
TREE_DOMAIN = b"agent-bridge/trusted-root-provisioning/tree/v1\0"
RECEIPT_DOMAIN = b"agent-bridge/trusted-root-provisioning/receipt/v1\0"

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ROOT_NAME = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
SAFE_AGENT_PATH = re.compile(r"^/[A-Za-z0-9._/-]+$")
SSH_SHA256 = re.compile(r"^SHA256:[A-Za-z0-9+/]{43}$")
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_FILE_BYTES = 1024 * 1024 * 1024
HARD_MAX_FILES = 1_000_000
HARD_MAX_BYTES = 16 * 1024 * 1024 * 1024
MIN_FREE_AFTER_FLOOR = 2 * 1024 * 1024 * 1024

ORCHESTRATOR_MODES = {
    "scripts/deploy_from_master.sh": 0o700,
    "scripts/publish-and-acquire-trusted-seed.py": 0o700,
    "scripts/prepare-gitlab-deploy-credential.py": 0o700,
    "scripts/provision-trusted-deployment-root.py": 0o700,
    "scripts/migrate-trusted-runtime-state.py": 0o700,
    "scripts/systemd/install-trusted-daemon-root.sh": 0o700,
    "scripts/wrapper/install.sh": 0o600,
    "scripts/wrapper/agent-bridge-wrapper.sh": 0o600,
    "scripts/wrapper/creds.example": 0o600,
}


class ProvisionError(RuntimeError):
    """Expected fail-closed rejection."""


def fail(message: str) -> NoReturn:
    raise ProvisionError(message)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str, maximum: int = MAX_FILE_BYTES) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        fail(f"cannot open physical input file: {exc.strerror}")
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            fail("input must be a singly linked physical regular file")
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > maximum:
                fail("input file exceeds its admitted byte bound")
            digest.update(chunk)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            fail("input file changed while it was hashed")
    finally:
        os.close(fd)
    return digest.hexdigest(), total


def parse_json(raw: bytes, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                fail(f"{label} contains duplicate key {key}")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"{label} is not strict UTF-8 JSON: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def exact_keys(value: dict[str, Any], expected: Sequence[str], label: str) -> None:
    if set(value) != set(expected):
        fail(f"{label} keys are not exact")


def mode_bits(st: os.stat_result) -> int:
    return stat.S_IMODE(st.st_mode)


def path_has_symlink(path: str) -> bool:
    current = "/"
    for part in path.split("/")[1:]:
        if not part:
            continue
        current = os.path.join(current, part)
        try:
            if stat.S_ISLNK(os.lstat(current).st_mode):
                return True
        except FileNotFoundError:
            return False
    return False


def canonical_absolute(path: Any, label: str, *, must_exist: bool = True) -> str:
    if not isinstance(path, str) or not path.startswith("/") or "\x00" in path:
        fail(f"{label} must be an absolute path")
    if os.path.normpath(path) != path:
        fail(f"{label} must be canonical")
    if path_has_symlink(path):
        fail(f"{label} must not traverse a symlink")
    if must_exist and not os.path.exists(path):
        fail(f"{label} does not exist")
    if must_exist and os.path.realpath(path) != path:
        fail(f"{label} must resolve to itself")
    return path


def validate_trusted_ancestors(path: str, label: str) -> None:
    current = os.path.dirname(path)
    while True:
        try:
            st = os.lstat(current)
        except OSError as exc:
            fail(f"cannot inspect {label} ancestor: {exc.strerror}")
        if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
            fail(f"{label} ancestor must be a physical directory")
        mode = mode_bits(st)
        if st.st_uid not in (0, os.geteuid()):
            fail(f"{label} ancestor has an untrusted owner")
        if mode & 0o022 and not (st.st_uid == 0 and mode & 0o1000):
            fail(f"{label} ancestor is replaceable")
        if current == "/":
            break
        current = os.path.dirname(current)


def require_directory(
    path: str,
    label: str,
    *,
    exact_mode: int | None = None,
    owner: bool = True,
) -> os.stat_result:
    try:
        st = os.lstat(path)
    except OSError as exc:
        fail(f"cannot inspect {label}: {exc.strerror}")
    if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
        fail(f"{label} must be a physical directory")
    if owner and st.st_uid != os.geteuid():
        fail(f"{label} must be owned by the effective user")
    if exact_mode is not None and mode_bits(st) != exact_mode:
        fail(f"{label} mode must be exact 0{exact_mode:o}")
    return st


def require_file(
    path: str,
    label: str,
    *,
    exact_mode: int | None = None,
    maximum: int = MAX_FILE_BYTES,
) -> tuple[os.stat_result, str, int]:
    canonical_absolute(path, label)
    validate_trusted_ancestors(path, label)
    try:
        st = os.lstat(path)
    except OSError as exc:
        fail(f"cannot inspect {label}: {exc.strerror}")
    if not stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode) or st.st_nlink != 1:
        fail(f"{label} must be a singly linked physical regular file")
    if st.st_uid != os.geteuid():
        fail(f"{label} must be owned by the effective user")
    if exact_mode is not None and mode_bits(st) != exact_mode:
        fail(f"{label} mode must be exact 0{exact_mode:o}")
    digest, size = sha256_file(path, maximum)
    return st, digest, size


def validate_parent(root: str) -> tuple[str, os.stat_result]:
    parent = os.path.dirname(root)
    name = os.path.basename(root)
    if not SAFE_ROOT_NAME.fullmatch(name) or name in (".", ".."):
        fail("deployment-root basename is not safe")
    canonical_absolute(parent, "deployment-root parent")
    validate_trusted_ancestors(parent, "deployment-root parent")
    st = require_directory(parent, "deployment-root parent", owner=False)
    mode = mode_bits(st)
    if st.st_uid == os.geteuid():
        if mode & 0o022:
            fail("effective-user deployment-root parent must not be group/other writable")
    elif st.st_uid == 0:
        if not (mode & 0o1000 and mode & 0o002):
            fail("root-owned deployment-root parent must be a writable sticky directory")
    else:
        fail("deployment-root parent has an untrusted owner")
    return parent, st


def paths_overlap(first: str, second: str) -> bool:
    return first == second or first.startswith(second + "/") or second.startswith(first + "/")


def git_env(home: str) -> dict[str, str]:
    return {
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PROTOCOL_FROM_USER": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "HOME": home,
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
    }


def git_run(
    repo: str | None,
    args: Sequence[str],
    *,
    home: str,
    timeout: int = 60,
) -> bytes:
    command = [
        "/usr/bin/git",
        "--no-pager",
        "-c",
        "core.attributesFile=/dev/null",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "protocol.file.allow=always",
    ]
    if repo is not None:
        command += ["-C", repo]
    command += list(args)
    try:
        result = subprocess.run(
            command,
            env=git_env(home),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        fail("bounded bootstrap Git operation failed")
    if result.returncode != 0:
        fail("bounded bootstrap Git operation failed")
    return result.stdout


def git_value(repo: str, args: Sequence[str], home: str) -> str:
    try:
        return git_run(repo, args, home=home).decode("ascii", "strict").strip()
    except UnicodeDecodeError:
        fail("bootstrap Git result is not ASCII")


def validate_local_git_config(repo: str, home: str) -> None:
    raw = git_run(repo, ("config", "--local", "--list"), home=home)
    try:
        lines = raw.decode("utf-8", "strict").splitlines()
    except UnicodeDecodeError:
        fail("trusted source local Git config is not UTF-8")
    observed: dict[str, list[str]] = {}
    for line in lines:
        if "=" not in line:
            fail("trusted source local Git config line is malformed")
        key, value = line.split("=", 1)
        observed.setdefault(key.lower(), []).append(value)
    filemode = observed.pop("core.filemode", None)
    if filemode not in (["true"], ["false"]):
        fail("trusted source core.filemode config is invalid")
    expected = {
        "core.bare": ["false"],
        "core.logallrefupdates": ["true"],
        "core.repositoryformatversion": ["0"],
        "remote.gitlab.fetch": ["+refs/heads/*:refs/remotes/gitlab/*"],
        "remote.gitlab.url": [REMOTE_URL],
        "branch.master.remote": ["gitlab"],
        "branch.master.merge": ["refs/heads/master"],
    }
    if observed != expected:
        fail("trusted source local Git config is not exact")


def validate_seed(repo: str, candidate: str) -> dict[str, str]:
    canonical_absolute(repo, "bootstrap source repository")
    require_directory(repo, "bootstrap source repository", exact_mode=0o700)
    require_directory(os.path.join(repo, ".git"), "bootstrap Git metadata", exact_mode=0o700)
    for relative in (
        ".git/info/attributes",
        ".git/info/grafts",
        ".git/objects/info/alternates",
        ".git/objects/info/http-alternates",
    ):
        if os.path.lexists(os.path.join(repo, relative)):
            fail("bootstrap source contains a forbidden Git override")
    validate_local_git_config(repo, repo)
    head = git_value(repo, ("rev-parse", "--verify", "HEAD^{commit}"), repo)
    remote = git_value(
        repo,
        ("rev-parse", "--verify", "refs/remotes/gitlab/master^{commit}"),
        repo,
    )
    tree = git_value(repo, ("rev-parse", "--verify", f"{candidate}^{{tree}}"), repo)
    url_lines = git_run(
        repo, ("config", "--local", "--get-all", "remote.gitlab.url"), home=repo
    ).decode("ascii", "strict").splitlines()
    status_out = git_run(
        repo,
        ("status", "--porcelain=v1", "--untracked-files=all"),
        home=repo,
    )
    gitlinks = git_run(repo, ("ls-tree", "-r", candidate), home=repo)
    if head != candidate or remote != candidate:
        fail("bootstrap source HEAD and gitlab/master must equal candidate")
    if url_lines != [REMOTE_URL]:
        fail("bootstrap source GitLab URL is not exact")
    if status_out:
        fail("bootstrap source repository must be completely clean")
    if any(line.split(maxsplit=2)[1:2] == [b"commit"] for line in gitlinks.splitlines()):
        fail("bootstrap source repository may not contain gitlinks")
    return {"commit": candidate, "tree": tree, "url": REMOTE_URL}


def reject_gitlinks(repo: str, candidate: str, home: str, label: str) -> None:
    listing = git_run(repo, ("ls-tree", "-r", candidate), home=home)
    if any(line.split(maxsplit=2)[1:2] == [b"commit"] for line in listing.splitlines()):
        fail(f"{label} may not contain gitlinks")


def iter_tree(root: str) -> Iterator[tuple[str, os.DirEntry[str], os.stat_result]]:
    stack: list[tuple[str, str]] = [("", root)]
    while stack:
        relative, current = stack.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda entry: entry.name, reverse=True)
        except OSError as exc:
            fail(f"cannot scan tree: {exc.strerror}")
        for entry in entries:
            child_relative = entry.name if not relative else relative + "/" + entry.name
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError as exc:
                fail(f"cannot inspect tree entry: {exc.strerror}")
            yield child_relative, entry, st
            if stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                stack.append((child_relative, entry.path))


def tree_manifest(
    root: str,
    *,
    max_files: int,
    max_bytes: int,
    require_private_root: bool = True,
    normalize_private_modes: bool = False,
) -> tuple[list[dict[str, Any]], str, int, int]:
    root_st = require_directory(
        root,
        "tree root",
        exact_mode=0o700 if require_private_root else None,
    )
    records: list[dict[str, Any]] = [
        {
            "mode": 0o700 if normalize_private_modes else mode_bits(root_st),
            "path": ".",
            "type": "directory",
            "uid": root_st.st_uid,
        }
    ]
    files = 0
    total = 0
    for relative, entry, st in iter_tree(root):
        if stat.S_ISLNK(st.st_mode):
            fail("tree contains a symlink")
        if st.st_uid != os.geteuid():
            fail("tree contains an entry not owned by the effective user")
        if stat.S_ISDIR(st.st_mode):
            records.append(
                {
                    "mode": 0o700 if normalize_private_modes else mode_bits(st),
                    "path": relative,
                    "type": "directory",
                    "uid": st.st_uid,
                }
            )
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            fail("tree contains a special or multiply linked file")
        digest, size = sha256_file(entry.path, maximum=max_bytes)
        files += 1
        total += size
        if files > max_files or total > max_bytes:
            fail("tree exceeds its admitted file or byte bound")
        records.append(
            {
                "mode": (
                    0o700 if mode_bits(st) & 0o100 else 0o600
                ) if normalize_private_modes else mode_bits(st),
                "path": relative,
                "sha256": digest,
                "size": size,
                "type": "file",
                "uid": st.st_uid,
            }
        )
    records.sort(key=lambda item: item["path"])
    digest = sha256_bytes(TREE_DOMAIN + canonical_json(records))
    return records, digest, files, total


def input_spec(value: Any, label: str) -> tuple[str, str]:
    if not isinstance(value, dict):
        fail(f"{label} input must be an object")
    exact_keys(value, ("path", "sha256"), f"{label} input")
    path = canonical_absolute(value["path"], f"{label} input")
    expected = value["sha256"]
    if not isinstance(expected, str) or not HEX64.fullmatch(expected):
        fail(f"{label} input SHA-256 is invalid")
    return path, expected


def validate_known_hosts(path: str) -> None:
    try:
        with open(path, "rb") as handle:
            raw = handle.read(256 * 1024 + 1)
    except OSError as exc:
        fail(f"cannot read known-hosts input: {exc.strerror}")
    if not raw or len(raw) > 256 * 1024 or b"\x00" in raw:
        fail("known-hosts input is empty or invalid")
    for line in raw.splitlines():
        if not line or line.startswith(b"#"):
            continue
        if not (line.startswith(b"gitlab.com ") or line.startswith(b"|1|")):
            fail("known-hosts input contains a host other than gitlab.com")


def validate_private_key(path: str) -> None:
    try:
        with open(path, "rb") as handle:
            head = handle.read(128)
    except OSError as exc:
        fail(f"cannot read GitLab key input: {exc.strerror}")
    if not head.startswith(b"-----BEGIN OPENSSH PRIVATE KEY-----\n"):
        fail("GitLab key input is not an OpenSSH private key")


def bounded_ssh(
    args: Sequence[str], *, socket_path: str | None = None,
    allowed_returncodes: tuple[int, ...] = (0,),
) -> bytes:
    env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LANG": "C", "LC_ALL": "C"}
    if socket_path is not None:
        env["SSH_AUTH_SOCK"] = socket_path
    try:
        result = subprocess.run(
            list(args), env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        fail("bounded SSH identity inspection failed")
    if result.returncode not in allowed_returncodes:
        fail("SSH identity inspection failed")
    return result.stdout


def public_key_fingerprint(path: str) -> str:
    raw = bounded_ssh(("/usr/bin/ssh-keygen", "-E", "sha256", "-lf", path))
    try:
        value = raw.decode("ascii", "strict").split()[1]
    except (UnicodeDecodeError, IndexError):
        fail("GitLab agent public-key fingerprint is malformed")
    if not SSH_SHA256.fullmatch(value):
        fail("GitLab agent public-key fingerprint is invalid")
    return value


def agent_fingerprints(socket_path: str) -> set[str]:
    raw = bounded_ssh(
        ("/usr/bin/ssh-add", "-l"), socket_path=socket_path,
        allowed_returncodes=(0, 1),
    )
    try:
        result = {line.split()[1] for line in raw.decode("ascii", "strict").splitlines()}
    except (UnicodeDecodeError, IndexError):
        fail("SSH agent inventory is malformed")
    return result


def validate_agent_authentication(value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict):
        fail("GitLab authentication input must be an object")
    exact_keys(
        value,
        ("mode", "socket_path", "public_key", "public_key_fingerprint"),
        "GitLab authentication input",
    )
    if value["mode"] != "agent_socket":
        fail("GitLab authentication mode is invalid")
    socket_path = canonical_absolute(value["socket_path"], "GitLab agent socket")
    if not SAFE_AGENT_PATH.fullmatch(socket_path):
        fail("GitLab agent socket path is not shell-safe")
    validate_trusted_ancestors(socket_path, "GitLab agent socket")
    socket_st = os.lstat(socket_path)
    if (
        not stat.S_ISSOCK(socket_st.st_mode)
        or socket_st.st_uid != os.geteuid()
        or mode_bits(socket_st) != 0o600
    ):
        fail("GitLab agent socket custody is invalid")
    public_path, expected = input_spec(value["public_key"], "gitlab_agent_public_key")
    _, digest, size = require_file(
        public_path, "gitlab_agent_public_key", exact_mode=0o600,
        maximum=256 * 1024,
    )
    if digest != expected:
        fail("gitlab_agent_public_key input digest mismatch")
    fingerprint = value["public_key_fingerprint"]
    if not isinstance(fingerprint, str) or not SSH_SHA256.fullmatch(fingerprint):
        fail("GitLab agent public-key fingerprint is invalid")
    if public_key_fingerprint(public_path) != fingerprint:
        fail("GitLab agent public key does not match its fingerprint")
    if fingerprint not in agent_fingerprints(socket_path):
        fail("required GitLab agent identity is absent")
    authentication = {
        "mode": "agent_socket",
        "socket_path": socket_path,
        "public_key_fingerprint": fingerprint,
        "socket_identity": {
            "dev": socket_st.st_dev,
            "ino": socket_st.st_ino,
            "mode": mode_bits(socket_st),
            "uid": socket_st.st_uid,
        },
    }
    public_fact = {"path": public_path, "sha256": digest, "size": size}
    return authentication, public_fact


@dataclass
class Prepared:
    manifest_path: str
    manifest: dict[str, Any]
    manifest_sha256: str
    root: str
    parent: str
    candidate: str
    seed: dict[str, str]
    seed_manifest_digest: str
    seed_files: int
    seed_bytes: int
    authentication: dict[str, Any]
    files: dict[str, dict[str, Any]]
    toolchain_manifest: list[dict[str, Any]]
    toolchain_digest: str
    toolchain_files: int
    toolchain_bytes: int
    plan_digest: str


def read_manifest(path: str) -> tuple[dict[str, Any], str]:
    canonical_absolute(path, "provisioning manifest")
    st, digest, size = require_file(
        path, "provisioning manifest", exact_mode=0o600, maximum=MAX_MANIFEST_BYTES
    )
    del st
    try:
        with open(path, "rb") as handle:
            raw = handle.read(size + 1)
    except OSError as exc:
        fail(f"cannot read provisioning manifest: {exc.strerror}")
    if sha256_bytes(raw) != digest:
        fail("provisioning manifest changed while it was read")
    manifest = parse_json(raw, "provisioning manifest")
    return manifest, sha256_bytes(canonical_json(manifest))


def prepare(manifest_path: str, deploy_root: str, *, require_absent: bool) -> Prepared:
    manifest, manifest_digest = read_manifest(manifest_path)
    exact_keys(
        manifest,
        (
            "schema",
            "candidate_commit",
            "deploy_root",
            "source_repository",
            "authoritative_remote",
            "inputs",
            "limits",
        ),
        "provisioning manifest",
    )
    if manifest["schema"] != MANIFEST_SCHEMA:
        fail("provisioning manifest schema mismatch")
    candidate = manifest["candidate_commit"]
    if not isinstance(candidate, str) or not HEX40.fullmatch(candidate):
        fail("candidate commit is invalid")
    root = canonical_absolute(deploy_root, "deployment root", must_exist=False)
    if manifest["deploy_root"] != root:
        fail("manifest deployment root does not match the command")
    if manifest["authoritative_remote"] != REMOTE_URL:
        fail("manifest authoritative remote is not exact")
    parent, _ = validate_parent(root)
    if require_absent and os.path.lexists(root):
        fail("deployment root already exists")
    source_repo = canonical_absolute(
        manifest["source_repository"], "bootstrap source repository"
    )
    validate_trusted_ancestors(source_repo, "bootstrap source repository")
    if paths_overlap(root, source_repo):
        fail("bootstrap source repository and deployment root must not overlap")
    seed = validate_seed(source_repo, candidate)

    inputs = manifest["inputs"]
    if not isinstance(inputs, dict):
        fail("manifest inputs must be an object")
    common_input_keys = {"known_hosts", "toolchain", "machine_env", "credentials"}
    observed_input_keys = set(inputs)
    file_auth_keys = common_input_keys | {"gitlab_deploy_key"}
    agent_auth_keys = common_input_keys | {"gitlab_authentication"}
    if observed_input_keys not in (file_auth_keys, agent_auth_keys):
        fail("manifest inputs keys are not exact")
    files: dict[str, dict[str, Any]] = {}
    for name in ("known_hosts", "machine_env", "credentials"):
        path, expected = input_spec(inputs[name], name)
        _, digest, size = require_file(path, name, exact_mode=0o600)
        if digest != expected:
            fail(f"{name} input digest mismatch")
        files[name] = {"path": path, "sha256": digest, "size": size}
    if observed_input_keys == file_auth_keys:
        path, expected = input_spec(inputs["gitlab_deploy_key"], "gitlab_deploy_key")
        _, digest, size = require_file(path, "gitlab_deploy_key", exact_mode=0o600)
        if digest != expected:
            fail("gitlab_deploy_key input digest mismatch")
        files["gitlab_deploy_key"] = {"path": path, "sha256": digest, "size": size}
        validate_private_key(path)
        authentication = {"mode": "file"}
    else:
        authentication, public_fact = validate_agent_authentication(
            inputs["gitlab_authentication"]
        )
        files["gitlab_agent_public_key"] = public_fact
    validate_known_hosts(files["known_hosts"]["path"])

    tool = inputs["toolchain"]
    if not isinstance(tool, dict):
        fail("toolchain input must be an object")
    exact_keys(tool, ("path",), "toolchain input")
    tool_path = canonical_absolute(tool["path"], "toolchain input")
    validate_trusted_ancestors(tool_path, "toolchain input")
    if paths_overlap(root, tool_path):
        fail("toolchain input and deployment root must not overlap")

    limits = manifest["limits"]
    if not isinstance(limits, dict):
        fail("manifest limits must be an object")
    exact_keys(
        limits,
        (
            "max_source_files",
            "max_source_bytes",
            "max_toolchain_files",
            "max_toolchain_bytes",
            "min_free_bytes_after",
        ),
        "manifest limits",
    )
    for key in limits:
        if type(limits[key]) is not int or limits[key] < 0:
            fail(f"manifest limit {key} is invalid")
    if not 1 <= limits["max_toolchain_files"] <= HARD_MAX_FILES:
        fail("toolchain file limit is outside the hard bound")
    if not 1 <= limits["max_toolchain_bytes"] <= HARD_MAX_BYTES:
        fail("toolchain byte limit is outside the hard bound")
    if not 1 <= limits["max_source_files"] <= HARD_MAX_FILES:
        fail("source file limit is outside the hard bound")
    if not 1 <= limits["max_source_bytes"] <= HARD_MAX_BYTES:
        fail("source byte limit is outside the hard bound")
    if limits["min_free_bytes_after"] < MIN_FREE_AFTER_FLOOR:
        fail("free-space reserve is below the fixed safety floor")
    _, seed_manifest_digest, seed_files, seed_bytes = tree_manifest(
        source_repo,
        max_files=limits["max_source_files"],
        max_bytes=limits["max_source_bytes"],
    )
    tool_manifest, tool_digest, tool_files, tool_bytes = tree_manifest(
        tool_path,
        max_files=limits["max_toolchain_files"],
        max_bytes=limits["max_toolchain_bytes"],
        normalize_private_modes=True,
    )
    for required in ("bin/cargo", "bin/rustc"):
        record = next((item for item in tool_manifest if item["path"] == required), None)
        if record is None or record["type"] != "file" or not (record["mode"] & 0o100):
            fail(f"toolchain is missing executable {required}")

    input_snapshot = {
        "candidate_commit": candidate,
        "authentication": authentication,
        "files": {name: {"sha256": fact["sha256"], "size": fact["size"]} for name, fact in files.items()},
        "manifest_sha256": manifest_digest,
        "seed": seed,
        "seed_manifest_digest": seed_manifest_digest,
        "seed_files": seed_files,
        "seed_bytes": seed_bytes,
        "toolchain_manifest_sha256": tool_digest,
        "toolchain_files": tool_files,
        "toolchain_bytes": tool_bytes,
    }
    plan_digest = sha256_bytes(PLAN_DOMAIN + canonical_json(input_snapshot))
    return Prepared(
        manifest_path=manifest_path,
        manifest=manifest,
        manifest_sha256=manifest_digest,
        root=root,
        parent=parent,
        candidate=candidate,
        seed=seed,
        seed_manifest_digest=seed_manifest_digest,
        seed_files=seed_files,
        seed_bytes=seed_bytes,
        authentication=authentication,
        files=files,
        toolchain_manifest=tool_manifest,
        toolchain_digest=tool_digest,
        toolchain_files=tool_files,
        toolchain_bytes=tool_bytes,
        plan_digest=plan_digest,
    )


def copy_file(source: str, target: str, mode: int = 0o600) -> dict[str, Any]:
    before_digest, before_size = sha256_file(source)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    source_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    source_fd = os.open(source, source_flags)
    digest = hashlib.sha256()
    total = 0
    try:
        target_fd = os.open(target, flags, mode)
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
            os.fchmod(target_fd, mode)
            os.fsync(target_fd)
        finally:
            os.close(target_fd)
    finally:
        os.close(source_fd)
    after_digest, after_size = sha256_file(source)
    if (before_digest, before_size) != (after_digest, after_size):
        fail("input file changed while it was copied")
    if (digest.hexdigest(), total) != (before_digest, before_size):
        fail("copied file does not match its input")
    return {"mode": mode, "sha256": before_digest, "size": before_size}


def normalize_private_tree(root: str) -> None:
    directories: list[str] = [root]
    files: list[str] = []
    for _, entry, st in iter_tree(root):
        if stat.S_ISLNK(st.st_mode):
            fail("copied tree contains a symlink")
        if stat.S_ISDIR(st.st_mode):
            directories.append(entry.path)
        elif stat.S_ISREG(st.st_mode) and st.st_nlink == 1:
            files.append(entry.path)
        else:
            fail("copied tree contains an unsafe inode")
    for path in directories:
        os.chmod(path, 0o700)
    for path in files:
        current = mode_bits(os.lstat(path))
        os.chmod(path, 0o700 if current & 0o100 else 0o600)


def copy_toolchain(prepared: Prepared, target: str) -> None:
    source = prepared.manifest["inputs"]["toolchain"]["path"]
    shutil.copytree(source, target, symlinks=True)
    normalize_private_tree(target)
    _, digest, files, size = tree_manifest(
        target,
        max_files=prepared.manifest["limits"]["max_toolchain_files"],
        max_bytes=prepared.manifest["limits"]["max_toolchain_bytes"],
    )
    if (digest, files, size) != (
        prepared.toolchain_digest,
        prepared.toolchain_files,
        prepared.toolchain_bytes,
    ):
        fail("copied toolchain tree drifted from the admitted input")


def clone_source(prepared: Prepared, target: str, home: str) -> tuple[str, str, int, int]:
    source = prepared.manifest["source_repository"]
    git_run(
        None,
        (
            "clone",
            "--no-local",
            "--no-hardlinks",
            "--no-checkout",
            "-o",
            "gitlab",
            source,
            target,
        ),
        home=home,
        timeout=120,
    )
    git_run(target, ("remote", "set-url", "gitlab", REMOTE_URL), home=home)
    git_run(
        target,
        ("update-ref", "refs/remotes/gitlab/master", prepared.candidate),
        home=home,
    )
    git_run(target, ("checkout", "-q", "-B", "master", prepared.candidate), home=home)
    normalize_private_tree(target)
    for relative, required_mode in ORCHESTRATOR_MODES.items():
        path = os.path.join(target, relative)
        require_file(path, f"trusted source {relative}")
        os.chmod(path, required_mode)
    head = git_value(target, ("rev-parse", "--verify", "HEAD^{commit}"), home)
    remote = git_value(
        target,
        ("rev-parse", "--verify", "refs/remotes/gitlab/master^{commit}"),
        home,
    )
    url = git_value(target, ("config", "--local", "--get", "remote.gitlab.url"), home)
    if (head, remote, url) != (prepared.candidate, prepared.candidate, REMOTE_URL):
        fail("copied source authority drifted")
    _, digest, files, size = tree_manifest(
        target, max_files=HARD_MAX_FILES, max_bytes=HARD_MAX_BYTES
    )
    return prepared.seed["tree"], digest, files, size


def fsync_tree(root: str) -> None:
    directories: list[str] = []
    for _, entry, st in iter_tree(root):
        if stat.S_ISREG(st.st_mode):
            fd = os.open(entry.path, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        elif stat.S_ISDIR(st.st_mode):
            directories.append(entry.path)
        else:
            fail("cannot sync an unsafe inode")
    directories.sort(key=lambda path: path.count(os.sep), reverse=True)
    directories.append(root)
    for path in directories:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def fsync_dir(path: str) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def remove_stage(path: str, parent: str) -> None:
    if not path.startswith(parent + "/.") or not os.path.basename(path).startswith("."):
        fail("refusing to clean an unproven provisioning stage")
    if not os.path.lexists(path):
        return
    for _, entry, st in list(iter_tree(path)):
        if stat.S_ISLNK(st.st_mode) or not (stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode)):
            fail("refusing to clean a stage containing an unsafe inode")
    shutil.rmtree(path)
    fsync_dir(parent)


def free_capacity(prepared: Prepared) -> None:
    usage = shutil.disk_usage(prepared.parent)
    estimated = (
        prepared.seed_bytes
        + prepared.toolchain_bytes
        + sum(item["size"] for item in prepared.files.values())
    )
    if usage.free - estimated < prepared.manifest["limits"]["min_free_bytes_after"]:
        fail("insufficient capacity after the required provisioning reserve")


def confirmation(prepared: Prepared) -> str:
    return f"PROVISION:{prepared.candidate}:{prepared.plan_digest}"


def stable_result(command: str, status_value: str, **values: Any) -> dict[str, Any]:
    return {"schema": RESULT_SCHEMA, "command": command, "status": status_value, **values}


def command_plan(manifest_path: str, deploy_root: str) -> dict[str, Any]:
    prepared = prepare(manifest_path, deploy_root, require_absent=True)
    free_capacity(prepared)
    return stable_result(
        "plan",
        "ready",
        candidate_commit=prepared.candidate,
        confirmation=confirmation(prepared),
        manifest_sha256=prepared.manifest_sha256,
        plan_digest=prepared.plan_digest,
        source_bytes=prepared.seed_bytes,
        source_files=prepared.seed_files,
        toolchain_bytes=prepared.toolchain_bytes,
        toolchain_files=prepared.toolchain_files,
    )


def build_receipt(
    prepared: Prepared,
    stage: str,
    source_tree: str,
    source_digest: str,
    source_files: int,
    source_bytes: int,
    installed_files: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    root_st = require_directory(stage, "provisioning stage", exact_mode=0o700)
    lock_path = os.path.join(stage, "publisher-state/deploy/publisher.kernel.lock")
    lock_st, lock_sha, lock_size = require_file(
        lock_path, "publisher kernel lock", exact_mode=0o600
    )
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "candidate_commit": prepared.candidate,
        "authoritative_remote": REMOTE_URL,
        "authority_state": "bootstrap_seed_not_publication_authority",
        "deploy_root": prepared.root,
        "deploy_root_identity": {
            "dev": root_st.st_dev,
            "ino": root_st.st_ino,
            "mode": mode_bits(root_st),
            "uid": root_st.st_uid,
        },
        "manifest_sha256": prepared.manifest_sha256,
        "plan_digest": prepared.plan_digest,
        "source_commit": prepared.candidate,
        "source_tree": source_tree,
        "source_manifest_digest": source_digest,
        "source_files": source_files,
        "source_bytes": source_bytes,
        "toolchain_manifest_digest": prepared.toolchain_digest,
        "toolchain_files": prepared.toolchain_files,
        "toolchain_bytes": prepared.toolchain_bytes,
        "installed_inputs": installed_files,
        "publisher_lock": {
            "dev": lock_st.st_dev,
            "ino": lock_st.st_ino,
            "mode": mode_bits(lock_st),
            "sha256": lock_sha,
            "size": lock_size,
            "uid": lock_st.st_uid,
        },
        "provisioned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    receipt["receipt_digest"] = sha256_bytes(RECEIPT_DOMAIN + canonical_json(receipt))
    return receipt


def write_json_file(path: str, value: dict[str, Any], mode: int = 0o600) -> None:
    raw = canonical_json(value) + b"\n"
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
        mode,
    )
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fchmod(fd, mode)
        os.fsync(fd)
    finally:
        os.close(fd)


def rename_noreplace(source: str, destination: str) -> None:
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError:
        fail("atomic no-replace deployment-root activation is unavailable")
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1) == 0:
        return
    observed = ctypes.get_errno()
    if observed in (errno.EEXIST, errno.ENOTEMPTY):
        fail("deployment root appeared during atomic activation")
    fail(f"atomic no-replace deployment-root activation failed: {os.strerror(observed)}")


def command_provision(
    manifest_path: str, deploy_root: str, supplied_confirmation: str | None
) -> dict[str, Any]:
    prepared = prepare(manifest_path, deploy_root, require_absent=True)
    free_capacity(prepared)
    if supplied_confirmation != confirmation(prepared):
        fail("provision confirmation must exactly bind the candidate and input plan")
    stage = os.path.join(
        prepared.parent,
        f".{os.path.basename(prepared.root)}.provision-stage.{prepared.plan_digest[:24]}",
    )
    if os.path.lexists(stage):
        fail("deterministic provisioning stage already exists")
    created = False
    try:
        os.mkdir(stage, 0o700)
        created = True
        for relative in (
            "source",
            "config",
            "config/git",
            "config/agent-bridge",
            "build-cache",
            "publisher-state",
            "publisher-state/deploy",
            "provisioning",
        ):
            os.mkdir(os.path.join(stage, relative), 0o700)

        installed_files: dict[str, dict[str, Any]] = {}
        targets = {
            "known_hosts": "config/git/known_hosts",
            "machine_env": "config/agent-bridge/machine.env",
            "credentials": "config/agent-bridge/credentials",
        }
        if prepared.authentication["mode"] == "file":
            targets["gitlab_deploy_key"] = "config/git/gitlab_deploy_key"
        else:
            targets["gitlab_agent_public_key"] = "config/git/gitlab_agent_key.pub"
        for name, relative in targets.items():
            fact = copy_file(prepared.files[name]["path"], os.path.join(stage, relative))
            if fact["sha256"] != prepared.files[name]["sha256"]:
                fail(f"installed {name} digest drifted")
            installed_files[name] = {"path": relative, **fact}
        if prepared.authentication["mode"] == "agent_socket":
            descriptor_relative = "config/git/authentication.json"
            descriptor_path = os.path.join(stage, descriptor_relative)
            descriptor = {
                "schema": AGENT_AUTH_SCHEMA,
                "mode": "agent_socket",
                "socket_path": prepared.authentication["socket_path"],
                "public_key_fingerprint": prepared.authentication["public_key_fingerprint"],
                "public_key_path": "gitlab_agent_key.pub",
            }
            write_json_file(descriptor_path, descriptor)
            _, descriptor_digest, descriptor_size = require_file(
                descriptor_path, "installed gitlab_authentication", exact_mode=0o600
            )
            installed_files["gitlab_authentication"] = {
                "path": descriptor_relative,
                "mode": 0o600,
                "sha256": descriptor_digest,
                "size": descriptor_size,
            }

        copy_toolchain(prepared, os.path.join(stage, "toolchain"))
        source_tree, source_digest, source_files, source_bytes = clone_source(
            prepared, os.path.join(stage, "source/agent-bridge"), stage
        )

        lock_path = os.path.join(stage, "publisher-state/deploy/publisher.kernel.lock")
        write_json_file(
            os.path.join(stage, "provisioning/manifest.json"), prepared.manifest
        )
        lock_fd = os.open(
            lock_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
            0o600,
        )
        try:
            os.fchmod(lock_fd, 0o600)
            os.fsync(lock_fd)
        finally:
            os.close(lock_fd)

        tool_manifest, tool_digest, tool_files, tool_bytes = tree_manifest(
            os.path.join(stage, "toolchain"),
            max_files=prepared.manifest["limits"]["max_toolchain_files"],
            max_bytes=prepared.manifest["limits"]["max_toolchain_bytes"],
        )
        if (tool_digest, tool_files, tool_bytes) != (
            prepared.toolchain_digest,
            prepared.toolchain_files,
            prepared.toolchain_bytes,
        ):
            fail("installed toolchain drifted before receipt")
        receipt = build_receipt(
            prepared,
            stage,
            source_tree,
            source_digest,
            source_files,
            source_bytes,
            installed_files,
        )
        write_json_file(os.path.join(stage, "provisioning/current.json"), receipt)
        fsync_tree(stage)
        fsync_dir(prepared.parent)
        if os.path.lexists(prepared.root):
            fail("deployment root appeared before atomic activation")
        rename_noreplace(stage, prepared.root)
        created = False
        fsync_dir(prepared.parent)
        return stable_result(
            "provision",
            "provisioned_bootstrap",
            candidate_commit=prepared.candidate,
            receipt_digest=receipt["receipt_digest"],
        )
    except BaseException:
        if created and os.path.lexists(stage):
            remove_stage(stage, prepared.parent)
        raise


def load_stored(root: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = os.path.join(root, "provisioning/manifest.json")
    receipt_path = os.path.join(root, "provisioning/current.json")
    _, manifest_sha, manifest_size = require_file(
        manifest_path, "stored provisioning manifest", exact_mode=0o600, maximum=MAX_MANIFEST_BYTES
    )
    _, receipt_sha, receipt_size = require_file(
        receipt_path, "provisioning receipt", exact_mode=0o600, maximum=8 * 1024 * 1024
    )
    del manifest_sha, receipt_sha
    with open(manifest_path, "rb") as handle:
        manifest = parse_json(handle.read(manifest_size + 1), "stored provisioning manifest")
    with open(receipt_path, "rb") as handle:
        receipt = parse_json(handle.read(receipt_size + 1), "provisioning receipt")
    return manifest, receipt


def verify_receipt(root: str, inherited_lock_fd: int | None = None) -> dict[str, Any]:
    root = canonical_absolute(root, "deployment root")
    root_st = require_directory(root, "deployment root", exact_mode=0o700)
    manifest, receipt = load_stored(root)
    exact_keys(
        receipt,
        (
            "schema",
            "candidate_commit",
            "authoritative_remote",
            "authority_state",
            "deploy_root",
            "deploy_root_identity",
            "manifest_sha256",
            "plan_digest",
            "source_commit",
            "source_tree",
            "source_manifest_digest",
            "source_files",
            "source_bytes",
            "toolchain_manifest_digest",
            "toolchain_files",
            "toolchain_bytes",
            "installed_inputs",
            "publisher_lock",
            "provisioned_at",
            "receipt_digest",
        ),
        "provisioning receipt",
    )
    digest_body = dict(receipt)
    observed_digest = digest_body.pop("receipt_digest")
    if not isinstance(observed_digest, str) or not HEX64.fullmatch(observed_digest):
        fail("provisioning receipt digest is invalid")
    if sha256_bytes(RECEIPT_DOMAIN + canonical_json(digest_body)) != observed_digest:
        fail("provisioning receipt digest mismatch")
    if receipt["schema"] != RECEIPT_SCHEMA:
        fail("provisioning receipt schema mismatch")
    if receipt["authority_state"] != "bootstrap_seed_not_publication_authority":
        fail("provisioning receipt authority state is invalid")
    if receipt["deploy_root"] != root or receipt["authoritative_remote"] != REMOTE_URL:
        fail("provisioning receipt root or remote binding drifted")
    identity = receipt["deploy_root_identity"]
    if identity != {
        "dev": root_st.st_dev,
        "ino": root_st.st_ino,
        "mode": mode_bits(root_st),
        "uid": root_st.st_uid,
    }:
        fail("provisioned deployment-root identity drifted")
    stored_manifest_raw = canonical_json(manifest)
    if sha256_bytes(stored_manifest_raw) != receipt["manifest_sha256"]:
        fail("stored provisioning manifest binding drifted")
    if manifest.get("deploy_root") != root or manifest.get("candidate_commit") != receipt["candidate_commit"]:
        fail("stored provisioning manifest identity drifted")

    source = os.path.join(root, "source/agent-bridge")
    require_directory(source, "trusted source repository", exact_mode=0o700)
    head = git_value(source, ("rev-parse", "--verify", "HEAD^{commit}"), root)
    remote = git_value(
        source,
        ("rev-parse", "--verify", "refs/remotes/gitlab/master^{commit}"),
        root,
    )
    url = git_value(source, ("config", "--local", "--get", "remote.gitlab.url"), root)
    if head != remote or url != REMOTE_URL or not HEX40.fullmatch(head):
        fail("provisioned source authority drifted")
    validate_local_git_config(source, root)
    try:
        git_run(
            source,
            ("merge-base", "--is-ancestor", receipt["source_commit"], head),
            home=root,
        )
    except ProvisionError:
        fail("current source candidate is not a descendant of the provisioned seed")
    if git_run(
        source,
        ("status", "--porcelain=v1", "--untracked-files=all"),
        home=root,
    ):
        fail("provisioned source repository is not clean")
    reject_gitlinks(source, head, root, "provisioned source candidate")
    for relative in (
        ".git/info/attributes",
        ".git/info/grafts",
        ".git/objects/info/alternates",
        ".git/objects/info/http-alternates",
    ):
        if os.path.lexists(os.path.join(source, relative)):
            fail("provisioned source contains a forbidden Git override")
    source_manifest, _, _, _ = tree_manifest(
        source, max_files=HARD_MAX_FILES, max_bytes=HARD_MAX_BYTES
    )
    for record in source_manifest:
        if record["type"] == "directory" and record["mode"] != 0o700:
            fail("provisioned source contains a non-private directory")
        if record["type"] == "file" and record["mode"] not in (0o600, 0o700):
            fail("provisioned source contains a non-private file")
    expected_script = os.path.join(source, "scripts/provision-trusted-deployment-root.py")
    require_file(expected_script, "trusted provisioning verifier", exact_mode=0o700)
    if os.path.realpath(__file__) != expected_script:
        fail("verify must run from the fixed trusted provisioning tool")
    for relative, required_mode in ORCHESTRATOR_MODES.items():
        path = os.path.join(source, relative)
        _, digest, _ = require_file(path, f"trusted source {relative}", exact_mode=required_mode)
        candidate_bytes = git_run(
            source,
            ("show", "--no-textconv", "--no-ext-diff", f"{head}:{relative}"),
            home=root,
        )
        if digest != sha256_bytes(candidate_bytes):
            fail(f"trusted source {relative} does not match the current candidate")

    tool = os.path.join(root, "toolchain")
    _, tool_digest, tool_files, tool_bytes = tree_manifest(
        tool,
        max_files=manifest["limits"]["max_toolchain_files"],
        max_bytes=manifest["limits"]["max_toolchain_bytes"],
    )
    if (tool_digest, tool_files, tool_bytes) != (
        receipt["toolchain_manifest_digest"],
        receipt["toolchain_files"],
        receipt["toolchain_bytes"],
    ):
        fail("provisioned toolchain manifest drifted")

    installed_inputs = receipt["installed_inputs"]
    file_inputs = {"gitlab_deploy_key", "known_hosts", "machine_env", "credentials"}
    agent_inputs = {
        "gitlab_agent_public_key", "gitlab_authentication",
        "known_hosts", "machine_env", "credentials",
    }
    if not isinstance(installed_inputs, dict) or set(installed_inputs) not in (file_inputs, agent_inputs):
        fail("provisioning receipt installed inputs are not exact")
    for name, fact in installed_inputs.items():
        if not isinstance(fact, dict):
            fail(f"installed {name} receipt fact must be an object")
        exact_keys(fact, ("mode", "path", "sha256", "size"), f"installed {name} fact")
        if not isinstance(fact["path"], str) or fact["path"].startswith("/") or ".." in fact["path"].split("/"):
            fail(f"installed {name} receipt path is invalid")
        path = os.path.join(root, fact["path"])
        _, digest, size = require_file(path, f"installed {name}", exact_mode=0o600)
        if {"mode": 0o600, "path": fact["path"], "sha256": digest, "size": size} != fact:
            fail(f"installed {name} drifted")
    if set(installed_inputs) == agent_inputs:
        descriptor_path = os.path.join(root, installed_inputs["gitlab_authentication"]["path"])
        try:
            with open(descriptor_path, "rb") as handle:
                descriptor = parse_json(
                    handle.read(installed_inputs["gitlab_authentication"]["size"] + 1),
                    "installed GitLab authentication",
                )
        except OSError as exc:
            fail(f"cannot read installed GitLab authentication: {exc.strerror}")
        exact_keys(
            descriptor,
            ("schema", "mode", "socket_path", "public_key_fingerprint", "public_key_path"),
            "installed GitLab authentication",
        )
        if (
            descriptor["schema"] != AGENT_AUTH_SCHEMA
            or descriptor["mode"] != "agent_socket"
            or descriptor["public_key_path"] != "gitlab_agent_key.pub"
            or not isinstance(descriptor["socket_path"], str)
            or not SAFE_AGENT_PATH.fullmatch(descriptor["socket_path"])
            or not isinstance(descriptor["public_key_fingerprint"], str)
            or not SSH_SHA256.fullmatch(descriptor["public_key_fingerprint"])
        ):
            fail("installed GitLab authentication contract is invalid")
        manifest_auth = manifest.get("inputs", {}).get("gitlab_authentication")
        if (
            not isinstance(manifest_auth, dict)
            or manifest_auth.get("mode") != "agent_socket"
            or manifest_auth.get("socket_path") != descriptor["socket_path"]
            or manifest_auth.get("public_key_fingerprint")
            != descriptor["public_key_fingerprint"]
        ):
            fail("stored GitLab agent authentication binding drifted")
        public_path = os.path.join(root, installed_inputs["gitlab_agent_public_key"]["path"])
        if public_key_fingerprint(public_path) != descriptor["public_key_fingerprint"]:
            fail("installed GitLab agent public-key identity drifted")

    lock_path = os.path.join(root, "publisher-state/deploy/publisher.kernel.lock")
    lock_st, lock_sha, lock_size = require_file(
        lock_path, "publisher kernel lock", exact_mode=0o600
    )
    lock_fact = {
        "dev": lock_st.st_dev,
        "ino": lock_st.st_ino,
        "mode": mode_bits(lock_st),
        "sha256": lock_sha,
        "size": lock_size,
        "uid": lock_st.st_uid,
    }
    if lock_fact != receipt["publisher_lock"]:
        fail("publisher kernel lock identity drifted")
    if inherited_lock_fd is not None:
        try:
            opened = os.fstat(inherited_lock_fd)
        except OSError:
            fail("inherited publisher lock descriptor is invalid")
        if (opened.st_dev, opened.st_ino, mode_bits(opened), opened.st_uid) != (
            lock_st.st_dev,
            lock_st.st_ino,
            mode_bits(lock_st),
            lock_st.st_uid,
        ):
            fail("inherited publisher lock descriptor does not identify the fixed lock")
    return stable_result(
        "verify",
        "verified_provisioning_custody",
        candidate_commit=head,
        receipt_digest=observed_digest,
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    for name in ("plan", "provision"):
        command = sub.add_parser(name)
        command.add_argument("--manifest", required=True)
        command.add_argument("--deploy-root", required=True)
        if name == "provision":
            command.add_argument("--confirm")
    verify = sub.add_parser("verify")
    verify.add_argument("--deploy-root", required=True)
    verify.add_argument("--inherited-lock-fd", type=int)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    previous_umask = os.umask(0o077)
    try:
        args = parser().parse_args(argv)
        if args.command == "plan":
            value = command_plan(args.manifest, args.deploy_root)
        elif args.command == "provision":
            value = command_provision(args.manifest, args.deploy_root, args.confirm)
        else:
            value = verify_receipt(args.deploy_root, args.inherited_lock_fd)
        sys.stdout.buffer.write(canonical_json(value) + b"\n")
        return 0
    except ProvisionError as exc:
        sys.stderr.write(f"trusted-root provisioning blocked: {exc}\n")
        return 1
    finally:
        os.umask(previous_umask)


if __name__ == "__main__":
    raise SystemExit(main())
