#!/usr/bin/env python3
"""S612 fixed POSIX nonce binding and fd-based authority-key loader."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
S611_CONTRACT_PATH = ROOT / "docs/design/voice-scene/s611_story_executor_secure_runtime_configuration_contract.json"
EXPECTED_NONCE_PATH = Path(
    "/home/pallasting/.agent-bridge-secure/story-render/story-render-nonces.sqlite3"
)
EXPECTED_KEY_PATH = Path(
    "/home/pallasting/.agent-bridge-secure/story-render/authority-keys.v1.json"
)
MAX_KEY_BUNDLE_BYTES = 65536


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_contract() -> dict[str, Any]:
    with S611_CONTRACT_PATH.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("S611 contract object required")
    bound = {key: value[key] for key in (
        "evidence", "custody", "installation", "blockers",
        "installation_authorized", "execution_authorized", "runtime_effects")}
    if (value.get("schema")
            != "agent_bridge.story_executor_secure_runtime_configuration_contract.v1"
            or value.get("installation_authorized") is not False
            or value.get("execution_authorized") is not False
            or any(value.get("runtime_effects", {}).values())
            or _digest(bound) != value.get("contract_sha256")):
        raise ValueError("S611 contract invalid")
    return value


def secure_nonce_store_path() -> Path:
    contract = _read_contract()
    path = Path(contract["custody"]["nonce_store"]["path"])
    if (path != EXPECTED_NONCE_PATH
            or contract["custody"]["nonce_store"]["installed_now"] is not False):
        raise ValueError("S611 nonce binding invalid")
    return path


def secure_key_bundle_path() -> Path:
    contract = _read_contract()
    path = Path(contract["custody"]["key_bundle"]["path"])
    if (path != EXPECTED_KEY_PATH
            or contract["custody"]["key_bundle"]["installed_now"] is not False):
        raise ValueError("S611 key binding invalid")
    return path


class LoadedAuthorityKey:
    """Short-lived mutable key material that clears its buffer on exit."""

    def __init__(self, key_id: str, key: bytes) -> None:
        self.key_id = key_id
        self._key = bytearray(key)
        self.cleared = False

    def expose(self) -> bytes:
        return bytes(self._key)

    def clear(self) -> None:
        for index in range(len(self._key)):
            self._key[index] = 0
        self.cleared = True

    def __enter__(self) -> "LoadedAuthorityKey":
        return self

    def __exit__(self, _kind, _value, _traceback) -> None:
        self.clear()

    def __del__(self) -> None:
        self.clear()


def _open_private_parent(path: Path) -> int:
    if not path.is_absolute() or path.name in {"", ".", ".."}:
        raise ValueError("authority key path invalid")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    current = os.open("/", flags)
    try:
        for component in path.parent.parts[1:]:
            following = os.open(
                component, flags | os.O_NOFOLLOW, dir_fd=current
            )
            os.close(current)
            current = following
        metadata = os.fstat(current)
        if (not stat.S_ISDIR(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o700
                or metadata.st_uid != os.getuid()
                or metadata.st_gid != os.getgid()):
            raise ValueError("authority key parent identity invalid")
        return current
    except Exception:
        os.close(current)
        raise


def _decode_closed_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("authority key schema duplicate field")
        result[key] = value
    return result


def _parse_key_bundle(payload: bytes, requested_key_id: str) -> LoadedAuthorityKey:
    try:
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=_decode_closed_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("authority key schema invalid") from error
    if (not isinstance(value, dict)
            or set(value) != {"schema", "active_key_id", "keys"}
            or value.get("schema") != "agent_bridge.story_render_authority_keys.v1"
            or not isinstance(value.get("active_key_id"), str)
            or not isinstance(value.get("keys"), list)
            or not 1 <= len(value["keys"]) <= 16):
        raise ValueError("authority key schema invalid")
    records = {}
    active = []
    for row in value["keys"]:
        if (not isinstance(row, dict)
                or set(row) != {"key_id", "status", "key_hex"}
                or not isinstance(row.get("key_id"), str) or not row["key_id"]
                or row.get("status") not in {"active", "verify_only", "revoked"}
                or row["key_id"] in records):
            raise ValueError("authority key schema invalid")
        raw = row.get("key_hex")
        if (not isinstance(raw, str) or len(raw) != 64 or raw != raw.lower()):
            raise ValueError("authority key schema invalid")
        try:
            decoded = bytes.fromhex(raw)
        except ValueError as error:
            raise ValueError("authority key schema invalid") from error
        if len(decoded) != 32 or not any(decoded):
            raise ValueError("authority key schema invalid")
        records[row["key_id"]] = (row["status"], decoded)
        if row["status"] == "active":
            active.append(row["key_id"])
    if active != [value["active_key_id"]]:
        raise ValueError("authority key schema invalid")
    if requested_key_id not in records:
        raise ValueError("authority key id unavailable")
    status, key = records[requested_key_id]
    if status == "revoked":
        raise ValueError("authority key revoked")
    return LoadedAuthorityKey(requested_key_id, key)


def _load_authority_key(path: Path, requested_key_id: str) -> LoadedAuthorityKey:
    parent_fd = _open_private_parent(path)
    descriptor = None
    try:
        try:
            descriptor = os.open(
                path.name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
        except OSError as error:
            raise ValueError("authority key open failed") from error
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_uid != os.getuid()
                or metadata.st_gid != os.getgid()
                or metadata.st_nlink != 1):
            raise ValueError("authority key identity invalid")
        payload = bytearray()
        while True:
            chunk = os.read(descriptor, 8192)
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > MAX_KEY_BUNDLE_BYTES:
                raise ValueError("authority key schema too large")
        return _parse_key_bundle(bytes(payload), requested_key_id)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_fd)


def load_installed_authority_key(requested_key_id: str) -> LoadedAuthorityKey:
    """Load one configured key from the fixed S611 path; never create or fallback."""
    return _load_authority_key(secure_key_bundle_path(), requested_key_id)
