#!/usr/bin/env python3
"""Strict one-request/one-response adapter for bounded Story rendering."""

from __future__ import annotations

import hashlib
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


Executor = Callable[[dict[str, Any]], dict[str, Any]]
ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs/design/voice-scene"
PROTOCOL_CONTRACT_PATH = (
    VOICE_SCENE / "s620_story_render_one_shot_worker_protocol_contract.json"
)
PROTOCOL_CONTRACT_SHA256 = (
    "c044017a2015fae0b279b648f6fc415dcf6e516d214cc6ed2965b4efa0a38dd1"
)
CODEC_PATH = ROOT / "scripts/story_render_worker_protocol.py"
CODEC_SHA256 = "23cb69b10e2a11042fdfd4061b17549c22419581f08a00dc0da594257053358d"
EXECUTION_CONTRACT_PATH = (
    VOICE_SCENE / "s604_story_bounded_render_execution_contract.json"
)
EXECUTION_CONTRACT_SHA256 = (
    "9d458de17f1c18da93c773452707b538879e4fd28892a85e12804752e91ba369"
)
PREFLIGHT_RECEIPT_PATH = VOICE_SCENE / "s602_story_fixture_mcp_preflight_receipt.json"
PREFLIGHT_RECEIPT_SHA256 = (
    "2584a0d3152a4d2a06a80e790dada67144b31ad95b4e2787c99f7c1579cf9a32"
)
ACCEPTED_RECEIPT_PATH = (
    VOICE_SCENE / "s603_story_fixture_bounded_render_receipt.json"
)
ACCEPTED_RECEIPT_SHA256 = (
    "db9988eb3874c0638b8ee40ffb91c30ab6e5d7f53321bd11c2fc65b45ee6a971"
)
RUNTIME_CONTRACT_PATH = (
    VOICE_SCENE / "s608_story_executor_authority_model_nonce_contract.json"
)
RUNTIME_CONTRACT_SHA256 = (
    "6c16e7aeed567d7d32a4b8183845acf0f929dee4afadc38adcd9e707db1dc05f"
)
INSTALLED_COMPOSITION_PATH = (
    ROOT / "scripts/story_executor_installed_key_composition.py"
)
INSTALLED_COMPOSITION_SHA256 = (
    "56e27a1c02926addbd0b23f969e12107c0e1a7154d28d676733496b2aa760c53"
)
EXECUTOR_PATH = ROOT / "scripts/story_bounded_render_executor.py"
EXECUTOR_SHA256 = "e469e51f109f5e5427175d824eb84d14155e257879c7e438279065d27dbc9e46"
FIXED_TTS_DIR = (
    "/4TNVMe2/aiot_weights/modelscope/models/"
    "Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice/snapshots/master"
)


def _read_pinned_bytes(path: Path, expected_sha256: str) -> bytes:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("fixed artifact drift")
    return payload


def _read_pinned_json(path: Path, expected_sha256: str) -> dict[str, Any]:
    try:
        value = json.loads(_read_pinned_bytes(path, expected_sha256))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("fixed JSON artifact rejected") from error
    if not isinstance(value, dict):
        raise ValueError("fixed JSON artifact rejected")
    return value


def _load_pinned_module(path: Path, expected_sha256: str, name: str) -> Any:
    source = _read_pinned_bytes(path, expected_sha256)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def _load_installed_composition() -> Any:
    return _load_pinned_module(
        INSTALLED_COMPOSITION_PATH,
        INSTALLED_COMPOSITION_SHA256,
        "s637_installed_key_composition",
    )


def _load_executor() -> Any:
    return _load_pinned_module(
        EXECUTOR_PATH,
        EXECUTOR_SHA256,
        "s637_bounded_render_executor",
    )


def _load_protocol_contract() -> dict[str, Any]:
    return _read_pinned_json(PROTOCOL_CONTRACT_PATH, PROTOCOL_CONTRACT_SHA256)


def _load_codec() -> Any:
    return _load_pinned_module(
        CODEC_PATH,
        CODEC_SHA256,
        "s637_story_render_worker_protocol",
    )


class WorkerFailure(RuntimeError):
    """A public fixed-code failure that intentionally discards private detail."""

    def __init__(
        self,
        code: str,
        *,
        retryable: bool,
        private_detail: object | None = None,
    ) -> None:
        del private_detail
        self.code = code
        self.retryable = retryable
        super().__init__(code)


