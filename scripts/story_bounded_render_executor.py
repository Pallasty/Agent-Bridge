#!/usr/bin/env python3
"""Fail-closed bounded Story renderer core with no CLI or playback surface."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import wave
from array import array
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


AuthorityVerifier = Callable[[dict[str, Any]], bool]
ModelVerifier = Callable[[dict[str, Any], dict[str, Any]], bool]
Runner = Callable[..., dict[str, Any]]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("schema")
        != "agent_bridge.story_bounded_render_execution_contract.v1"
        or contract.get("status")
        != "story_bounded_render_execution_contract_reviewable"
        or contract.get("execution_authorized") is not False
        or any(contract.get("runtime_effects", {}).values())
    ):
        raise ValueError("execution contract boundary invalid")
    bound = {
        key: contract[key]
        for key in (
            "evidence",
            "bounds",
            "authority",
            "state_machine",
            "execution_authorized",
            "runtime_effects",
        )
    }
    if _digest(bound) != contract.get("contract_sha256"):
        raise ValueError("execution contract digest invalid")
    bounds = contract["bounds"]
    if (
        bounds.get("existing_output_overwrite_allowed") is not False
        or bounds.get("network_allowed") is not False
        or bounds.get("gpu_allowed") is not False
        or contract.get("authority", {}).get("record", {}).get("supported")
        is not False
        or contract.get("authority", {}).get("memory_write", {}).get("supported")
        is not False
    ):
        raise ValueError("execution contract safety boundary invalid")


def _utc_time(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid {field}") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"invalid {field}")
    return parsed.astimezone(timezone.utc)


def _safe_output_directory(contract: dict[str, Any], raw: str) -> Path:
    root = Path(contract["bounds"]["output_root"]).resolve()
    output = Path(raw).resolve()
    if output.parent != root:
        raise ValueError("output directory outside contract root")
    if output.exists():
        raise ValueError("output target exists")
    if not root.is_dir():
        raise ValueError("contract output root missing")
    return output


def _validate_authorization(
    *,
    contract: dict[str, Any],
    authorization: dict[str, Any],
    request: dict[str, Any],
    now: datetime,
    authority_verifier: AuthorityVerifier,
) -> Path:
    required = {
        "authorization_id",
        "contract_sha256",
        "preflight_sha256",
        "output_directory",
        "action",
        "issued_at",
        "expires_at",
        "single_use_nonce",
    }
    if set(authorization) != required:
        raise ValueError("authorization envelope fields invalid")
    if not all(
        isinstance(authorization[key], str) and authorization[key]
        for key in required
    ):
        raise ValueError("authorization envelope values invalid")
    if authorization["action"] != "render":
        raise ValueError("authorization action invalid")
    if authorization["contract_sha256"] != contract["contract_sha256"]:
        raise ValueError("contract SHA-256 mismatch")
    preflight = request.get("preflight", {})
    if (
        authorization["preflight_sha256"]
        != contract["evidence"]["preflight_sha256"]
        or authorization["preflight_sha256"] != preflight.get("preflight_sha256")
    ):
        raise ValueError("preflight SHA-256 mismatch")
    if authorization["output_directory"] != request.get("output_directory"):
        raise ValueError("output directory authorization mismatch")
    issued_at = _utc_time(authorization["issued_at"], "issued_at")
    expires_at = _utc_time(authorization["expires_at"], "expires_at")
    now = now.astimezone(timezone.utc)
    if issued_at > now:
        raise ValueError("authorization not active")
    if expires_at <= now:
        raise ValueError("authorization expired")
    if expires_at <= issued_at:
        raise ValueError("authorization interval invalid")
    if expires_at - issued_at > timedelta(minutes=10):
        raise ValueError("authorization interval too long")
    try:
        verified = authority_verifier(dict(authorization))
    except Exception as error:
        raise ValueError("authority proof rejected") from error
    if verified is not True:
        raise ValueError("authority proof rejected")
    return _safe_output_directory(contract, authorization["output_directory"])


def _validate_request(contract: dict[str, Any], request: dict[str, Any]) -> None:
    if request.get("playback") is not False:
        raise ValueError("playback requested")
    if request.get("record") is not False:
        raise ValueError("recording requested")
    if request.get("write_" + "memory") is not False:
        raise ValueError("memory write requested")
    bounds = contract["bounds"]
    render_requests = request.get("preflight", {}).get("render_requests", [])
    if not 1 <= len(render_requests) <= bounds["max_segments_per_grant"]:
        raise ValueError("segment limit exceeded")
    allowed_speakers = set(bounds["allowed_speakers"])
    gaps = request.get("preflight", {}).get("assembly_gap_seconds", [])
    if (
        len(gaps) != len(render_requests) - 1
        or any(not isinstance(gap, (int, float)) or not 0 <= gap <= 10 for gap in gaps)
    ):
        raise ValueError("assembly gaps invalid")
    for row in render_requests:
        if (
            set(row)
            != {
                "event_id",
                "text",
                "qwen_speaker",
                "style_instruction",
                "cache_key",
            }
            or row["qwen_speaker"] not in allowed_speakers
            or not isinstance(row["text"], str)
            or not row["text"].strip()
            or not isinstance(row["style_instruction"], str)
            or not row["style_instruction"].strip()
            or len(row["style_instruction"]) > 120
            or not isinstance(row["cache_key"], str)
            or len(row["cache_key"]) != 64
        ):
            raise ValueError("render request invalid")
    model = request.get("model", {})
    if set(model) != {"inference_path", "model_path", "tts_dir"}:
        raise ValueError("model request invalid")
    inference_path = Path(model["inference_path"])
    model_path = Path(model["model_path"])
    tts_dir = Path(model["tts_dir"])
    if not inference_path.is_file() or not model_path.is_dir() or not tts_dir.is_dir():
        raise ValueError("model assets missing")
    if _sha256_file(inference_path) != contract["evidence"][
        "model_inference_sha256"
    ]:
        raise ValueError("model inference SHA-256 mismatch")
    runner_path = Path(contract["evidence"]["trusted_runner_path"])
    if (
        not runner_path.is_file()
        or _sha256_file(runner_path)
        != contract["evidence"]["trusted_runner_sha256"]
    ):
        raise ValueError("trusted runner SHA-256 mismatch")


def _consume_nonce(
    store_path: Path, authorization: dict[str, Any], now: datetime
) -> None:
    store_path = store_path.resolve()
    if not store_path.parent.is_dir():
        raise ValueError("nonce store parent missing")
    created = not store_path.exists()
    with sqlite3.connect(store_path) as connection:
        connection.execute("pragma journal_mode=WAL")
        connection.execute(
            "create table if not exists consumed_nonces ("
            "nonce text primary key, authorization_id text not null, "
            "consumed_at text not null)"
        )
        try:
            connection.execute("begin immediate")
            connection.execute(
                "insert into consumed_nonces(nonce, authorization_id, consumed_at) "
                "values (?, ?, ?)",
                (
                    authorization["single_use_nonce"],
                    authorization["authorization_id"],
                    now.astimezone(timezone.utc).isoformat(),
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as error:
            connection.rollback()
            raise ValueError("single-use nonce already consumed") from error
    if created:
        store_path.chmod(0o600)


def _load_runner(path: Path) -> Runner:
    spec = importlib.util.spec_from_file_location("bounded_story_trusted_runner", path)
    if spec is None or spec.loader is None:
        raise ValueError("trusted runner import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_trial


def _probe_wav(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        sample_width = stream.getsampwidth()
        sample_rate = stream.getframerate()
        frames = stream.getnframes()
        payload = stream.readframes(frames)
    if channels != 1 or sample_width != 2 or sample_rate != 24000 or frames < 1:
        raise ValueError("audio format invalid")
    samples = array("h")
    samples.frombytes(payload)
    if sys.byteorder != "little":
        samples.byteswap()
    peak = max((abs(value) for value in samples), default=0)
    if peak == 0:
        raise ValueError("audio is silent")
    return {
        "sha256": _sha256_file(path),
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "frames": frames,
        "duration_seconds": frames / sample_rate,
        "peak": peak / 32768.0,
        "non_silent": True,
    }


def _assemble(
    segment_paths: list[Path], gaps: list[float], output_path: Path
) -> None:
    with wave.open(str(output_path), "wb") as destination:
        destination.setnchannels(1)
        destination.setsampwidth(2)
        destination.setframerate(24000)
        for index, path in enumerate(segment_paths):
            with wave.open(str(path), "rb") as source:
                if (
                    source.getnchannels() != 1
                    or source.getsampwidth() != 2
                    or source.getframerate() != 24000
                ):
                    raise ValueError("segment format changed during assembly")
                destination.writeframes(source.readframes(source.getnframes()))
            if index < len(gaps):
                destination.writeframes(b"\x00\x00" * round(gaps[index] * 24000))


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".part")
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _cleanup_owned(output: Path, owned: list[Path]) -> None:
    for path in reversed(owned):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        output.rmdir()
    except OSError:
        pass


def execute_bounded_render(
    *,
    contract: dict[str, Any],
    authorization: dict[str, Any],
    request: dict[str, Any],
    now: datetime,
    authority_verifier: AuthorityVerifier,
    model_verifier: ModelVerifier,
    nonce_store_path: Path,
) -> dict[str, Any]:
    """Execute rendering only after externally verified, single-use authority."""

    _validate_contract(contract)
    _validate_request(contract, request)
    output = _validate_authorization(
        contract=contract,
        authorization=authorization,
        request=request,
        now=now,
        authority_verifier=authority_verifier,
    )
    try:
        model_verified = model_verifier(dict(request["model"]), contract)
    except Exception as error:
        raise ValueError("model bundle proof rejected") from error
    if model_verified is not True:
        raise ValueError("model bundle proof rejected")
    _consume_nonce(nonce_store_path, authorization, now)
    output.mkdir(mode=0o700)
    owned: list[Path] = []
    try:
        runner_path = Path(contract["evidence"]["trusted_runner_path"])
        runner = _load_runner(runner_path)
        model = request["model"]
        render_requests = request["preflight"]["render_requests"]
        segment_rows = []
        segment_paths = []
        for index, row in enumerate(render_requests):
            temporary = output / f"{index:02d}.wav.part"
            final = output / f"{index:02d}.wav"
            owned.extend([temporary, final])
            result = runner(
                inference_path=Path(model["inference_path"]),
                expected_inference_sha256=contract["evidence"][
                    "model_inference_sha256"
                ],
                model_path=Path(model["model_path"]),
                tts_dir=Path(model["tts_dir"]),
                output_path=temporary,
                text=row["text"],
                speaker=row["qwen_speaker"],
                language="Chinese",
                max_new_tokens=contract["bounds"][
                    "max_codec_frames_per_segment"
                ],
                style_instruction=row["style_instruction"],
            )
            frames = result.get("generated_codec_frames", 0)
            if (
                result.get("stopped_before_frame_cap") is not True
                or result.get("frame_cap")
                != contract["bounds"]["max_codec_frames_per_segment"]
                or not 1 <= frames < result["frame_cap"]
            ):
                raise ValueError("natural EOS not reached")
            audio = _probe_wav(temporary)
            os.replace(temporary, final)
            segment_paths.append(final)
            segment_rows.append(
                {
                    "index": index,
                    "event_id": row["event_id"],
                    "cache_key": row["cache_key"],
                    "speaker": row["qwen_speaker"],
                    "generated_codec_frames": frames,
                    "natural_eos": True,
                    "audio_path": str(final),
                    **audio,
                }
            )
        assembly_part = output / "chapter.wav.part"
        assembly_final = output / "chapter.wav"
        owned.extend([assembly_part, assembly_final])
        gaps = request["preflight"]["assembly_gap_seconds"]
        _assemble(segment_paths, gaps, assembly_part)
        assembly = _probe_wav(assembly_part)
        if assembly["duration_seconds"] > contract["bounds"][
            "max_assembled_duration_seconds"
        ]:
            raise ValueError("assembled duration exceeds contract")
        os.replace(assembly_part, assembly_final)
        assembly["audio_path"] = str(assembly_final)
        assembly["gap_seconds"] = gaps
        runtime_effects = {
            "created_output_directory": True,
            "loaded_model": True,
            "executed_onnx": True,
            "rendered_audio": True,
            "played_audio": False,
            "recorded_audio": False,
            "wrote_cache": False,
            "wrote_" + "memory": False,
            "consumed_render_nonce": True,
        }
        bound = {
            "authorization_id": authorization["authorization_id"],
            "contract_sha256": contract["contract_sha256"],
            "preflight_sha256": authorization["preflight_sha256"],
            "segments": segment_rows,
            "assembly": assembly,
            "runtime_effects": runtime_effects,
        }
        receipt = {
            "schema": "agent_bridge.story_bounded_render_receipt.v1",
            "status": "bounded_render_machine_verified",
            **bound,
            "receipt_payload_sha256": _digest(bound),
            "playback_authorized": False,
            "memory_authorized": False,
            "next_gate": "separate_playback_authorization_or_render_review",
        }
        receipt_path = output / "render-receipt.json"
        owned.extend([receipt_path.with_name(receipt_path.name + ".part"), receipt_path])
        _atomic_json(receipt_path, receipt)
        return receipt
    except Exception:
        _cleanup_owned(output, owned)
        raise
