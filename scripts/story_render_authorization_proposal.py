#!/usr/bin/env python3
"""Build an owner-reviewable Story authorization proposal without signing."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
import types
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMPOSITION_PATH = ROOT / "scripts/story_executor_secure_runtime_composition.py"
COMPOSITION_SHA256 = (
    "0ac4ba4116a341310a34a02bf94833bc2d582fa7728b6eac905150c7fb9c27fe"
)
INSTALLATION_RESULT_PATH = (
    ROOT
    / "docs/design/voice-scene/"
    "s614_story_render_secure_configuration_installation_result.json"
)
INSTALLATION_RESULT_SHA256 = (
    "c3e50d1b9bd716e3274c670f15a47622416fbe6b7b5391486f085acc85a9edb4"
)
ACTIVE_KEY_ID = "story-render-owner-v1"
ISSUER = "agent-bridge-owner-console"
SUBJECT = "story-bounded-render-executor"
TTL_SECONDS = 300


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_installation_result() -> dict[str, Any]:
    payload = INSTALLATION_RESULT_PATH.read_bytes()
    if hashlib.sha256(payload).hexdigest() != INSTALLATION_RESULT_SHA256:
        raise ValueError("S614 installation result source drift")
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("S614 installation result invalid")
    return value


def _load_composition():
    source = COMPOSITION_PATH.read_bytes()
    if hashlib.sha256(source).hexdigest() != COMPOSITION_SHA256:
        raise ValueError("S610 composition source drift")
    module = types.ModuleType("s615_pinned_secure_composition")
    module.__file__ = str(COMPOSITION_PATH)
    exec(compile(source, str(COMPOSITION_PATH), "exec"), module.__dict__)
    return module


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _random_hex(byte_count: int) -> str:
    return secrets.token_hex(byte_count)


def _validate_public_identifier(value: str, expected_length: int) -> None:
    if (
        not isinstance(value, str)
        or len(value) != expected_length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("authorization proposal identifier invalid")


def _validate_installed_custody(
    runtime_contract: dict[str, Any],
) -> dict[str, Any]:
    installation_result = _read_installation_result()
    installation = installation_result.get("installation", {})
    runtime = Path(installation.get("runtime_directory", ""))
    key_bundle = Path(installation.get("key_bundle", ""))
    if (
        installation_result.get("schema")
        != "agent_bridge.story_render_secure_configuration_installation.v1"
        or installation_result.get("status")
        != "story_render_secure_configuration_installed"
        or installation_result.get("execution_authorized") is not False
        or installation.get("active_key_id") != ACTIVE_KEY_ID
        or installation.get("runtime_directory_mode") != "0700"
        or installation.get("key_bundle_mode") != "0600"
        or installation.get("key_material_disclosed") is not False
    ):
        raise ValueError("S614 installation result invalid")
    runtime_metadata = runtime.lstat()
    key_metadata = key_bundle.lstat()
    if (
        not stat.S_ISDIR(runtime_metadata.st_mode)
        or stat.S_IMODE(runtime_metadata.st_mode) != 0o700
        or runtime_metadata.st_uid != os.getuid()
        or runtime_metadata.st_gid != os.getgid()
        or not stat.S_ISREG(key_metadata.st_mode)
        or stat.S_IMODE(key_metadata.st_mode) != 0o600
        or key_metadata.st_uid != os.getuid()
        or key_metadata.st_gid != os.getgid()
        or key_metadata.st_nlink != 1
        or sorted(path.name for path in runtime.iterdir()) != [key_bundle.name]
    ):
        raise ValueError("installed authority custody metadata invalid")
    nonce_store = Path(runtime_contract["nonce_store"]["path"])
    nonce_family = (
        nonce_store,
        Path(str(nonce_store) + "-wal"),
        Path(str(nonce_store) + "-shm"),
        Path(str(nonce_store) + ".lock"),
    )
    if any(path.exists() for path in nonce_family):
        raise ValueError("nonce store must remain absent before execution")
    return {
        "installation_result_path": str(INSTALLATION_RESULT_PATH),
        "installation_result_sha256": INSTALLATION_RESULT_SHA256,
        "runtime_directory": str(runtime),
        "active_key_id": ACTIVE_KEY_ID,
        "metadata_only": True,
        "key_material_read": False,
        "nonce_store_absent": True,
    }


def _validate_request_boundary(
    execution_contract: dict[str, Any], request: dict[str, Any]
) -> None:
    if not isinstance(request, dict):
        raise ValueError("composition request fields invalid")
    if (
        request.get("playback") is not False
        or request.get("record") is not False
        or request.get("write_memory") is not False
    ):
        raise ValueError("composition request effects invalid")
    output_root = Path(execution_contract["bounds"]["output_root"]).resolve()
    output = Path(request.get("output_directory", ""))
    if (
        not output.is_absolute()
        or output.resolve().parent != output_root
        or output.exists()
    ):
        raise ValueError("output directory outside contract root or already exists")


def build_story_render_authorization_proposal(
    *, execution_contract: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    """Build an unsigned, exact Story render proposal for later owner review.

    Args:
        execution_contract: The fixed S604 bounded-render contract.
        request: The exact no-playback, no-recording, no-memory render request.

    Returns:
        A content-addressed proposal without an authority proof.

    Raises:
        ValueError: If custody, contract, request, model, or output bounds drift.
    """
    composition = _load_composition()
    composition._validate_execution_contract(execution_contract)
    _validate_request_boundary(execution_contract, request)
    runtime_contract = composition._read_json(composition.RUNTIME_CONTRACT_PATH)
    verifiers = composition._load_verifiers()
    custody = _validate_installed_custody(runtime_contract)

    now = _utc_now()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("authorization proposal clock invalid")
    now = now.astimezone(timezone.utc).replace(microsecond=0)
    authorization_token = _random_hex(16)
    nonce = _random_hex(32)
    _validate_public_identifier(authorization_token, 32)
    _validate_public_identifier(nonce, 64)
    signed_fields = {
        "authorization_id": "story-render-auth-" + authorization_token,
        "contract_sha256": execution_contract["contract_sha256"],
        "preflight_sha256": execution_contract["evidence"]["preflight_sha256"],
        "output_directory": request["output_directory"],
        "action": "render",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=TTL_SECONDS)).isoformat(),
        "single_use_nonce": nonce,
        "issuer": ISSUER,
        "subject": SUBJECT,
        "key_id": ACTIVE_KEY_ID,
    }
    composition._validate_request(
        request,
        execution_contract,
        signed_fields,
        runtime_contract,
        verifiers,
    )
    if TTL_SECONDS > runtime_contract["authority_proof"]["maximum_ttl_seconds"]:
        raise ValueError("authorization proposal TTL exceeds contract")
    proposal = {
        "signed_fields": signed_fields,
        "signed_fields_sha256": _digest(signed_fields),
        "request_sha256": _digest(request),
        "proof_field": runtime_contract["authority_proof"]["proof_field"],
        "proof_present": False,
        "ttl_seconds": TTL_SECONDS,
    }
    boundaries = {
        "real_key_read": False,
        "real_mac_generated": False,
        "nonce_store_created": False,
        "executor_invoked": False,
    }
    runtime_effects = {
        "created_nonce_store": False,
        "called_executor": False,
        "loaded_model": False,
        "executed_onnx": False,
        "rendered_audio": False,
        "played_audio": False,
        "recorded_audio": False,
        "wrote_memory": False,
    }
    bound = {
        "proposal": proposal,
        "custody": custody,
        "boundaries": boundaries,
        "owner_signature_required": True,
        "execution_authorized": False,
        "runtime_effects": runtime_effects,
    }
    return {
        "schema": "agent_bridge.story_render_authorization_proposal.v1",
        "status": "story_render_authorization_proposal_reviewable",
        "decision": "owner_signature_required_execution_blocked",
        **bound,
        "proposal_sha256": _digest(bound),
        "next_gate": (
            "owner_authorized_story_render_envelope_signing_preflight"
        ),
    }