def _validate_private_receipt(receipt: dict[str, Any]) -> None:
    effects = receipt.get("runtime_effects") if isinstance(receipt, dict) else None
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema")
        != "agent_bridge.story_bounded_render_receipt.v1"
        or receipt.get("status") != "bounded_render_machine_verified"
        or receipt.get("playback_authorized") is not False
        or receipt.get("memory_authorized") is not False
        or not isinstance(receipt.get("segments"), list)
        or not receipt["segments"]
        or not all(isinstance(segment, dict) for segment in receipt["segments"])
        or not isinstance(receipt.get("assembly"), dict)
        or not isinstance(effects, dict)
        or any(
            effects.get(name) is not False
            for name in (
                "played_audio",
                "recorded_audio",
                "wrote_cache",
                "wrote_memory",
            )
        )
    ):
        raise ValueError("private receipt rejected")


def build_fixed_executor_request(
    *,
    decoded_request: dict[str, Any],
    protocol_contract: dict[str, Any],
    execution_contract: dict[str, Any],
    preflight_receipt: dict[str, Any],
    accepted_receipt: dict[str, Any],
    runtime_contract: dict[str, Any],
) -> dict[str, Any]:
    """Compose the fixed executor input without reading authority or model data."""
    fixture = protocol_contract["request"]["fixture"]
    preflight_sha256 = fixture["preflight_sha256"]
    segments = accepted_receipt.get("segments")
    if (
        decoded_request.get("fixture") != fixture
        or execution_contract.get("schema")
        != "agent_bridge.story_bounded_render_execution_contract.v1"
        or execution_contract.get("contract_sha256")
        != fixture["execution_contract_sha256"]
        or execution_contract.get("evidence", {}).get("preflight_sha256")
        != preflight_sha256
        or preflight_receipt.get("schema")
        != "agent_bridge.story_fixture_mcp_preflight.v1"
        or preflight_receipt.get("result", {}).get("preflight_sha256")
        != preflight_sha256
        or accepted_receipt.get("schema")
        != "agent_bridge.story_fixture_bounded_render.v1"
        or accepted_receipt.get("preflight", {}).get("preflight_sha256")
        != preflight_sha256
        or not isinstance(segments, list)
        or len(segments) != preflight_receipt.get("selection", {}).get(
            "selected_segments"
        )
        or runtime_contract.get("schema")
        != "agent_bridge.story_executor_authority_model_nonce_contract.v1"
    ):
        raise ValueError("fixed fixture evidence rejected")
    render_requests = []
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ValueError("fixed fixture segment rejected")
        render_requests.append(
            {
                "event_id": f"s620-fixed-chapter-2-segment-{index}",
                "text": segment["text"],
                "qwen_speaker": segment["speaker"],
                "style_instruction": segment["style_instruction"],
                "cache_key": segment["cache_key"],
            }
        )
    model_bundle = runtime_contract["model_bundle"]
    return {
        "preflight": {
            "preflight_sha256": preflight_sha256,
            "render_requests": render_requests,
            "assembly_gap_seconds": preflight_receipt["selection"][
                "assembly_gap_seconds"
            ],
        },
        "model": {
            "inference_path": model_bundle["inference_path"],
            "model_path": model_bundle["snapshot"] + "/cpu_int4",
            "tts_dir": FIXED_TTS_DIR,
        },
        "output_directory": decoded_request["authorization"]["output_directory"],
        "playback": False,
        "record": False,
        "write_memory": False,
    }


def _require_compatible_execution_contract(
    *,
    decoded_request: dict[str, Any],
    protocol_contract: dict[str, Any],
    execution_contract: dict[str, Any],
) -> None:
    authorization = decoded_request["authorization"]
    if (
        authorization["contract_sha256"]
        != execution_contract.get("contract_sha256")
        or protocol_contract["output_custody"]["root"]
        != execution_contract.get("bounds", {}).get("output_root")
    ):
        raise WorkerFailure("custody_rejected", retryable=False)


