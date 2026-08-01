#!/usr/bin/env python3
"""S609 fail-closed verifier implementations with no executor or secret loading."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Callable


EXECUTOR_AUTHORIZATION_FIELDS = (
    "authorization_id", "contract_sha256", "preflight_sha256",
    "output_directory", "action", "issued_at", "expires_at", "single_use_nonce",
)
SIGNED_AUTHORIZATION_FIELDS = EXECUTOR_AUTHORIZATION_FIELDS + (
    "issuer", "subject", "key_id",
)
FIXED_NONCE_STORE = Path(
    "/home/pallasting/.agent-bridge-secure/story-render/story-render-nonces.sqlite3"
)
FIXED_TTS_DIR = Path(
    "/4TNVMe2/aiot_weights/modelscope/models/"
    "Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice/snapshots/master"
)
AuthorityVerifier = Callable[[dict[str, Any]], bool]
ModelVerifier = Callable[[dict[str, Any], dict[str, Any]], bool]


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_contract(contract: dict[str, Any]) -> None:
    if (contract.get("schema")
            != "agent_bridge.story_executor_authority_model_nonce_contract.v1"
            or contract.get("execution_authorized") is not False
            or any(contract.get("runtime_effects", {}).values())):
        raise ValueError("S608 contract boundary invalid")
    bound = {key: contract[key] for key in (
        "evidence", "authority_proof", "model_bundle", "nonce_store",
        "receipt_schema", "blockers", "execution_authorized", "runtime_effects")}
    if _digest(bound) != contract.get("contract_sha256"):
        raise ValueError("S608 contract digest invalid")


def canonical_authorization_message(
    envelope: dict[str, Any], contract: dict[str, Any]
) -> bytes:
    """Return the domain-separated canonical bytes covered by the owner MAC."""
    _validate_contract(contract)
    expected = set(SIGNED_AUTHORIZATION_FIELDS)
    fields = set(envelope) - {"mac_sha256"}
    if fields != expected or any(
        not isinstance(envelope[name], str) or not envelope[name]
        for name in SIGNED_AUTHORIZATION_FIELDS
    ):
        raise ValueError("authorization envelope fields invalid")
    authority = contract["authority_proof"]
    if (authority.get("algorithm") != "hmac-sha256"
            or authority.get("canonicalization") != "utf8-jcs-rfc8785"
            or authority.get("signed_fields") != list(SIGNED_AUTHORIZATION_FIELDS)):
        raise ValueError("authorization envelope contract invalid")
    canonical = json.dumps(
        {name: envelope[name] for name in SIGNED_AUTHORIZATION_FIELDS},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return authority["domain_separator"].encode("ascii") + b"\0" + canonical


def build_authority_verifier(
    *, envelope: dict[str, Any], key: bytes, contract: dict[str, Any]
) -> AuthorityVerifier:
    """Bind a full proof envelope to the executor's intentionally narrow view."""
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("authority key must contain at least 32 bytes")
    if set(envelope) != set(SIGNED_AUTHORIZATION_FIELDS) | {"mac_sha256"}:
        raise ValueError("authorization envelope fields invalid")
    mac = envelope.get("mac_sha256")
    if not isinstance(mac, str) or len(mac) != 64:
        raise ValueError("authorization envelope MAC invalid")
    try:
        bytes.fromhex(mac)
    except ValueError as error:
        raise ValueError("authorization envelope MAC invalid") from error
    message = canonical_authorization_message(envelope, contract)
    expected_mac = hmac.new(key, message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected_mac):
        raise ValueError("authorization envelope MAC invalid")
    signed_view = {name: envelope[name] for name in EXECUTOR_AUTHORIZATION_FIELDS}

    def verify(candidate: dict[str, Any]) -> bool:
        return set(candidate) == set(EXECUTOR_AUTHORIZATION_FIELDS) and all(
            isinstance(candidate.get(name), str)
            and hmac.compare_digest(candidate[name], signed_view[name])
            for name in EXECUTOR_AUTHORIZATION_FIELDS
        )

    return verify


def _plain_regular_file(path: Path) -> bool:
    try:
        return path.is_absolute() and path.resolve() == path and path.is_file()
    except OSError:
        return False


def build_model_verifier(contract: dict[str, Any]) -> ModelVerifier:
    """Build a verifier that streams every bound model file before admission."""
    _validate_contract(contract)
    bundle = contract["model_bundle"]
    captured_digest = contract["contract_sha256"]
    snapshot = Path(bundle["snapshot"])
    expected_model = snapshot / "cpu_int4"
    expected_tts = FIXED_TTS_DIR

    def verify(model: dict[str, Any], supplied_contract: dict[str, Any]) -> bool:
        try:
            _validate_contract(supplied_contract)
            if supplied_contract.get("contract_sha256") != captured_digest:
                return False
            if set(model) != {"inference_path", "model_path", "tts_dir"}:
                return False
            paths = {name: Path(value) for name, value in model.items()}
            if (paths["inference_path"] != Path(bundle["inference_path"])
                    or paths["model_path"] != expected_model
                    or paths["tts_dir"] != expected_tts
                    or not paths["tts_dir"].is_dir()
                    or paths["tts_dir"].resolve() != paths["tts_dir"]):
                return False
            controls = (
                (Path(bundle["manifest_path"]), bundle["manifest_sha256"]),
                (Path(bundle["inference_path"]), bundle["inference_sha256"]),
            )
            for path, expected_hash in controls:
                if not _plain_regular_file(path) or _sha256_file(path) != expected_hash:
                    return False
            for row in bundle["files"]:
                path = snapshot / row["path"]
                if (not _plain_regular_file(path) or path.stat().st_size != row["size"]
                        or _sha256_file(path) != row["sha256"]):
                    return False
            return True
        except (KeyError, OSError, TypeError, ValueError):
            return False

    return verify


def fixed_nonce_store_path(contract: dict[str, Any]) -> Path:
    """Return the immutable nonce path without creating it or its parent."""
    _validate_contract(contract)
    nonce = contract["nonce_store"]
    if (nonce.get("path") != str(FIXED_NONCE_STORE)
            or nonce.get("caller_configurable") is not False
            or nonce.get("outside_render_output_root") is not True
            or nonce.get("installed_now") is not False):
        raise ValueError("nonce contract invalid")
    return FIXED_NONCE_STORE
