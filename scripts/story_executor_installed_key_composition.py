#!/usr/bin/env python3
"""S613 public preparation entrypoint backed only by fixed installed custody."""

from __future__ import annotations

import hashlib
from pathlib import Path
import types
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMPOSITION_PATH = ROOT / "scripts/story_executor_secure_runtime_composition.py"
COMPOSITION_SHA256 = "0ac4ba4116a341310a34a02bf94833bc2d582fa7728b6eac905150c7fb9c27fe"
BINDING_PATH = ROOT / "scripts/story_executor_posix_runtime_binding.py"
BINDING_SHA256 = "e2fd3d719a9b0996500c7447f1df3d4726db0bca6f3edb9336200aa8aa481208"
SIGNED_AUTHORIZATION_FIELDS = (
    "authorization_id", "contract_sha256", "preflight_sha256",
    "output_directory", "action", "issued_at", "expires_at",
    "single_use_nonce", "issuer", "subject", "key_id",
)
AUTHORIZATION_ENVELOPE_FIELDS = set(SIGNED_AUTHORIZATION_FIELDS) | {"mac_sha256"}


def _load_pinned(path: Path, expected: str, name: str):
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != expected:
        raise ValueError(f"{name} source drift")
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def _load_composition():
    return _load_pinned(COMPOSITION_PATH, COMPOSITION_SHA256,
                        "s613_pinned_secure_composition")


def _load_binding():
    return _load_pinned(BINDING_PATH, BINDING_SHA256,
                        "s613_pinned_posix_binding")


def _validate_closed_envelope(envelope: dict[str, Any]) -> str:
    if not isinstance(envelope, dict):
        raise ValueError("authorization envelope fields invalid")
    key_id = envelope.get("key_id")
    if not isinstance(key_id, str) or not key_id:
        raise ValueError("authorization envelope key_id invalid")
    if (set(envelope) != AUTHORIZATION_ENVELOPE_FIELDS
            or any(not isinstance(envelope[name], str) or not envelope[name]
                   for name in AUTHORIZATION_ENVELOPE_FIELDS)):
        raise ValueError("authorization envelope fields invalid")
    mac = envelope["mac_sha256"]
    if len(mac) != 64 or any(character not in "0123456789abcdef" for character in mac):
        raise ValueError("authorization envelope MAC invalid")
    return key_id


def prepare_installed_secure_bounded_render(
    *, execution_contract: dict[str, Any], envelope: dict[str, Any],
    request: dict[str, Any]
) -> dict[str, Any]:
    """Prepare S606 arguments using only the envelope-selected installed key."""
    key_id = _validate_closed_envelope(envelope)
    binding = _load_binding()
    composition = _load_composition()
    with binding.load_installed_authority_key(key_id) as loaded:
        if loaded.key_id != key_id:
            raise ValueError("installed authority key_id mismatch")
        authority_verifier_context = composition._build_authority_verifier_context_with_key(
            envelope=envelope,
            key=loaded.expose(),
        )
    prepared = composition._prepare_secure_bounded_render_with_authority_verifier_context(
        execution_contract=execution_contract,
        envelope=envelope,
        authority_verifier_context=authority_verifier_context,
        request=request,
    )
    if prepared.get("nonce_store_path") != binding.secure_nonce_store_path():
        raise ValueError("installed nonce binding mismatch")
    return prepared