def execute_real(
    decoded_request: dict[str, Any],
    *,
    protocol_contract: dict[str, Any],
) -> dict[str, Any]:
    """Reach installed authority only after all fixed custody contracts agree."""
    execution_contract = _read_pinned_json(
        EXECUTION_CONTRACT_PATH,
        EXECUTION_CONTRACT_SHA256,
    )
    _require_compatible_execution_contract(
        decoded_request=decoded_request,
        protocol_contract=protocol_contract,
        execution_contract=execution_contract,
    )
    try:
        executor_request = build_fixed_executor_request(
            decoded_request=decoded_request,
            protocol_contract=protocol_contract,
            execution_contract=execution_contract,
            preflight_receipt=_read_pinned_json(
                PREFLIGHT_RECEIPT_PATH,
                PREFLIGHT_RECEIPT_SHA256,
            ),
            accepted_receipt=_read_pinned_json(
                ACCEPTED_RECEIPT_PATH,
                ACCEPTED_RECEIPT_SHA256,
            ),
            runtime_contract=_read_pinned_json(
                RUNTIME_CONTRACT_PATH,
                RUNTIME_CONTRACT_SHA256,
            ),
        )
        composition = _load_installed_composition()
        prepared = composition.prepare_installed_secure_bounded_render(
            execution_contract=execution_contract,
            envelope=decoded_request["authorization"],
            request=executor_request,
        )
    except WorkerFailure:
        raise
    except Exception as error:
        raise WorkerFailure(
            "authority_rejected",
            retryable=False,
            private_detail=error,
        ) from None
    try:
        executor = _load_executor()
        return executor.execute_bounded_render(
            **prepared,
            now=datetime.now(timezone.utc),
        )
    except Exception as error:
        raise WorkerFailure(
            "render_failed",
            retryable=False,
            private_detail=error,
        ) from None


def _success_response(
    *,
    receipt: dict[str, Any],
    request_id: str,
    protocol_contract: dict[str, Any],
) -> dict[str, Any]:
    _validate_private_receipt(receipt)
    assembly = receipt["assembly"]
    return {
        "protocol": protocol_contract["protocol"]["name"],
        "request_id": request_id,
        "status": "success",
        "render_id": request_id,
        "segment_count": len(receipt["segments"]),
        "assembly": {
            name: assembly[name]
            for name in protocol_contract["response"]["assembly_exact_fields"]
        },
        "playback_authorized": receipt["playback_authorized"],
        "memory_authorized": receipt["memory_authorized"],
    }


def _encode_public_error(
    *,
    codec: Any,
    protocol_contract: dict[str, Any],
    request_id: str | None,
    code: str,
    retryable: bool,
) -> bytes:
    if (
        code not in protocol_contract["response"]["error_codes"]
        or not isinstance(retryable, bool)
    ):
        code = "internal_failure"
        retryable = False
    return codec.encode_error_response(
        request_id=request_id,
        code=code,
        retryable=retryable,
        contract=protocol_contract,
    )


def process_request(
    raw: bytes,
    *,
    protocol_contract: dict[str, Any],
    codec: Any,
    execute: Executor,
) -> bytes:
    """Process one already-bounded request using an injected execution seam."""
    try:
        request = codec.decode_request(raw, protocol_contract)
    except codec.ProtocolError:
        return _encode_public_error(
            codec=codec,
            protocol_contract=protocol_contract,
            request_id=None,
            code="invalid_request",
            retryable=False,
        )
    try:
        receipt = execute(request)
    except WorkerFailure as error:
        return _encode_public_error(
            codec=codec,
            protocol_contract=protocol_contract,
            request_id=request["request_id"],
            code=error.code,
            retryable=error.retryable,
        )
    except Exception:
        return _encode_public_error(
            codec=codec,
            protocol_contract=protocol_contract,
            request_id=request["request_id"],
            code="internal_failure",
            retryable=False,
        )
    try:
        response = _success_response(
            receipt=receipt,
            request_id=request["request_id"],
            protocol_contract=protocol_contract,
        )
        encoded = json.dumps(
            response,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        codec.validate_worker_response(
            encoded,
            protocol_contract,
            expected_request_id=request["request_id"],
        )
        return encoded
    except Exception:
        return _encode_public_error(
            codec=codec,
            protocol_contract=protocol_contract,
            request_id=request["request_id"],
            code="internal_failure",
            retryable=False,
        )


def main(
    *,
    stdin: Any | None = None,
    stdout: Any | None = None,
    protocol_contract: dict[str, Any] | None = None,
    codec: Any | None = None,
    execute: Executor | None = None,
) -> int:
    """Read one bounded document and write exactly one bounded response."""
    if protocol_contract is None:
        protocol_contract = _load_protocol_contract()
    if codec is None:
        codec = _load_codec()
    if stdin is None:
        stdin = sys.stdin.buffer
    if stdout is None:
        stdout = sys.stdout.buffer
    if execute is None:
        execute = lambda decoded: execute_real(
            decoded,
            protocol_contract=protocol_contract,
        )
    maximum = protocol_contract["protocol"]["stdin_max_bytes"]
    raw = stdin.read(maximum + 1)
    response = process_request(
        raw,
        protocol_contract=protocol_contract,
        codec=codec,
        execute=execute,
    )
    stdout.write(response)
    stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
