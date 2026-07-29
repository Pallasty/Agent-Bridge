#!/usr/bin/env python3
"""Voice Scene S2 offline segment renderer, cache, assembler, and gated player."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import signal
import struct
import subprocess
import wave
from pathlib import Path
from typing import Any, Callable


MANIFEST_SCHEMA = "agent_bridge.story_render_manifest.v1"
Renderer = Callable[[dict[str, Any], Path], dict[str, Any]]


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_cache_key(request: dict[str, Any]) -> str:
    """Bind cache identity to source, text, model, profile version, and controls."""

    fields = {
        key: request[key]
        for key in (
            "source_sha256",
            "text",
            "model_sha256",
            "voice_profile_id",
            "voice_profile_version",
            "speed",
            "gain_db",
            "pause_ms",
        )
    }
    return hashlib.sha256(canonical_json(fields).encode("utf-8")).hexdigest()


def _pcm_rms(frames: bytes, sample_width: int) -> float:
    if sample_width != 2 or not frames:
        return 0.0
    count = len(frames) // 2
    samples = struct.unpack(f"<{count}h", frames)
    return math.sqrt(sum(sample * sample for sample in samples) / count)


def validate_wav(path: Path) -> dict[str, Any]:
    """Validate a non-empty, non-silent PCM WAV and report machine evidence."""

    if not path.is_file():
        return {"valid": False, "reason": "wav_missing"}
    try:
        with wave.open(str(path), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frame_count = wav.getnframes()
            compression = wav.getcomptype()
            frames = wav.readframes(frame_count)
    except (OSError, EOFError, wave.Error):
        return {"valid": False, "reason": "wav_invalid_container"}
    if (
        channels != 1
        or sample_width != 2
        or sample_rate < 8000
        or frame_count < max(1, sample_rate // 100)
        or compression != "NONE"
    ):
        return {"valid": False, "reason": "wav_format_or_duration_invalid"}
    rms = _pcm_rms(frames, sample_width)
    if rms < 1.0:
        return {"valid": False, "reason": "wav_silent"}
    return {
        "valid": True,
        "reason": "verified_pcm_wav",
        "sha256": sha256_file(path),
        "channels": channels,
        "sample_width": sample_width,
        "sample_rate": sample_rate,
        "frame_count": frame_count,
        "duration_ms": round(frame_count * 1000 / sample_rate),
        "rms": round(rms, 4),
    }


def _profile_by_speaker(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row["speaker_id"]: row
        for row in plan["voice_scene"]["voice_profiles"]
    }


def _request_for_event(
    plan: dict[str, Any],
    event: dict[str, Any],
    profile: dict[str, Any],
    backend: dict[str, Any],
    *,
    pause_ms: int,
    gain_db: float,
    speed: float,
) -> dict[str, Any]:
    request = {
        "event_id": event["event_id"],
        "sequence": event["sequence"],
        "text": event["utterance"]["text"],
        "speaker_id": event["utterance"]["speaker_id"],
        "voice_profile_id": profile["voice_profile_id"],
        "voice_profile_version": profile["version"],
        "voice": profile["voice"],
        "speed": speed,
        "gain_db": gain_db,
        "pause_ms": pause_ms,
        "source_sha256": plan["source"]["sha256"],
        "source_version": plan["source"]["version"],
        "backend": backend["backend"],
        "model_id": backend["model_id"],
        "model_sha256": backend["model_sha256"],
        "binary_sha256": backend["binary_sha256"],
    }
    request["cache_key"] = render_cache_key(request)
    return request


def _verify_receipt(
    receipt: Any,
    request: dict[str, Any],
    output: Path,
) -> str | None:
    if not isinstance(receipt, dict) or receipt.get("ok") is not True:
        return (
            str(receipt.get("error", "renderer_failed"))
            if isinstance(receipt, dict)
            else "renderer_receipt_invalid"
        )
    for field in ("backend", "model_id", "voice"):
        if receipt.get(field) != request[field]:
            return f"renderer_provenance_mismatch:{field}"
    if Path(str(receipt.get("output_file", ""))) != output:
        return "renderer_output_path_mismatch"
    wav = validate_wav(output)
    return None if wav["valid"] else wav["reason"]


def _normalize_pcm16(frames: bytes, target_rms: float = 3276.7) -> bytes:
    count = len(frames) // 2
    samples = struct.unpack(f"<{count}h", frames)
    current = math.sqrt(sum(sample * sample for sample in samples) / max(1, count))
    if current < 1.0:
        raise ValueError("cannot_normalize_silent_audio")
    scale = min(4.0, target_rms / current)
    normalized = [
        max(-32768, min(32767, round(sample * scale))) for sample in samples
    ]
    return struct.pack(f"<{count}h", *normalized)


def _assemble(
    segment_paths: list[Path],
    pauses_ms: list[int],
    gains_db: list[float],
    output: Path,
) -> dict[str, Any]:
    combined = bytearray()
    expected_format: tuple[int, int, int] | None = None
    for path, pause_ms, gain_db in zip(
        segment_paths, pauses_ms, gains_db, strict=True
    ):
        with wave.open(str(path), "rb") as wav:
            current_format = (
                wav.getnchannels(),
                wav.getsampwidth(),
                wav.getframerate(),
            )
            frames = wav.readframes(wav.getnframes())
        if expected_format is None:
            expected_format = current_format
        elif current_format != expected_format:
            raise ValueError("segment_wav_format_mismatch")
        if current_format[:2] != (1, 2):
            raise ValueError("segment_pcm16_mono_required")
        target_rms = 3276.7 * (10 ** (gain_db / 20))
        combined.extend(_normalize_pcm16(frames, target_rms=target_rms))
        silence_frames = round(current_format[2] * pause_ms / 1000)
        combined.extend(b"\0\0" * silence_frames)
    if expected_format is None:
        raise ValueError("no_segments_to_assemble")
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(expected_format[0])
        wav.setsampwidth(expected_format[1])
        wav.setframerate(expected_format[2])
        wav.writeframes(bytes(combined))
    return validate_wav(output)


def render_chapter(
    plan: dict[str, Any],
    output_dir: Path,
    backend: dict[str, Any],
    renderer: Renderer,
    *,
    retry_limit: int = 1,
    pause_ms: int = 120,
    gain_db: float = 0.0,
    speed: float = 1.0,
) -> dict[str, Any]:
    """Render, cache, assemble, and machine-verify one selected chapter lane."""

    if plan.get("status") != "story_plan_reviewable":
        raise ValueError("story_plan_not_reviewable")
    capabilities = backend.get("capabilities", {})
    for field, requested in (
        ("speed", speed != 1.0),
        ("gain", gain_db != 0.0),
        ("pause", pause_ms != 0),
    ):
        if requested and capabilities.get(field) is not True:
            raise ValueError(f"backend_capability_missing:{field}")
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    profiles = _profile_by_speaker(plan)
    timeline = sorted(
        plan["voice_scene"]["timeline"], key=lambda row: row["sequence"]
    )
    expected_sequence = [row["event_id"] for row in timeline]
    segments: list[dict[str, Any]] = []
    attempts_total = 0
    cache_hits = 0

    for event in timeline:
        speaker_id = event["utterance"]["speaker_id"]
        profile = profiles.get(speaker_id)
        if profile is None:
            raise ValueError(f"voice_profile_missing:{speaker_id}")
        if profile["backend"] not in (backend["backend"], "unassigned"):
            raise ValueError(f"voice_profile_backend_mismatch:{speaker_id}")
        request = _request_for_event(
            plan,
            event,
            profile,
            backend,
            pause_ms=pause_ms,
            gain_db=gain_db,
            speed=speed,
        )
        segment_path = cache_dir / f"{request['cache_key']}.wav"
        wav_evidence = validate_wav(segment_path)
        cached = wav_evidence["valid"]
        attempts = 0
        receipt: dict[str, Any] = {}
        if cached:
            cache_hits += 1
        else:
            if segment_path.exists():
                segment_path.unlink()
            last_error = "renderer_not_attempted"
            for _attempt in range(retry_limit + 1):
                attempts += 1
                attempts_total += 1
                receipt = renderer(request, segment_path)
                last_error = _verify_receipt(receipt, request, segment_path) or ""
                if not last_error:
                    break
                if segment_path.exists():
                    segment_path.unlink()
            if last_error:
                raise RuntimeError(
                    f"segment_render_failed:{event['event_id']}:{last_error}"
                )
            wav_evidence = validate_wav(segment_path)
        segments.append(
            {
                "event_id": event["event_id"],
                "sequence": event["sequence"],
                "cache_key": request["cache_key"],
                "path": str(segment_path.resolve()),
                "sha256": wav_evidence["sha256"],
                "duration_ms": wav_evidence["duration_ms"],
                "cached": cached,
                "attempts": attempts,
                "voice_profile_id": profile["voice_profile_id"],
                "voice_profile_version": profile["version"],
                "backend": backend["backend"],
                "model_id": backend["model_id"],
                "model_sha256": backend["model_sha256"],
                "binary_sha256": backend["binary_sha256"],
                "voice": profile["voice"],
                "pause_ms": pause_ms,
            }
        )

    chapter_path = output_dir / "chapter.wav"
    chapter_evidence = _assemble(
        [Path(row["path"]) for row in segments],
        [row["pause_ms"] for row in segments],
        [gain_db for _row in segments],
        chapter_path,
    )
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "status": "rendered_verified",
        "scene_id": plan["voice_scene"]["scene"]["scene_id"],
        "source_sha256": plan["source"]["sha256"],
        "source_version": plan["source"]["version"],
        "expected_event_sequence": expected_sequence,
        "backend": backend,
        "render_controls": {
            "speed": speed,
            "gain_db": gain_db,
            "pause_ms": pause_ms,
            "normalization": "pcm16_target_rms_-20dbfs",
            "pitch": "unsupported",
        },
        "segments": segments,
        "segment_summary": {
            "count": len(segments),
            "rendered": len(segments),
            "cache_hits": cache_hits,
            "attempts": attempts_total,
        },
        "chapter_artifact": {
            "path": str(chapter_path.resolve()),
            "sha256": chapter_evidence["sha256"],
            "duration_ms": chapter_evidence["duration_ms"],
            "sample_rate": chapter_evidence["sample_rate"],
            "channels": chapter_evidence["channels"],
            "verification": "machine_pcm_wav_integrity",
            "human_audition": "pending",
        },
        "player_gate": "explicit_owner_authorization_required",
    }
    (output_dir / "chapter_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    verification = verify_chapter_manifest(manifest)
    if not verification["valid"]:
        raise RuntimeError(
            "chapter_integrity_failed:" + ",".join(verification["errors"])
        )
    return manifest


def verify_chapter_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Revalidate ordering, segment hashes, and the assembled chapter artifact."""

    errors: list[str] = []
    segments = manifest.get("segments", [])
    event_ids = [row.get("event_id") for row in segments]
    if event_ids != manifest.get("expected_event_sequence"):
        errors.append("segment_order_mismatch")
    for row in segments:
        path = Path(str(row.get("path", "")))
        evidence = validate_wav(path)
        if not evidence["valid"]:
            errors.append(f"segment_invalid:{row.get('event_id')}")
        elif evidence["sha256"] != row.get("sha256"):
            errors.append(f"segment_hash_mismatch:{row.get('event_id')}")
    artifact = manifest.get("chapter_artifact", {})
    chapter_path = Path(str(artifact.get("path", "")))
    chapter_evidence = validate_wav(chapter_path)
    if not chapter_evidence["valid"]:
        errors.append("chapter_artifact_invalid")
    elif chapter_evidence["sha256"] != artifact.get("sha256"):
        errors.append("chapter_hash_mismatch")
    return {"valid": not errors, "errors": sorted(set(errors))}


