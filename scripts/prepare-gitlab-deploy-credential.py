#!/usr/bin/python3
"""Prepare a local, not-yet-enrolled GitLab deploy credential pack."""

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

MANIFEST_SCHEMA = "agent_bridge.gitlab_deploy_credential_manifest.v1"
RECEIPT_SCHEMA = "agent_bridge.gitlab_deploy_credential_receipt.v1"
RESULT_SCHEMA = "agent_bridge.gitlab_deploy_credential_result.v1"
DOMAIN = b"agent-bridge/gitlab-deploy-credential/v1\0"
SAFE_PATH = re.compile(r"^/[A-Za-z0-9._/-]+$")
SAFE_PROJECT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SAFE_COMMENT = re.compile(r"^[A-Za-z0-9_.:@/-]{1,128}$")
OFFICIAL_SOURCE = "https://docs.gitlab.com/user/gitlab_com/#ssh-host-keys-fingerprints"
OFFICIAL_VERIFIED_DATE = "2026-08-29"
KNOWN_HOSTS = (
    "gitlab.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAfuCHKVTjquxvt6CM6tdG4SLp1Btn/nOeHHE5UOzRdf\n"
    "gitlab.com ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCsj2bNKTBSpIYDEGk9KxsGh3mySTRgMtXL583qmBpzeQ+jqCMRgBqB98u3z++J1sKlXHWfM9dyhSevkMwSbhoR8XIq/U0tCNyokEi/ueaBMCvbcTHhO7FcwzY92WK4Yt0aGROY5qX2UKSeOvuP4D6TPqKF1onrSzH9bx9XUf2lEdWT/ia1NEKjunUqu1xOB/StKDHMoX4/OKyIzuS0q/T1zOATthvasJFoPrAjkohTyaDUz2LN5JoH839hViyEG82yB+MjcFV5MU3N1l1QL3cVUCh93xSaua1N85qivl+siMkPGbO5xR/En4iEY6K2XPASUEMaieWVNTRCtJ4S8H+9\n"
    "gitlab.com ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBFSMqzJeV9rUzU4kWitGjeR4PWSa29SPqJ1fVkhtj3Hw9xjLVXVYrU9QlYWrOLXBpQ6KWjbjTDTdDkoohFzgbEY=\n"
)
EXPECTED_HOST_FINGERPRINTS = {
    "SHA256:HbW3g8zUjNSksFbqTiUWPWg2Bq1x8xdGUrliXFzSnUw",
    "SHA256:eUXGGm1YGsMAS7vkcx6JOJdOGHPem5gQp4taiCfCLB8",
    "SHA256:ROQFvPThGrW4RuWLoL9tq9I9zJ42fK4XywyRtbOz/EQ",
}


class Blocked(RuntimeError):
    pass


def fail(message: str) -> NoReturn:
    raise Blocked(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def physical(path: Any, label: str, *, final_may_be_absent: bool = False) -> str:
    if not isinstance(path, str) or not SAFE_PATH.fullmatch(path) or os.path.normpath(path) != path:
        fail(f"{label} must be a canonical shell-safe absolute path")
    current = "/"
    parts = path.split("/")[1:]
    for index, part in enumerate(parts):
        current = os.path.join(current, part)
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            if final_may_be_absent and index == len(parts) - 1:
                break
            fail(f"{label} does not exist")
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


def file_fact(path: str, label: str, mode: int = 0o600) -> dict[str, Any]:
    physical(path, label)
    trusted_ancestors(path, label)
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != mode:
        fail(f"{label} custody is invalid")
    with open(path, "rb") as handle:
        raw = handle.read(1024 * 1024 + 1)
    if not raw or len(raw) > 1024 * 1024:
        fail(f"{label} content is invalid")
    return {"mode": mode, "sha256": sha(raw), "size": len(raw)}


def load_manifest(path: str) -> tuple[dict[str, Any], str]:
    fact = file_fact(path, "credential manifest")
    try:
        raw = Path(path).read_bytes()
        def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in items:
                if key in result: fail(f"manifest contains duplicate key {key}")
                result[key] = value
            return result
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"manifest is not strict JSON: {exc}")
    if not isinstance(value, dict) or set(value) != {"schema", "target_directory", "project_path", "key_comment"}:
        fail("manifest keys are not exact")
    if value["schema"] != MANIFEST_SCHEMA:
        fail("manifest schema is invalid")
    if not isinstance(value["project_path"], str) or not SAFE_PROJECT.fullmatch(value["project_path"]):
        fail("project path is invalid")
    if not isinstance(value["key_comment"], str) or not SAFE_COMMENT.fullmatch(value["key_comment"]):
        fail("key comment is invalid")
    target = physical(value["target_directory"], "credential target", final_may_be_absent=True)
    parent = os.path.dirname(target)
    physical(parent, "credential parent")
    trusted_ancestors(parent, "credential parent")
    st = os.lstat(parent)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        fail("credential parent must be an owned physical mode-0700 directory")
    return value, fact["sha256"]


