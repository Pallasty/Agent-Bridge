#!/usr/bin/env python3
"""Prepare S606 executor arguments without importing or invoking the executor."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import types
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CONTRACT_PATH = ROOT / "docs/design/voice-scene/s608_story_executor_authority_model_nonce_contract.json"
VERIFIER_PATH = ROOT / "scripts/story_executor_runtime_verifiers.py"
VERIFIER_SHA256 = "f01520fbc1342a58b1c0c3d9731180dcd0d585c1fae508fd5fe1db922a542c37"
EXECUTOR_AUTHORIZATION_FIELDS = (
    "authorization_id", "contract_sha256", "preflight_sha256",
    "output_directory", "action", "issued_at", "expires_at", "single_use_nonce",
)
TTS_SUPPORT_FILES = {
    "config.json": "17a07f527a1c25ea30b4e023a184482a23d3e279d697b1dc81b1bde498d29cf9",
    "tokenizer_config.json": "dc3c31c3bdaedd5016382bb3cbe07323026775ad51f5a4fb564505992ae4a670",
    "vocab.json": "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910",
    "merges.txt": "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required:{path}")
    return value


def _load_verifiers():
    source = VERIFIER_PATH.read_bytes()
    if hashlib.sha256(source).hexdigest() != VERIFIER_SHA256:
        raise ValueError("runtime verifier source drift")
    module = types.ModuleType("s610_pinned_runtime_verifiers")
    module.__file__ = str(VERIFIER_PATH)
    exec(compile(source, str(VERIFIER_PATH), "exec"), module.__dict__)
    return module


def _validate_execution_contract(contract: dict[str, Any]) -> None:
    if (contract.get("schema") != "agent_bridge.story_bounded_render_execution_contract.v1"
            or contract.get("execution_authorized") is not False
            or any(contract.get("runtime_effects", {}).values())):
        raise ValueError("execution contract boundary invalid")
    bound = {key: contract[key] for key in (
        "evidence", "bounds", "authority", "state_machine",
        "execution_authorized", "runtime_effects")}
    if _digest(bound) != contract.get("contract_sha256"):
        raise ValueError("execution contract digest invalid")


def _validate_tts_support_assets(tts_dir: Path) -> None:
    if not tts_dir.is_absolute() or tts_dir.resolve() != tts_dir or not tts_dir.is_dir():
        raise ValueError("model support directory invalid")
    for relative, expected in TTS_SUPPORT_FILES.items():
        path = tts_dir / relative
        if (path.resolve() != path or not path.is_file()
                or _sha256_file(path) != expected):
            raise ValueError("model support asset mismatch")


def _validate_request(request: dict[str, Any], execution_contract: dict[str, Any],
                      envelope: dict[str, Any], runtime_contract: dict[str, Any],
                      verifiers) -> None:
    if set(request) != {"preflight", "model", "output_directory", "playback", "record", "write_memory"}:
        raise ValueError("composition request fields invalid")
    if request["playback"] is not False or request["record"] is not False or request["write_memory"] is not False:
        raise ValueError("composition request effects invalid")
    if (request["output_directory"] != envelope["output_directory"]
            or request.get("preflight", {}).get("preflight_sha256")
            != execution_contract["evidence"]["preflight_sha256"]
            or envelope["preflight_sha256"]
            != execution_contract["evidence"]["preflight_sha256"]
            or envelope["contract_sha256"] != execution_contract["contract_sha256"]):
        raise ValueError("composition request binding invalid")
    model = request.get("model", {})
    bundle = runtime_contract["model_bundle"]
    expected_model = {
        "inference_path": bundle["inference_path"],
        "model_path": str(Path(bundle["snapshot"]) / "cpu_int4"),
        "tts_dir": str(verifiers.FIXED_TTS_DIR),
    }
    if model != expected_model:
        raise ValueError("composition model binding invalid")
    _validate_tts_support_assets(verifiers.FIXED_TTS_DIR)


def _build_authority_verifier_context_with_key(
    *, envelope: dict[str, Any], key: bytes
):
    """Build a keyless verifier/dependency context while key bytes are available."""
    runtime_contract = _read_json(RUNTIME_CONTRACT_PATH)
    verifiers = _load_verifiers()
    authority_verifier = verifiers.build_authority_verifier(
        envelope=envelope, key=key, contract=runtime_contract)
    return authority_verifier, runtime_contract, verifiers


def _build_executor_model_verifier(
    *,
    execution_contract: dict[str, Any],
    runtime_contract: dict[str, Any],
    runtime_model_verifier: Callable[
        [dict[str, Any], dict[str, Any]], bool
    ],
):
    """Adapt S606's S604 contract argument to the bound S608 verifier view."""
    _validate_execution_contract(execution_contract)
    captured_execution_sha256 = execution_contract["contract_sha256"]

    def verify(
        model: dict[str, Any], supplied_execution_contract: dict[str, Any]
    ) -> bool:
        try:
            _validate_execution_contract(supplied_execution_contract)
            if (
                supplied_execution_contract.get("contract_sha256")
                != captured_execution_sha256
            ):
                return False
            return runtime_model_verifier(model, runtime_contract) is True
        except (KeyError, OSError, TypeError, ValueError):
            return False

    return verify


def _prepare_secure_bounded_render_with_authority_verifier_context(
    *, execution_contract: dict[str, Any], envelope: dict[str, Any],
    authority_verifier_context, request: dict[str, Any]
) -> dict[str, Any]:
    """Finish preparation after the authority-key context has been cleared."""
    if (not isinstance(authority_verifier_context, tuple)
            or len(authority_verifier_context) != 3):
        raise ValueError("authority verifier context invalid")
    authority_verifier, runtime_contract, verifiers = authority_verifier_context
    _validate_execution_contract(execution_contract)
    _validate_request(request, execution_contract, envelope, runtime_contract, verifiers)
    authorization = {name: envelope[name] for name in EXECUTOR_AUTHORIZATION_FIELDS}
    if not callable(authority_verifier) or authority_verifier(authorization) is not True:
        raise ValueError("authority verifier binding invalid")
    runtime_model_verifier = verifiers.build_model_verifier(runtime_contract)
    return {
        "contract": execution_contract,
        "authorization": authorization,
        "request": request,
        "authority_verifier": authority_verifier,
        "model_verifier": _build_executor_model_verifier(
            execution_contract=execution_contract,
            runtime_contract=runtime_contract,
            runtime_model_verifier=runtime_model_verifier,
        ),
        "nonce_store_path": verifiers.fixed_nonce_store_path(runtime_contract),
    }


def _prepare_secure_bounded_render_with_key(
    *, execution_contract: dict[str, Any], envelope: dict[str, Any],
    key: bytes, request: dict[str, Any]
) -> dict[str, Any]:
    """Private synthetic-key seam retained only for deterministic tests."""
    authority_verifier_context = _build_authority_verifier_context_with_key(
        envelope=envelope, key=key)
    return _prepare_secure_bounded_render_with_authority_verifier_context(
        execution_contract=execution_contract,
        envelope=envelope,
        authority_verifier_context=authority_verifier_context,
        request=request,
    )