class SubprocessRenderer:
    """No-shell adapter for the installed `ab-tts-synth` render-only binary."""

    def __init__(
        self,
        binary: Path,
        *,
        backend: str,
        model_id: str,
        environment: dict[str, str] | None = None,
    ) -> None:
        self.binary = binary
        self.backend = backend
        self.model_id = model_id
        self.environment = environment or {}

    def __call__(self, request: dict[str, Any], output: Path) -> dict[str, Any]:
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(self.binary),
            "--text",
            request["text"],
            "--out",
            str(output),
            "--backend",
            self.backend,
            "--voice",
            request["voice"],
            "--speed",
            str(request["speed"]),
        ]
        environment = os.environ.copy()
        environment.update(self.environment)
        process = subprocess.run(
            command,
            text=True,
            capture_output=True,
            env=environment,
            check=False,
        )
        receipt: dict[str, Any] = {}
        for line in reversed(process.stdout.splitlines()):
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                receipt = candidate
                break
        if process.returncode != 0 or receipt.get("ok") is not True:
            return {
                "ok": False,
                "error": receipt.get("error")
                or process.stderr.strip()
                or f"renderer_exit:{process.returncode}",
            }
        return {
            "ok": True,
            "backend": receipt.get("backend"),
            "model_id": self.model_id,
            "voice": receipt.get("voice"),
            "output_file": receipt.get("out"),
            "backend_receipt": receipt,
        }