def run_ssh_keygen(args: Sequence[str]) -> bytes:
    try:
        result = subprocess.run(["/usr/bin/ssh-keygen", *args], env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        fail("bounded ssh-keygen operation failed")
    if result.returncode:
        fail("ssh-keygen rejected the credential material")
    return result.stdout


def host_fingerprints(path: str) -> set[str]:
    raw = run_ssh_keygen(("-E", "sha256", "-lf", path))
    try:
        values = {line.split()[1] for line in raw.decode("ascii").splitlines()}
    except (UnicodeDecodeError, IndexError):
        fail("host fingerprint output is malformed")
    if values != EXPECTED_HOST_FINGERPRINTS:
        fail("GitLab host fingerprints do not match the official anchor")
    return values


def write_file(path: str, raw: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fchmod(fd, 0o600)
        os.fsync(fd)
    finally:
        os.close(fd)


def fsync_directory(path: str) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try: os.fsync(fd)
    finally: os.close(fd)


def rename_noreplace(source: str, target: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        fail("atomic no-replace activation is unavailable")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(source), -100, os.fsencode(target), 1) != 0:
        observed = ctypes.get_errno()
        if observed == errno.EEXIST: fail("credential target appeared before activation")
        fail(f"atomic no-replace activation failed with errno {observed}")


def plan_digest(manifest: dict[str, Any], manifest_sha: str) -> str:
    return sha(DOMAIN + canonical({"manifest": manifest, "manifest_sha256": manifest_sha,
                                  "official_source": OFFICIAL_SOURCE, "official_verified_date": OFFICIAL_VERIFIED_DATE,
                                  "host_fingerprints": sorted(EXPECTED_HOST_FINGERPRINTS)}))


def generate(manifest: dict[str, Any], manifest_sha: str, confirmation: str | None) -> dict[str, Any]:
    target = manifest["target_directory"]
    plan = plan_digest(manifest, manifest_sha)
    if confirmation != f"GENERATE:{plan}": fail("credential generation confirmation is not exact")
    if os.path.lexists(target): fail("credential target already exists")
    stage = target + ".credential-stage"
    if os.path.lexists(stage): fail("credential stage already exists")
    os.mkdir(stage, 0o700)
    active = True
    try:
        private_key = os.path.join(stage, "gitlab_deploy_key")
        run_ssh_keygen(("-q", "-t", "ed25519", "-N", "", "-C", manifest["key_comment"], "-f", private_key))
        os.chmod(private_key, 0o600)
        os.chmod(private_key + ".pub", 0o600)
        known = os.path.join(stage, "known_hosts")
        write_file(known, KNOWN_HOSTS.encode("ascii"))
        fingerprints = host_fingerprints(known)
        public = Path(private_key + ".pub").read_text("ascii").strip()
        fingerprint_line = run_ssh_keygen(("-E", "sha256", "-lf", private_key + ".pub")).decode("ascii").strip()
        key_fingerprint = fingerprint_line.split()[1]
        enrollment = {"schema": "agent_bridge.gitlab_deploy_key_enrollment.v1", "enrollment_status": "not_enrolled",
                      "project_path": manifest["project_path"], "required_access": "write_repository",
                      "public_key": public, "public_key_fingerprint": key_fingerprint}
        write_file(os.path.join(stage, "enrollment.json"), canonical(enrollment) + b"\n")
        facts = {name: file_fact(os.path.join(stage, name), name) for name in
                 ("gitlab_deploy_key", "gitlab_deploy_key.pub", "known_hosts", "enrollment.json")}
        receipt = {"schema": RECEIPT_SCHEMA, "authority_state": "local_key_not_enrolled",
                   "target_directory": target, "manifest_sha256": manifest_sha, "plan_digest": plan,
                   "project_path": manifest["project_path"], "public_key_fingerprint": key_fingerprint,
                   "official_host_key_source": OFFICIAL_SOURCE, "official_host_key_verified_date": OFFICIAL_VERIFIED_DATE,
                   "host_fingerprints": sorted(fingerprints), "files": facts}
        receipt["receipt_digest"] = sha(DOMAIN + canonical(receipt))
        write_file(os.path.join(stage, "receipt.json"), canonical(receipt) + b"\n")
        fsync_directory(stage)
        fsync_directory(os.path.dirname(target))
        rename_noreplace(stage, target)
        active = False
        fsync_directory(os.path.dirname(target))
        return receipt
    except BaseException:
        if active and os.path.isdir(stage) and not os.path.islink(stage): shutil.rmtree(stage)
        raise


def verify(manifest: dict[str, Any], manifest_sha: str) -> dict[str, Any]:
    target = physical(manifest["target_directory"], "credential target")
    st = os.lstat(target)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        fail("credential target custody is invalid")
    receipt_path = os.path.join(target, "receipt.json")
    file_fact(receipt_path, "credential receipt")
    try: receipt = json.loads(Path(receipt_path).read_text("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc: fail(f"credential receipt is invalid: {exc}")
    expected_keys = {"schema", "authority_state", "target_directory", "manifest_sha256", "plan_digest", "project_path",
                     "public_key_fingerprint", "official_host_key_source", "official_host_key_verified_date",
                     "host_fingerprints", "files", "receipt_digest"}
    if not isinstance(receipt, dict) or set(receipt) != expected_keys: fail("credential receipt keys are not exact")
    body = dict(receipt); observed = body.pop("receipt_digest", None)
    if observed != sha(DOMAIN + canonical(body)): fail("credential receipt digest mismatch")
    if receipt["schema"] != RECEIPT_SCHEMA or receipt["authority_state"] != "local_key_not_enrolled": fail("credential authority state is invalid")
    if (receipt["target_directory"], receipt["manifest_sha256"], receipt["plan_digest"], receipt["project_path"]) != (
        target, manifest_sha, plan_digest(manifest, manifest_sha), manifest["project_path"]): fail("credential manifest binding drifted")
    expected_files = {"gitlab_deploy_key", "gitlab_deploy_key.pub", "known_hosts", "enrollment.json"}
    if not isinstance(receipt["files"], dict) or set(receipt["files"]) != expected_files: fail("credential file set is not exact")
    for name in expected_files:
        if file_fact(os.path.join(target, name), name) != receipt["files"][name]: fail(f"credential file {name} drifted")
    if host_fingerprints(os.path.join(target, "known_hosts")) != set(receipt["host_fingerprints"]): fail("host-key receipt drifted")
    derived = run_ssh_keygen(("-y", "-f", os.path.join(target, "gitlab_deploy_key"))).decode("ascii").strip().split()
    public = Path(target, "gitlab_deploy_key.pub").read_text("ascii").strip().split()
    if derived[:2] != public[:2]: fail("private and public deploy keys do not match")
    fingerprint = run_ssh_keygen(("-E", "sha256", "-lf", os.path.join(target, "gitlab_deploy_key.pub"))).decode("ascii").split()[1]
    if fingerprint != receipt["public_key_fingerprint"]: fail("deploy-key fingerprint drifted")
    return receipt


def packet(command: str, status: str, **extra: Any) -> dict[str, Any]:
    return {"schema": RESULT_SCHEMA, "command": command, "status": status, **extra}


def main(argv: Sequence[str] | None = None) -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "generate", "verify"))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--confirm")
    args = parser.parse_args(argv)
    try:
        manifest, manifest_sha = load_manifest(args.manifest)
        plan = plan_digest(manifest, manifest_sha)
        if args.command == "plan":
            if os.path.lexists(manifest["target_directory"]): fail("credential target already exists")
            value = packet("plan", "ready", plan_digest=plan, confirmation=f"GENERATE:{plan}",
                           authority_state="will_generate_local_key_not_enrolled")
        elif args.command == "generate":
            receipt = generate(manifest, manifest_sha, args.confirm)
            value = packet("generate", "generated_local_key_not_enrolled",
                           public_key_fingerprint=receipt["public_key_fingerprint"], receipt_digest=receipt["receipt_digest"])
        else:
            receipt = verify(manifest, manifest_sha)
            value = packet("verify", "verified_local_key_not_enrolled",
                           public_key_fingerprint=receipt["public_key_fingerprint"], receipt_digest=receipt["receipt_digest"])
        sys.stdout.buffer.write(canonical(value) + b"\n")
        return 0
    except Blocked as exc:
        sys.stderr.write(f"GitLab deploy credential blocked: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
