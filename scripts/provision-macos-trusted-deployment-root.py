#!/usr/bin/env python3
"""Plan, provision, and verify an isolated Darwin trusted deployment root.

Only ``provision`` writes. It requires the exact confirmation emitted by
``plan`` and activates a newly staged root through a separately hashed native
RENAME_EXCL helper. It never reads or changes production services or state.
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
import tempfile
from pathlib import Path
from typing import Any, NoReturn, Sequence


MANIFEST_SCHEMA = "agent_bridge.darwin_trusted_root_manifest.v0"
RECEIPT_SCHEMA = "agent_bridge.darwin_trusted_root_receipt.v0"
RESULT_SCHEMA = "agent_bridge.darwin_trusted_root_result.v0"
BACKEND = "darwin-launchd-v0"
RECEIPT_NAME = "receipts/root-provisioning.json"
LAYOUT = (
    "bin", "build", "config", "data", "lib", "publisher", "receipts",
    "rollback", "share", "source",
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ROOT_NAME = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
PLAN_DOMAIN = b"agent-bridge/darwin-trusted-root/plan/v0\0"
TREE_DOMAIN = b"agent-bridge/darwin-trusted-root/tree/v0\0"


class ProvisionError(RuntimeError):
    pass


def fail(message: str) -> NoReturn:
    raise ProvisionError(message)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            fail("helper must be a singly linked regular file")
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            fail("helper changed while hashing")
    finally:
        os.close(fd)
    return digest.hexdigest()


def canonical_absent_root(raw: str) -> Path:
    if not raw.startswith("/") or os.path.normpath(raw) != raw or "\x00" in raw:
        fail("deployment root must be an absolute canonical path")
    root = Path(raw)
    if not SAFE_ROOT_NAME.fullmatch(root.name) or root.name in (".", ".."):
        fail("deployment-root leaf name is unsafe")
    parent = root.parent
    if not parent.is_dir() or parent.resolve() != parent:
        fail("deployment-root parent must be an existing physical directory")
    parent_st = parent.lstat()
    if parent_st.st_uid != os.geteuid() or stat.S_IMODE(parent_st.st_mode) != 0o700:
        fail("deployment-root parent must be owner-controlled mode 0700")
    if root.exists() or root.is_symlink():
        fail("deployment root must be absent before provisioning")
    return root


def require_helper(path: Path) -> str:
    if not path.is_absolute() or path.resolve() != path:
        fail("rename helper must be an absolute physical path")
    value = path.lstat()
    if value.st_uid != os.geteuid() or not stat.S_ISREG(value.st_mode):
        fail("rename helper must be an owner-controlled regular file")
    if stat.S_IMODE(value.st_mode) & 0o022 or not os.access(path, os.X_OK):
        fail("rename helper must be executable and not group/other writable")
    return sha256_file(path)


def build_manifest(root: Path, helper: Path, helper_sha256: str) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "backend": BACKEND,
        "deployment_root": str(root),
        "layout": list(LAYOUT),
        "rename_helper": {"path": str(helper), "sha256": helper_sha256},
        "activation": "renameatx_np_RENAME_EXCL",
        "production_state_imported": False,
        "launchd_changed": False,
    }


def build_plan(root: Path, helper: Path) -> dict[str, Any]:
    helper_sha256 = require_helper(helper)
    manifest = build_manifest(root, helper, helper_sha256)
    confirmation = sha256_bytes(PLAN_DOMAIN + canonical_json(manifest))
    return {
        "schema": RESULT_SCHEMA,
        "command": "plan",
        "read_only": True,
        "manifest": manifest,
        "confirmation": confirmation,
    }


def custody_digest(root: Path) -> tuple[str, list[dict[str, Any]]]:
    observed_top_level = sorted(path.name for path in root.iterdir())
    expected_top_level = sorted((*LAYOUT,))
    if observed_top_level != expected_top_level:
        fail("trusted root top-level custody layout drifted")
    rows: list[dict[str, Any]] = []
    for name in LAYOUT:
        path = root / name
        value = path.lstat()
        if not stat.S_ISDIR(value.st_mode) or stat.S_ISLNK(value.st_mode):
            fail("trusted root custody namespace is not a physical directory")
        if value.st_uid != os.geteuid() or stat.S_IMODE(value.st_mode) != 0o700:
            fail("trusted root custody namespace owner or mode drifted")
        rows.append({"path": name, "kind": "directory", "mode": "0700"})
    manifest_path = root / "config/root-manifest.json"
    manifest_value = manifest_path.lstat()
    if (
        not stat.S_ISREG(manifest_value.st_mode)
        or manifest_value.st_nlink != 1
        or stat.S_IMODE(manifest_value.st_mode) != 0o600
    ):
        fail("root manifest type, link count, or mode drifted")
    rows.append({
        "path": "config/root-manifest.json", "kind": "regular", "mode": "0600",
        "sha256": sha256_file(manifest_path), "size": manifest_value.st_size,
    })
    return sha256_bytes(TREE_DOMAIN + canonical_json(rows)), rows


def provision(root: Path, helper: Path, confirmation: str) -> dict[str, Any]:
    expected = build_plan(root, helper)
    if not HEX64.fullmatch(confirmation) or confirmation != expected["confirmation"]:
        fail("confirmation does not match the exact plan")
    parent = root.parent
    stage = Path(tempfile.mkdtemp(prefix=f".{root.name}.stage-", dir=parent))
    stage.chmod(0o700)
    activated = False
    try:
        for name in LAYOUT:
            (stage / name).mkdir(mode=0o700)
        manifest_path = stage / "config/root-manifest.json"
        manifest_path.write_bytes(canonical_json(expected["manifest"]) + b"\n")
        manifest_path.chmod(0o600)
        digest, entries = custody_digest(stage)
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "backend": BACKEND,
            "manifest_sha256": sha256_bytes(canonical_json(expected["manifest"])),
            "tree_sha256": digest,
            "entry_count": len(entries),
            "activation": "renameatx_np_RENAME_EXCL",
            "production_state_imported": False,
            "launchd_changed": False,
        }
        receipt_path = stage / RECEIPT_NAME
        receipt_path.write_bytes(canonical_json(receipt) + b"\n")
        receipt_path.chmod(0o600)
        completed = subprocess.run(
            [str(helper), str(stage), str(root)], capture_output=True, text=True,
            timeout=10, check=False,
        )
        if completed.returncode != 0:
            if completed.returncode == 73:
                fail("exclusive activation rejected an existing destination")
            fail("exclusive activation helper failed")
        activated = True
        return verify(root, helper)
    finally:
        if not activated and stage.exists():
            # Deliberately retain failed staging custody for inspection. The
            # caller owns this disposable parent and may remove it separately.
            pass


def parse_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        fail("receipt or manifest is unreadable")
    if not isinstance(value, dict):
        fail("receipt or manifest must be an object")
    return value


def verify(root: Path, helper: Path) -> dict[str, Any]:
    if not root.is_absolute() or root.resolve() != root or not root.is_dir() or root.is_symlink():
        fail("trusted root is not a physical directory")
    parent = root.parent
    parent_value = parent.lstat()
    if parent.resolve() != parent or parent_value.st_uid != os.geteuid() or stat.S_IMODE(parent_value.st_mode) != 0o700:
        fail("trusted-root parent custody drifted")
    value = root.lstat()
    if value.st_uid != os.geteuid() or stat.S_IMODE(value.st_mode) != 0o700:
        fail("trusted root owner or mode drifted")
    helper_sha256 = require_helper(helper)
    manifest = parse_object(root / "config/root-manifest.json")
    receipt_path = root / RECEIPT_NAME
    receipt_value = receipt_path.lstat()
    if not stat.S_ISREG(receipt_value.st_mode) or receipt_value.st_nlink != 1 or stat.S_IMODE(receipt_value.st_mode) != 0o600:
        fail("root receipt type, link count, or mode drifted")
    receipt = parse_object(receipt_path)
    expected_manifest = build_manifest(root, helper, helper_sha256)
    if manifest != expected_manifest:
        fail("root manifest drifted")
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("backend") != BACKEND:
        fail("root receipt schema or backend is wrong")
    if receipt.get("manifest_sha256") != sha256_bytes(canonical_json(manifest)):
        fail("root receipt manifest digest drifted")
    digest, entries = custody_digest(root)
    if receipt.get("tree_sha256") != digest or receipt.get("entry_count") != len(entries):
        fail("root receipt tree binding drifted")
    return {
        "schema": RESULT_SCHEMA,
        "command": "verify",
        "backend": BACKEND,
        "verdict": "PASS",
        "deployment_root": str(root),
        "root_device": value.st_dev,
        "root_inode": value.st_ino,
        "tree_sha256": digest,
        "production_state_imported": False,
        "launchd_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "provision", "verify"))
    parser.add_argument("--deploy-root", required=True)
    parser.add_argument("--rename-helper", type=Path, required=True)
    parser.add_argument("--confirm")
    args = parser.parse_args()
    try:
        if platform.system() != "Darwin":
            fail("Darwin trusted-root provisioner requires Darwin")
        root = canonical_absent_root(args.deploy_root) if args.command != "verify" else Path(args.deploy_root)
        if args.command == "plan":
            result = build_plan(root, args.rename_helper)
        elif args.command == "provision":
            if not args.confirm:
                fail("provision requires --confirm")
            result = provision(root, args.rename_helper, args.confirm)
        else:
            result = verify(root, args.rename_helper)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except ProvisionError as exc:
        print(json.dumps({"schema": RESULT_SCHEMA, "verdict": "FAIL_CLOSED", "error": str(exc)}, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
