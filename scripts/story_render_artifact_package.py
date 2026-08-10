#!/usr/bin/env python3
"""Build and verify the S638 source-only Story Worker control package."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "agent_bridge.story_render_artifact_package.v1"
MANIFEST_NAME = "story-render-package-manifest.json"
FILE_MODE = 0o400
EXEC_MODE = 0o500
DIR_MODE = 0o500
REQUIRED_INFERENCE_MODULES = (
    "numpy",
    "onnxruntime",
    "soundfile",
    "torch",
    "transformers",
)
ARTIFACTS = (
    "crates/bridge/src/story_render_guardian_protocol.rs",
    "crates/bridge/src/story_render_guardian.rs",
    "crates/bridge/src/story_render_guardian_supervision.rs",
    "crates/bridge/src/story_render_supervisor.rs",
    "scripts/story_render_one_shot_worker.py",
    "scripts/story_render_worker_protocol.py",
    "scripts/story_executor_installed_key_composition.py",
    "scripts/story_executor_secure_runtime_composition.py",
    "scripts/story_executor_posix_runtime_binding.py",
    "scripts/story_executor_runtime_verifiers.py",
    "scripts/story_bounded_render_executor.py",
    "scripts/story_voice_existing_onnx_trusted_runner.py",
    "docs/design/voice-scene/s602_story_fixture_mcp_preflight_receipt.json",
    "docs/design/voice-scene/s603_story_fixture_bounded_render_receipt.json",
    "docs/design/voice-scene/s604_story_bounded_render_execution_contract.json",
    "docs/design/voice-scene/s608_story_executor_authority_model_nonce_contract.json",
    "docs/design/voice-scene/s611_story_executor_secure_runtime_configuration_contract.json",
    "docs/design/voice-scene/s620_story_render_one_shot_worker_protocol_contract.json",
)


class PackageRejected(ValueError):
    """A fixed-detail package construction or verification rejection."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _safe_relative(name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise PackageRejected("artifact path rejected")
    return path


