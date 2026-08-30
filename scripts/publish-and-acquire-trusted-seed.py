#!/usr/bin/python3
"""Publish one exact candidate to a governed authority and acquire its seed.

``plan`` and ``verify`` are read-only. ``publish`` is the only remote writer
and requires an exact confirmation. ``acquire-seed`` creates only an absent
local seed using a private sibling stage. CI is explicitly skipped on push.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any, NoReturn, Sequence

SCHEMA = "agent_bridge.trusted_publication_seed_manifest.v1"
RESULT = "agent_bridge.trusted_publication_seed_result.v1"
REMOTE = "git@gitlab.com:pallasting/agent-bridge.git"
AUTHORITIES = {
    "git@gitlab.com:pallasting/agent-bridge.git": {
        "name": "gitlab", "host": "gitlab.com", "ci_policy": "push_option",
    },
    "git@github.com:pallasting/Agent-Bridge.git": {
        "name": "github", "host": "github.com", "ci_policy": "commit_message",
    },
}
DOMAIN = b"agent-bridge/trusted-publication-seed/v1\0"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_PATH = re.compile(r"^/[A-Za-z0-9._/-]+$")


class Blocked(RuntimeError):
    pass


def fail(message: str) -> NoReturn:
    raise Blocked(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def strict_json(path: str) -> tuple[dict[str, Any], str]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                fail(f"manifest contains duplicate key {key}")
            result[key] = value
        return result
    try:
        with open(path, "rb") as handle:
            raw = handle.read(1024 * 1024 + 1)
    except OSError as exc:
        fail(f"cannot read manifest: {exc.strerror}")
    if len(raw) > 1024 * 1024:
        fail("manifest is too large")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"manifest is not strict JSON: {exc}")
    if not isinstance(value, dict):
        fail("manifest must be an object")
    return value, digest(canonical(value))


def physical(path: Any, label: str, *, exists: bool = True) -> str:
    if not isinstance(path, str) or not SAFE_PATH.fullmatch(path) or os.path.normpath(path) != path:
        fail(f"{label} must be a canonical shell-safe absolute path")
    current = "/"
    parts = path.split("/")[1:]
    for index, part in enumerate(parts):
        current = os.path.join(current, part)
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            if exists or index != len(parts) - 1:
                fail(f"{label} does not exist")
            break
        if stat.S_ISLNK(st.st_mode):
            fail(f"{label} must not traverse symlinks")
    return path


def trusted_ancestors(path: str, label: str) -> None:
    current = os.path.dirname(path)
    while True:
        st = os.lstat(current)
        mode = stat.S_IMODE(st.st_mode)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid not in (0, os.geteuid()):
            fail(f"{label} has an untrusted ancestor")
        if mode & 0o022 and not (st.st_uid == 0 and mode & 0o1000):
            fail(f"{label} has a replaceable ancestor")
        if current == "/": break
        current = os.path.dirname(current)


def private_file(
    path: str,
    label: str,
    *,
    private_key: bool = False,
    known_host: str | None = None,
) -> str:
    physical(path, label)
    trusted_ancestors(path, label)
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.geteuid():
        fail(f"{label} must be an owned singly-linked regular file")
    if stat.S_IMODE(st.st_mode) != 0o600:
        fail(f"{label} mode must be 0600")
    with open(path, "rb") as handle:
        raw = handle.read(256 * 1024 + 1)
    if not raw or len(raw) > 256 * 1024 or b"\x00" in raw:
        fail(f"{label} content is invalid")
    if private_key and not raw.startswith(b"-----BEGIN OPENSSH PRIVATE KEY-----\n"):
        fail(f"{label} is not an OpenSSH private key")
    if known_host is not None:
        lines = [line for line in raw.splitlines() if line and not line.startswith(b"#")]
        prefix = known_host.encode("ascii") + b" "
        if not lines or any(
            not (line.startswith(prefix) or line.startswith(b"|1|")) for line in lines
        ):
            fail(f"{label} contains a non-{known_host} host")
    return digest(raw)


def private_parent(path: str) -> str:
    parent = os.path.dirname(path)
    physical(parent, "seed parent")
    trusted_ancestors(parent, "seed parent")
    st = os.lstat(parent)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        fail("seed parent must be an owned physical mode-0700 directory")
    return parent


def agent_fingerprints(socket_path: str) -> set[str]:
    try:
        result = subprocess.run(
            ["/usr/bin/ssh-add", "-l"],
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "SSH_AUTH_SOCK": socket_path},
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        fail("bounded SSH agent inventory failed")
    if result.returncode:
        fail("SSH agent inventory is unavailable")
    try:
        values = {line.split()[1] for line in result.stdout.decode("ascii").splitlines()}
    except (UnicodeDecodeError, IndexError):
        fail("SSH agent inventory is malformed")
    if not values:
        fail("SSH agent contains no identities")
    return values


def public_key_fingerprint(path: str) -> str:
    try:
        result = subprocess.run(
            ["/usr/bin/ssh-keygen", "-E", "sha256", "-lf", path],
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        fail("bounded agent public-key inspection failed")
    if result.returncode:
        fail("agent public key is invalid")
    try:
        return result.stdout.decode("ascii").split()[1]
    except (UnicodeDecodeError, IndexError):
        fail("agent public-key fingerprint is malformed")


def ssh_command(value: dict[str, Any]) -> str:
    known_hosts = value["known_hosts"]
    common = ("/usr/bin/ssh -F /dev/null -o BatchMode=yes -o StrictHostKeyChecking=yes "
              f"-o UserKnownHostsFile={known_hosts} -o GlobalKnownHostsFile=/dev/null ")
    if value["auth_mode"] == "file":
        return common + ("-o IdentitiesOnly=yes -o IdentityAgent=none "
                         f"-o IdentityFile={value['deploy_key']}")
    return common + ("-o IdentitiesOnly=yes "
                     f"-o IdentityFile={value['agent_public_key']} "
                     f"-o IdentityAgent={value['agent_socket']}")


def assert_auth_binding(value: dict[str, Any]) -> None:
    if private_file(
        value["known_hosts"], "authority known-hosts",
        known_host=value["authority_host"],
    ) != value["known_hosts_sha256"]:
        fail("authority known-hosts changed after planning")
    if value["auth_mode"] == "file":
        if private_file(
            value["deploy_key"], "authority deploy key", private_key=True
        ) != value["key_sha256"]:
            fail("authority deploy key changed after planning")
        return
    public_key = value["agent_public_key"]
    if private_file(public_key, "SSH agent public key") != value["agent_public_key_sha256"]:
        fail("SSH agent public key changed after planning")
    if public_key_fingerprint(public_key) != value["agent_socket_identity"]["public_key_fingerprint"]:
        fail("SSH agent public-key identity changed after planning")
    socket_path = value["agent_socket"]
    physical(socket_path, "SSH agent socket")
    trusted_ancestors(socket_path, "SSH agent socket")
    socket_st = os.lstat(socket_path)
    observed = {
        "dev": socket_st.st_dev, "ino": socket_st.st_ino,
        "mode": stat.S_IMODE(socket_st.st_mode), "uid": socket_st.st_uid,
        "public_key_fingerprint": value["agent_socket_identity"]["public_key_fingerprint"],
    }
    if not stat.S_ISSOCK(socket_st.st_mode) or observed != value["agent_socket_identity"]:
        fail("SSH agent socket changed after planning")
    if observed["public_key_fingerprint"] not in agent_fingerprints(socket_path):
        fail("required SSH agent identity disappeared after planning")


def git(args: Sequence[str], *, repo: str | None, value: dict[str, Any], timeout: int = 60) -> bytes:
    assert_auth_binding(value)
    command = ["/usr/bin/git", "--no-pager", "-c", "core.hooksPath=/dev/null", "-c", "core.attributesFile=/dev/null"]
    if repo:
        command += ["-C", repo]
    command += list(args)
    env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LANG": "C", "LC_ALL": "C",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
           "GIT_NO_REPLACE_OBJECTS": "1", "GIT_SSH_COMMAND": ssh_command(value)}
    try:
        result = subprocess.run(command, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        fail("bounded Git operation failed")
    if result.returncode:
        fail("authenticated authority Git operation failed")
    return result.stdout


def load(path: str) -> dict[str, Any]:
    physical(path, "manifest")
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o600:
        fail("manifest must be an owned physical mode-0600 file")
    value, manifest_sha = strict_json(path)
    legacy_keys = {"schema", "candidate_commit", "source_repository", "seed_path", "gitlab_deploy_key", "known_hosts"}
    agent_keys = {"schema", "candidate_commit", "source_repository", "seed_path", "authentication", "known_hosts"}
    governed_file_keys = {
        "schema", "candidate_commit", "source_repository", "seed_path",
        "authoritative_remote", "deploy_key", "known_hosts",
    }
    governed_agent_keys = {
        "schema", "candidate_commit", "source_repository", "seed_path",
        "authoritative_remote", "authentication", "known_hosts",
    }
    observed_keys = set(value)
    if observed_keys not in (
        legacy_keys, agent_keys, governed_file_keys, governed_agent_keys
    ):
        fail("manifest keys are not exact")
    if value["schema"] != SCHEMA or not isinstance(value["candidate_commit"], str) or not HEX40.fullmatch(value["candidate_commit"]):
        fail("manifest schema or candidate is invalid")
    for name in ("source_repository", "known_hosts"):
        physical(value[name], name)
    physical(value["seed_path"], "seed path", exists=False)
    remote_url = value.get("authoritative_remote", REMOTE)
    if remote_url in AUTHORITIES:
        authority = AUTHORITIES[remote_url]
    elif remote_url == REMOTE:
        # Deliberate test seam for an isolated local bare remote.
        authority = {
            "name": "gitlab", "host": "gitlab.com", "ci_policy": "push_option",
        }
    else:
        fail("authoritative remote is not an exact governed SSH URL")
    value["remote_url"] = remote_url
    value["remote_name"] = authority["name"]
    value["authority_host"] = authority["host"]
    value["ci_policy"] = authority["ci_policy"]
    value["manifest_sha256"] = manifest_sha
    value["known_hosts_sha256"] = private_file(
        value["known_hosts"], "authority known-hosts",
        known_host=value["authority_host"],
    )
    if observed_keys in (legacy_keys, governed_file_keys):
        key_name = "gitlab_deploy_key" if observed_keys == legacy_keys else "deploy_key"
        value["deploy_key"] = value[key_name]
        physical(value["deploy_key"], "deploy_key")
        value["key_sha256"] = private_file(
            value["deploy_key"], "authority deploy key", private_key=True
        )
        value["auth_mode"] = "file"
    else:
        authentication = value["authentication"]
        if not isinstance(authentication, dict) or set(authentication) != {"mode", "socket_path", "public_key_path", "public_key_fingerprint"}:
            fail("agent authentication keys are not exact")
        if authentication["mode"] != "agent_socket":
            fail("agent authentication mode is invalid")
        fingerprint = authentication["public_key_fingerprint"]
        if not isinstance(fingerprint, str) or not fingerprint.startswith("SHA256:") or len(fingerprint) > 128:
            fail("agent public-key fingerprint is invalid")
        socket_path = physical(authentication["socket_path"], "SSH agent socket")
        public_key_path = physical(authentication["public_key_path"], "SSH agent public key")
        public_key_sha = private_file(public_key_path, "SSH agent public key")
        if public_key_fingerprint(public_key_path) != fingerprint:
            fail("agent public key does not match the required fingerprint")
        trusted_ancestors(socket_path, "SSH agent socket")
        socket_st = os.lstat(socket_path)
        if not stat.S_ISSOCK(socket_st.st_mode) or socket_st.st_uid != os.geteuid() or stat.S_IMODE(socket_st.st_mode) != 0o600:
            fail("SSH agent socket custody is invalid")
        if fingerprint not in agent_fingerprints(socket_path):
            fail("required SSH agent identity is absent")
        value["auth_mode"] = "agent_socket"
        value["agent_socket"] = socket_path
        value["agent_public_key"] = public_key_path
        value["agent_public_key_sha256"] = public_key_sha
        value["agent_socket_identity"] = {
            "dev": socket_st.st_dev, "ino": socket_st.st_ino,
            "mode": stat.S_IMODE(socket_st.st_mode), "uid": socket_st.st_uid,
            "public_key_fingerprint": fingerprint,
        }
    private_parent(value["seed_path"])
    return value


def remote_head(value: dict[str, Any]) -> str | None:
    raw = git(
        ("ls-remote", "--heads", value["remote_url"], "refs/heads/master"),
        repo=None, value=value,
    )
    lines = raw.decode("ascii", "strict").splitlines()
    if not lines:
        return None
    if len(lines) != 1 or lines[0].split("\t")[-1] != "refs/heads/master" or not HEX40.fullmatch(lines[0].split("\t")[0]):
        fail("authority master advertisement is malformed")
    return lines[0].split("\t")[0]


def inspect(value: dict[str, Any]) -> tuple[str | None, str]:
    repo = value["source_repository"]
    candidate = value["candidate_commit"]
    head = git(("rev-parse", "--verify", "HEAD^{commit}"), repo=repo, value=value).decode().strip()
    if head != candidate:
        fail("local source HEAD does not equal the candidate")
    if git(("status", "--porcelain=v1", "--untracked-files=all"), repo=repo, value=value):
        fail("local source must be completely clean")
    remote = remote_head(value)
    if remote is None:
        fail("authoritative master is absent")
    if remote != candidate:
        git(("merge-base", "--is-ancestor", remote, candidate), repo=repo, value=value)
    plan = digest(DOMAIN + canonical({k: value[k] for k in sorted(value)} ) + (remote or "absent").encode())
    return remote, plan


def require_ci_skip_contract(value: dict[str, Any]) -> None:
    if value["ci_policy"] != "commit_message":
        return
    message = git(
        ("show", "-s", "--format=%B", value["candidate_commit"]),
        repo=value["source_repository"], value=value,
    ).decode("utf-8", "strict").lower()
    instructions = (
        "[skip ci]", "[ci skip]", "[no ci]", "[skip actions]", "[actions skip]",
        "skip-checks:true", "skip-checks: true",
    )
    if not any(instruction in message for instruction in instructions):
        fail("GitHub candidate commit lacks an exact workflow skip instruction")


def result(command: str, status_value: str, **extra: Any) -> dict[str, Any]:
    return {"schema": RESULT, "command": command, "status": status_value, **extra}


def normalize(root: str) -> None:
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        if os.path.islink(current): fail("seed contains a symlink")
        os.chmod(current, 0o700)
        for name in dirs + files:
            path = os.path.join(current, name)
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode) or (not stat.S_ISDIR(st.st_mode) and (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1)):
                fail("seed contains an unsafe inode")
            if stat.S_ISREG(st.st_mode): os.chmod(path, 0o700 if st.st_mode & 0o100 else 0o600)


def durable_tree(root: str) -> None:
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    for current, dirs, files in os.walk(root, topdown=False, followlinks=False):
        for name in files:
            fd = os.open(os.path.join(current, name), flags)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        fd = os.open(current, flags | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def rename_noreplace(source: str, destination: str) -> None:
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError:
        fail("atomic no-replace activation is unavailable")
    renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1) == 0:
        return
    error = ctypes.get_errno()
    if error in (errno.EEXIST, errno.ENOTEMPTY):
        fail("seed path appeared during atomic activation")
    fail(f"atomic no-replace seed activation failed: {os.strerror(error)}")


def acquire(value: dict[str, Any]) -> None:
    seed = value["seed_path"]
    if os.path.lexists(seed): fail("seed path already exists")
    stage = seed + ".acquire-stage"
    if os.path.lexists(stage): fail("seed acquisition stage already exists")
    try:
        git(("clone", "--no-local", "--no-hardlinks", "--no-checkout", "--origin", value["remote_name"], value["remote_url"], stage), repo=None,
            value=value, timeout=120)
        git(("checkout", "-q", "-B", "master", value["candidate_commit"]), repo=stage,
            value=value)
        git(("config", "branch.master.remote", value["remote_name"]), repo=stage, value=value)
        git(("config", "branch.master.merge", "refs/heads/master"), repo=stage, value=value)
        normalize(stage)
        durable_tree(stage)
        rename_noreplace(stage, seed)
        parent_fd = os.open(os.path.dirname(seed), os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except BaseException:
        if os.path.isdir(stage) and not os.path.islink(stage): shutil.rmtree(stage)
        raise


def verify_seed(value: dict[str, Any]) -> None:
    seed = value["seed_path"]
    physical(seed, "seed")
    st = os.lstat(seed)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        fail("seed root custody is invalid")
    head = git(("rev-parse", "--verify", "HEAD^{commit}"), repo=seed, value=value).decode().strip()
    remote_name = value["remote_name"]
    tracking = git(("rev-parse", "--verify", f"refs/remotes/{remote_name}/master^{{commit}}"), repo=seed, value=value).decode().strip()
    if head != value["candidate_commit"] or tracking != head or remote_head(value) != head:
        fail("remote, seed HEAD, tracking ref, and candidate are not identical")
    url = git(("config", "--local", "--get", f"remote.{remote_name}.url"), repo=seed,
              value=value).decode().strip()
    branch_remote = git(("config", "--local", "--get", "branch.master.remote"), repo=seed,
                        value=value).decode().strip()
    branch_merge = git(("config", "--local", "--get", "branch.master.merge"), repo=seed,
                       value=value).decode().strip()
    if (url, branch_remote, branch_merge) != (
        value["remote_url"], remote_name, "refs/heads/master"
    ):
        fail("seed Git authority configuration drifted")
    if git(("status", "--porcelain=v1", "--untracked-files=all"), repo=seed, value=value):
        fail("seed is not clean")
    listing = git(("ls-tree", "-r", head), repo=seed, value=value)
    if any(line.split(maxsplit=2)[1:2] == [b"commit"] for line in listing.splitlines()):
        fail("seed candidate contains gitlinks")
    for current, dirs, files in os.walk(seed, topdown=True, followlinks=False):
        for path in [Path(current), *(Path(current) / name for name in dirs + files)]:
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode) or st.st_uid != os.geteuid():
                fail("seed tree custody drifted")
            if stat.S_ISDIR(st.st_mode) and stat.S_IMODE(st.st_mode) != 0o700:
                fail("seed directory mode drifted")
            if stat.S_ISREG(st.st_mode) and (st.st_nlink != 1 or stat.S_IMODE(st.st_mode) not in (0o600, 0o700)):
                fail("seed file custody drifted")


def main(argv: Sequence[str] | None = None) -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "publish", "acquire-seed", "verify"))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--confirm")
    args = parser.parse_args(argv)
    try:
        value = load(args.manifest)
        remote, plan = inspect(value)
        confirmation = f"PUBLISH:{value['candidate_commit']}:{plan}"
        if args.command == "plan":
            require_ci_skip_contract(value)
            packet = result("plan", "ready", candidate_commit=value["candidate_commit"], remote_master=remote,
                            plan_digest=plan, confirmation=confirmation,
                            ci_policy="skip", ci_mechanism=value["ci_policy"])
        elif args.command == "publish":
            if args.confirm != confirmation: fail("publish confirmation is not exact")
            require_ci_skip_contract(value)
            if remote != value["candidate_commit"]:
                push = ["push", "--porcelain"]
                if value["ci_policy"] == "push_option":
                    push.append("--push-option=ci.skip")
                push += [value["remote_url"], f"{value['candidate_commit']}:refs/heads/master"]
                git(tuple(push), repo=value["source_repository"], value=value, timeout=120)
            if remote_head(value) != value["candidate_commit"]:
                fail("published authority master did not converge")
            packet = result(
                "publish", "published_authoritative_candidate",
                candidate_commit=value["candidate_commit"],
                ci_policy="skip", ci_mechanism=value["ci_policy"],
            )
        elif args.command == "acquire-seed":
            if remote != value["candidate_commit"]:
                fail("candidate is not authoritative master")
            acquire(value)
            verify_seed(value)
            packet = result("acquire-seed", "acquired_independent_seed", candidate_commit=value["candidate_commit"], seed_path=value["seed_path"])
        else:
            verify_seed(value)
            packet = result("verify", "verified_publication_and_seed", candidate_commit=value["candidate_commit"], seed_path=value["seed_path"])
        sys.stdout.buffer.write(canonical(packet) + b"\n")
        return 0
    except Blocked as exc:
        sys.stderr.write(f"trusted publication/seed blocked: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