class ChapterPlayer:
    """Persistent player state with an explicit owner gate for audio emission."""

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path

    def _read(self) -> dict[str, Any]:
        if not self.state_path.is_file():
            return {"state": "idle", "position_ms": 0, "audio_emitted": False}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _write(self, state: dict[str, Any]) -> dict[str, Any]:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return state

    @staticmethod
    def _require_owner(owner_authorized: bool) -> None:
        if not owner_authorized:
            raise PermissionError("owner_authorization_required")

    def _emit(self, path: str, position_ms: int) -> int:
        player = shutil.which("ffplay")
        if player is None:
            raise RuntimeError("ffplay_not_available")
        process = subprocess.Popen(
            [
                player,
                "-nodisp",
                "-autoexit",
                "-loglevel",
                "error",
                "-ss",
                f"{position_ms / 1000:.3f}",
                path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return process.pid

    def start(
        self,
        manifest: dict[str, Any],
        *,
        owner_authorized: bool,
        emit_audio: bool = False,
    ) -> dict[str, Any]:
        self._require_owner(owner_authorized)
        verification = verify_chapter_manifest(manifest)
        if not verification["valid"]:
            raise ValueError("chapter_manifest_invalid")
        state = {
            "state": "playing",
            "position_ms": 0,
            "artifact_path": manifest["chapter_artifact"]["path"],
            "artifact_sha256": manifest["chapter_artifact"]["sha256"],
            "audio_emitted": emit_audio,
            "pid": None,
        }
        if emit_audio:
            state["pid"] = self._emit(state["artifact_path"], 0)
        return self._write(state)

    def pause(self, *, position_ms: int) -> dict[str, Any]:
        state = self._read()
        if state.get("state") != "playing":
            raise ValueError("player_not_playing")
        pid = state.get("pid")
        if isinstance(pid, int):
            os.kill(pid, signal.SIGSTOP)
        state["state"] = "paused"
        state["position_ms"] = max(0, position_ms)
        return self._write(state)

    def resume(
        self, *, owner_authorized: bool, emit_audio: bool = False
    ) -> dict[str, Any]:
        self._require_owner(owner_authorized)
        state = self._read()
        if state.get("state") != "paused":
            raise ValueError("player_not_paused")
        pid = state.get("pid")
        if emit_audio and isinstance(pid, int):
            os.kill(pid, signal.SIGCONT)
        elif emit_audio:
            state["pid"] = self._emit(
                state["artifact_path"], state["position_ms"]
            )
        state["audio_emitted"] = bool(state.get("audio_emitted") or emit_audio)
        state["state"] = "playing"
        return self._write(state)

    def rewind(self, *, milliseconds: int) -> dict[str, Any]:
        state = self._read()
        state["position_ms"] = max(0, state.get("position_ms", 0) - milliseconds)
        return self._write(state)

    def status(self) -> dict[str, Any]:
        return self._read()