def _read_stable(path: Path) -> tuple[bytes, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise PackageRejected("artifact open rejected") from error
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise PackageRejected("artifact identity rejected")
        chunks = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(fd)
        identity = lambda row: (row.st_dev, row.st_ino, row.st_size, row.st_mtime_ns)
        if identity(before) != identity(after):
            raise PackageRejected("artifact changed during read")
        return b"".join(chunks), after
    finally:
        os.close(fd)


def _require_private_parent(path: Path, owner_uid: int) -> None:
    row = os.lstat(path)
    if not stat.S_ISDIR(row.st_mode) or row.st_uid != owner_uid:
        raise PackageRejected("package parent custody rejected")
    if stat.S_IMODE(row.st_mode) & 0o022:
        raise PackageRejected("package parent writable by non-owner")


def _python_probe(python: Path) -> dict[str, Any]:
    code = (
        "import importlib.util,json,sys;"
        "print(json.dumps({'version':sys.version.split()[0],"
        "'implementation':sys.implementation.name,'cache_tag':sys.implementation.cache_tag,"
        "'stdlib':__import__('sysconfig').get_path('stdlib'),"
        "'modules':{n:bool(importlib.util.find_spec(n)) for n in "
        + repr(REQUIRED_INFERENCE_MODULES)
        + "}},sort_keys=True))"
    )
    result = subprocess.run(
        [str(python), "-I", "-S", "-c", code], check=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}, timeout=15,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or value.get("implementation") != "cpython":
        raise PackageRejected("python runtime rejected")
    return value


def build_package(destination: Path, *, python: Path = Path("/usr/bin/python3")) -> dict[str, Any]:
    destination = destination.absolute()
    owner_uid = os.getuid()
    if destination.exists() or destination.is_symlink():
        raise PackageRejected("destination must not exist")
    _require_private_parent(destination.parent, owner_uid)
    resolved_python = python.resolve(strict=True)
    python_bytes, _ = _read_stable(resolved_python)
    probe = _python_probe(resolved_python)
    destination.mkdir(mode=0o700)
    try:
        rows = []
        for name in ARTIFACTS:
            relative = _safe_relative(name)
            source = ROOT / relative
            payload, _ = _read_stable(source)
            target = destination / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.write_bytes(payload)
            os.chmod(target, FILE_MODE)
            rows.append({"path": name, "sha256": _sha256(payload), "size": len(payload), "mode": "0400"})
        runtime = destination / "runtime/bin/python3"
        runtime.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        runtime.write_bytes(python_bytes)
        os.chmod(runtime, EXEC_MODE)
        rows.append({"path": "runtime/bin/python3", "sha256": _sha256(python_bytes), "size": len(python_bytes), "mode": "0500"})
        stdlib_source = Path(probe["stdlib"])
        if not stdlib_source.is_absolute() or not stdlib_source.is_dir():
            raise PackageRejected("python standard library rejected")
        stdlib_relative = Path("runtime/lib") / stdlib_source.name
        for source in sorted(stdlib_source.rglob("*")):
            relative_source = source.relative_to(stdlib_source)
            if "__pycache__" in relative_source.parts:
                continue
            stable_source = source.resolve(strict=True) if source.is_symlink() else source
            if not stable_source.is_file():
                continue
            payload, _ = _read_stable(stable_source)
            relative = stdlib_relative / relative_source
            target = destination / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.write_bytes(payload)
            os.chmod(target, FILE_MODE)
            rows.append({"path": relative.as_posix(), "sha256": _sha256(payload), "size": len(payload), "mode": "0400"})
        rows.sort(key=lambda row: row["path"])
        manifest: dict[str, Any] = {
            "schema": SCHEMA,
            "package_mode": "offline_control_plane_default_off",
            "artifacts": rows,
            "python": {
                "implementation": probe["implementation"],
                "version": probe["version"],
                "cache_tag": probe["cache_tag"],
                "isolated_flags": ["-I", "-S"],
                "inference_modules": probe["modules"],
                "inference_dependency_closure": "blocked_missing_offline_wheelhouse",
            },
            "authority": {
                "installed_key_read": False, "model_load": False,
                "render_output": False, "mcp_registration": False,
                "runtime_enablement": False, "deployment": False,
            },
        }
        manifest["package_id"] = _sha256(_canonical(manifest))
        manifest_path = destination / MANIFEST_NAME
        manifest_path.write_bytes(_canonical(manifest) + b"\n")
        os.chmod(manifest_path, FILE_MODE)
        for directory in sorted((row for row in destination.rglob("*") if row.is_dir()), reverse=True):
            os.chmod(directory, DIR_MODE)
        os.chmod(destination, DIR_MODE)
        verify_package(destination, expected_package_id=manifest["package_id"])
        return manifest
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def verify_package(package: Path, *, expected_package_id: str | None = None) -> dict[str, Any]:
    package = package.absolute()
    owner_uid = os.getuid()
    _require_private_parent(package.parent, owner_uid)
    root = os.lstat(package)
    if not stat.S_ISDIR(root.st_mode) or root.st_uid != owner_uid or stat.S_IMODE(root.st_mode) != DIR_MODE:
        raise PackageRejected("package root custody rejected")
    manifest_bytes, manifest_stat = _read_stable(package / MANIFEST_NAME)
    if manifest_stat.st_uid != owner_uid or stat.S_IMODE(manifest_stat.st_mode) != FILE_MODE:
        raise PackageRejected("manifest custody rejected")
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackageRejected("manifest rejected") from error
    package_id = manifest.pop("package_id", None)
    if package_id != _sha256(_canonical(manifest)) or (expected_package_id and package_id != expected_package_id):
        raise PackageRejected("package identity rejected")
    manifest["package_id"] = package_id
    expected = {MANIFEST_NAME}
    for row in manifest.get("artifacts", []):
        relative = _safe_relative(row["path"])
        expected.add(relative.as_posix())
        payload, info = _read_stable(package / relative)
        if (info.st_uid != owner_uid or stat.S_IMODE(info.st_mode) != int(row["mode"], 8)
                or len(payload) != row["size"] or _sha256(payload) != row["sha256"]):
            raise PackageRejected("artifact manifest mismatch")
    actual = {path.relative_to(package).as_posix() for path in package.rglob("*") if path.is_file()}
    if actual != expected:
        raise PackageRejected("package contains unmanifested files")
    for directory in (package, *(path for path in package.rglob("*") if path.is_dir())):
        info = os.lstat(directory)
        if info.st_uid != owner_uid or stat.S_IMODE(info.st_mode) != DIR_MODE:
            raise PackageRejected("package directory custody rejected")
    return manifest


def run_fail_closed_worker(package: Path, request: bytes) -> subprocess.CompletedProcess[bytes]:
    manifest = verify_package(package)
    by_path = {row["path"]: row for row in manifest["artifacts"]}
    descriptors = []
    try:
        for name in ("runtime/bin/python3", "scripts/story_render_one_shot_worker.py"):
            path = package / name
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(path, flags)
            info = os.fstat(fd)
            if info.st_nlink != 1 or _sha256(os.pread(fd, info.st_size, 0)) != by_path[name]["sha256"]:
                raise PackageRejected("launch descriptor identity rejected")
            os.set_inheritable(fd, True)
            descriptors.append(fd)
        python_fd, worker_fd = descriptors
        return subprocess.run(
            [f"/proc/self/fd/{python_fd}", "-I", "-S", f"/proc/self/fd/{worker_fd}"],
            executable=f"/proc/self/fd/{python_fd}", pass_fds=tuple(descriptors),
            input=request, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=package,
            env={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHOME": str(package / "runtime")},
            timeout=30,
        )
    finally:
        for fd in descriptors:
            os.close(fd)


if __name__ == "__main__":
    raise SystemExit("S638 is a source/isolated-test library, not a deployment CLI")
