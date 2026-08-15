#!/usr/bin/env python3
"""S614 fixed-path secure configuration installer; source is not a grant."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
S611_CONTRACT_PATH = ROOT / "docs/design/voice-scene/s611_story_executor_secure_runtime_configuration_contract.json"
S611_CONTRACT_SHA256 = "a6a74db9de4cf8050a4126a9519e5e7a0ae48093ad9cf32ada5dcb1962c1d06f"
S613_REVIEW_PATH = ROOT / "docs/design/voice-scene/s613_story_executor_installed_key_composition_review.json"
S613_REVIEW_SHA256 = "6eff56f79c41f4053c26c8cb6a6210f02c302c692af2de36b24c7b4b685974f7"
FIXED_SECURE_ROOT = Path("/home/pallasting/.agent-bridge-secure")
FIXED_RUNTIME_DIRECTORY = FIXED_SECURE_ROOT / "story-render"
FIXED_KEY_BUNDLE = FIXED_RUNTIME_DIRECTORY / "authority-keys.v1.json"
FIXED_NONCE_STORE = FIXED_RUNTIME_DIRECTORY / "story-render-nonces.sqlite3"
FIXED_KEY_ID = "story-render-owner-v1"
MOUNTINFO_PATH = Path("/proc/self/mountinfo")
APPROVED_FILESYSTEMS = {"ext4", "xfs", "btrfs"}
TEMPORARY_KEY_NAME = ".authority-keys.v1.json.installing"
MAX_BUNDLE_BYTES = 65536


class InstallationRecoveryRequired(RuntimeError):
    """Publication occurred; automated deletion is no longer permitted."""


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_pinned_json(path: Path, expected_sha256: str) -> dict[str, Any]:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("secure configuration policy source drift")
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required:{path}")
    return value


def _validate_fixed_policy() -> None:
    contract = _read_pinned_json(S611_CONTRACT_PATH, S611_CONTRACT_SHA256)
    contract_bound = {key: contract[key] for key in (
        "evidence", "custody", "installation", "blockers",
        "installation_authorized", "execution_authorized", "runtime_effects")}
    if (contract.get("schema")
            != "agent_bridge.story_executor_secure_runtime_configuration_contract.v1"
            or contract.get("installation_authorized") is not False
            or contract.get("execution_authorized") is not False
            or any(contract.get("runtime_effects", {}).values())
            or _digest(contract_bound) != contract.get("contract_sha256")):
        raise ValueError("S611 installation policy invalid")
    review = _read_pinned_json(S613_REVIEW_PATH, S613_REVIEW_SHA256)
    review_bound = {key: review[key] for key in (
        "evidence", "boundaries", "blockers", "implementation_present",
        "installation_authorized", "execution_authorized", "runtime_effects")}
    if (review.get("schema")
            != "agent_bridge.story_executor_installed_key_composition_review.v1"
            or review.get("next_gate")
            != "owner_authorized_story_executor_secure_configuration_installation"
            or review.get("installation_authorized") is not False
            or review.get("execution_authorized") is not False
            or any(review.get("runtime_effects", {}).values())
            or _digest(review_bound) != review.get("review_sha256")):
        raise ValueError("S613 installation gate invalid")
    custody = contract["custody"]
    if (Path(custody["secure_root"]["path"]) != FIXED_SECURE_ROOT
            or Path(custody["runtime_directory"]["path"])
            != FIXED_RUNTIME_DIRECTORY
            or Path(custody["key_bundle"]["path"]) != FIXED_KEY_BUNDLE
            or Path(custody["nonce_store"]["path"]) != FIXED_NONCE_STORE
            or contract["installation"].get("authorized_now") is not False):
        raise ValueError("fixed installation target invalid")


def _unescape_mount(value: str) -> str:
    for encoded, plain in (("\\040", " "), ("\\011", "\t"),
                           ("\\012", "\n"), ("\\134", "\\")):
        value = value.replace(encoded, plain)
    return value


def _filesystem_type(path: Path, mountinfo_path: Path) -> str:
    target = str(path.resolve(strict=True))
    matches: list[tuple[int, str]] = []
    for line in mountinfo_path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        separator = fields.index("-")
        mountpoint = _unescape_mount(fields[4]).rstrip("/") or "/"
        if target == mountpoint or target.startswith(mountpoint.rstrip("/") + "/"):
            matches.append((len(mountpoint), fields[separator + 1]))
    if not matches:
        raise ValueError("secure root filesystem mount not found")
    return max(matches)[1]


def _open_private_directory(path: Path) -> int:
    if (not path.is_absolute() or path.resolve(strict=True) != path
            or path.name in {"", ".", ".."}):
        raise ValueError("secure root canonical path invalid")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    current = os.open("/", flags)
    try:
        for component in path.parts[1:]:
            following = os.open(
                component, flags | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = following
        metadata = os.fstat(current)
        if (not stat.S_ISDIR(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o700
                or metadata.st_uid != os.getuid()
                or metadata.st_gid != os.getgid()):
            raise ValueError("secure root must be current-user 0700 directory")
        return current
    except Exception:
        os.close(current)
        raise


def _assert_absent(name: str, directory_fd: int, message: str) -> None:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise ValueError(message)


def _write_all(descriptor: int, payload: bytearray) -> None:
    view = memoryview(payload)
    try:
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                raise OSError("authority key write made no progress")
            written += count
    finally:
        view.release()


def _validate_key_descriptor(descriptor: int) -> None:
    metadata = os.fstat(descriptor)
    if (not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.getuid()
            or metadata.st_gid != os.getgid()
            or metadata.st_nlink != 1):
        raise ValueError("authority key identity invalid")


def _read_descriptor(descriptor: int) -> bytes:
    chunks = bytearray()
    while True:
        chunk = os.read(descriptor, 8192)
        if not chunk:
            break
        chunks.extend(chunk)
        if len(chunks) > MAX_BUNDLE_BYTES:
            raise ValueError("authority key bundle too large")
    return bytes(chunks)


def _clear(buffer: bytearray | None) -> None:
    if buffer is not None:
        for index in range(len(buffer)):
            buffer[index] = 0


def _install_secure_configuration(
    *, secure_root: Path, runtime_directory: Path, key_id: str,
    key_factory: Callable[[int], bytes], mountinfo_path: Path,
    step_hook: Callable[[str, Path], None],
) -> dict[str, Any]:
    """Private fault-injection seam; public installation fixes every target."""
    if (runtime_directory.parent != secure_root
            or runtime_directory.name != "story-render"
            or not isinstance(key_id, str) or not key_id):
        raise ValueError("secure installation target invalid")
    if _filesystem_type(secure_root, mountinfo_path) not in APPROVED_FILESYSTEMS:
        raise ValueError("secure root filesystem is not approved POSIX storage")
    root_fd = _open_private_directory(secure_root)
    runtime_fd = None
    key_fd = None
    read_fd = None
    runtime_created = False
    temporary_created = False
    published = False
    key_material = None
    payload = None
    bundle = None
    previous_umask = os.umask(0o077)
    try:
        _assert_absent(
            runtime_directory.name, root_fd,
            "runtime directory already exists; adoption review required")
        os.mkdir(runtime_directory.name, mode=0o700, dir_fd=root_fd)
        runtime_created = True
        runtime_fd = os.open(
            runtime_directory.name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=root_fd,
        )
        runtime_metadata = os.fstat(runtime_fd)
        if (stat.S_IMODE(runtime_metadata.st_mode) != 0o700
                or runtime_metadata.st_uid != os.getuid()
                or runtime_metadata.st_gid != os.getgid()):
            raise ValueError("runtime directory identity invalid")
        os.fsync(root_fd)
        step_hook("runtime_directory_fsynced", runtime_directory)
        raw_key = key_factory(32)
        if (not isinstance(raw_key, (bytes, bytearray))
                or len(raw_key) != 32 or not any(raw_key)):
            raise ValueError("authority key material invalid")
        key_material = bytearray(raw_key)
        bundle = {
            "schema": "agent_bridge.story_render_authority_keys.v1",
            "active_key_id": key_id,
            "keys": [{"key_id": key_id, "status": "active",
                      "key_hex": key_material.hex()}],
        }
        payload = bytearray(json.dumps(
            bundle, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode("utf-8"))
        key_fd = os.open(
            TEMPORARY_KEY_NAME,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=runtime_fd,
        )
        temporary_created = True
        _validate_key_descriptor(key_fd)
        _write_all(key_fd, payload)
        os.fsync(key_fd)
        os.close(key_fd)
        key_fd = None
        step_hook("key_file_fsynced", runtime_directory)
        os.link(
            TEMPORARY_KEY_NAME, FIXED_KEY_BUNDLE.name,
            src_dir_fd=runtime_fd, dst_dir_fd=runtime_fd,
            follow_symlinks=False,
        )
        published = True
        os.unlink(TEMPORARY_KEY_NAME, dir_fd=runtime_fd)
        temporary_created = False
        os.fsync(runtime_fd)
        step_hook("key_published", runtime_directory)
        read_fd = os.open(
            FIXED_KEY_BUNDLE.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=runtime_fd,
        )
        _validate_key_descriptor(read_fd)
        if json.loads(_read_descriptor(read_fd).decode("utf-8")) != bundle:
            raise InstallationRecoveryRequired(
                "published authority key verification failed")
        _assert_absent(
            FIXED_NONCE_STORE.name, runtime_fd,
            "nonce store unexpectedly exists after installation")
        return {
            "schema": "agent_bridge.story_render_secure_configuration_installation.v1",
            "status": "story_render_secure_configuration_installed",
            "decision": "configuration_installed_executor_invocation_blocked",
            "installation": {
                "secure_root": str(secure_root),
                "runtime_directory": str(runtime_directory),
                "key_bundle": str(runtime_directory / FIXED_KEY_BUNDLE.name),
                "active_key_id": key_id,
                "runtime_directory_mode": "0700",
                "key_bundle_mode": "0600",
                "publication": "same_directory_link_no_replace",
                "file_and_directory_fsync": True,
                "nonce_store_absent": True,
                "key_material_disclosed": False,
            },
            "execution_authorized": False,
            "runtime_effects": {
                "created_runtime_directory": True,
                "created_key_bundle": True,
                "generated_key": True,
                "created_nonce_store": False,
                "called_executor": False,
                "loaded_model": False,
                "rendered_audio": False,
                "wrote_memory": False,
            },
        }
    except Exception as error:
        if key_fd is not None:
            os.close(key_fd)
            key_fd = None
        if temporary_created and runtime_fd is not None:
            try:
                os.unlink(TEMPORARY_KEY_NAME, dir_fd=runtime_fd)
                os.fsync(runtime_fd)
            except FileNotFoundError:
                pass
        if published:
            if isinstance(error, InstallationRecoveryRequired):
                raise
            raise InstallationRecoveryRequired(
                "authority key was published; explicit recovery review required") from error
        if runtime_fd is not None:
            os.close(runtime_fd)
            runtime_fd = None
        if runtime_created:
            try:
                os.rmdir(runtime_directory.name, dir_fd=root_fd)
                os.fsync(root_fd)
            except OSError:
                pass
        raise
    finally:
        os.umask(previous_umask)
        if read_fd is not None:
            os.close(read_fd)
        if key_fd is not None:
            os.close(key_fd)
        if runtime_fd is not None:
            os.close(runtime_fd)
        os.close(root_fd)
        _clear(payload)
        _clear(key_material)
        if bundle is not None:
            bundle.clear()


def install_story_render_secure_configuration() -> dict[str, Any]:
    """Effectful fixed-path entrypoint; invoking it requires fresh owner authority."""
    _validate_fixed_policy()
    return _install_secure_configuration(
        secure_root=FIXED_SECURE_ROOT,
        runtime_directory=FIXED_RUNTIME_DIRECTORY,
        key_id=FIXED_KEY_ID,
        key_factory=secrets.token_bytes,
        mountinfo_path=MOUNTINFO_PATH,
        step_hook=lambda _step, _runtime: None,
    )
