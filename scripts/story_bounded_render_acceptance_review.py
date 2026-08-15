#!/usr/bin/env python3
"""Build the read-only S618 S617-to-S603 PCM acceptance review."""

from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


S603_RECEIPT = Path(
    "docs/design/voice-scene/s603_story_fixture_bounded_render_receipt.json"
)
S603_SCHEMA = Path(
    "docs/design/voice-scene/story_fixture_bounded_render.schema.json"
)
S617_RESULT = Path(
    "docs/design/voice-scene/s617_story_bounded_render_execution_result.json"
)
S617_RESULT_SCHEMA = Path(
    "docs/design/voice-scene/story_bounded_render_execution_result.schema.json"
)
S617_RENDER_SCHEMA = Path(
    "docs/design/voice-scene/story_bounded_render_receipt.schema.json"
)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a regular file without changing it."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    """Hash a JSON-compatible value using the repository canonical form."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_validated(path: Path, schema_path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        location = "/".join(str(part) for part in errors[0].absolute_path)
        raise ValueError(f"schema_validation_failed:{path}:{location}")
    return value


def _read_pcm(path: Path) -> tuple[dict[str, int], bytes]:
    with wave.open(str(path), "rb") as stream:
        if stream.getcomptype() != "NONE":
            raise ValueError(f"compressed_wav_forbidden:{path}")
        metadata = {
            "sample_rate_hz": stream.getframerate(),
            "channels": stream.getnchannels(),
            "sample_width_bytes": stream.getsampwidth(),
            "frames": stream.getnframes(),
        }
        pcm = stream.readframes(stream.getnframes())
    expected_bytes = (
        metadata["frames"]
        * metadata["channels"]
        * metadata["sample_width_bytes"]
    )
    if len(pcm) != expected_bytes:
        raise ValueError(f"truncated_pcm:{path}")
    return metadata, pcm


def compare_pcm_wav(reference: Path, candidate: Path) -> dict[str, Any]:
    """Compare two PCM WAVs while separating container and sample identity."""

    reference_metadata, reference_pcm = _read_pcm(reference)
    candidate_metadata, candidate_pcm = _read_pcm(candidate)
    reference_file_sha256 = sha256_file(reference)
    candidate_file_sha256 = sha256_file(candidate)
    reference_pcm_sha256 = hashlib.sha256(reference_pcm).hexdigest()
    candidate_pcm_sha256 = hashlib.sha256(candidate_pcm).hexdigest()
    return {
        "reference_file_sha256": reference_file_sha256,
        "candidate_file_sha256": candidate_file_sha256,
        "file_sha256_equal": reference_file_sha256 == candidate_file_sha256,
        "reference_file_bytes": reference.stat().st_size,
        "candidate_file_bytes": candidate.stat().st_size,
        "reference_pcm_sha256": reference_pcm_sha256,
        "candidate_pcm_sha256": candidate_pcm_sha256,
        "pcm_sha256_equal": reference_pcm_sha256 == candidate_pcm_sha256,
        "format_equal": reference_metadata == candidate_metadata,
        "sample_rate_hz": reference_metadata["sample_rate_hz"],
        "channels": reference_metadata["channels"],
        "sample_width_bytes": reference_metadata["sample_width_bytes"],
        "frames": reference_metadata["frames"],
    }


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def build_acceptance_review(repo_root: Path) -> dict[str, Any]:
    """Build deterministic S618 evidence from checked-in and live artifacts."""

    root = repo_root.resolve()
    s603_path = root / S603_RECEIPT
    s617_path = root / S617_RESULT
    s603 = _load_validated(s603_path, root / S603_SCHEMA)
    s617 = _load_validated(s617_path, root / S617_RESULT_SCHEMA)

    render_receipt_path = Path(s617["execution"]["render_receipt_path"])
    render_receipt = _load_validated(
        render_receipt_path,
        root / S617_RENDER_SCHEMA,
    )
    _require(
        sha256_file(render_receipt_path)
        == s617["execution"]["render_receipt_sha256"],
        "s617_render_receipt_hash_drift",
    )
    _require(
        s603["status"] == "story_fixture_bounded_render_owner_accepted",
        "s603_owner_acceptance_missing",
    )
    _require(
        s603["playback"] == {
            "backend": "pw-play",
            "authorized": True,
            "attempts": 1,
            "exit_code": 0,
        },
        "s603_owner_playback_not_completed",
    )
    owner_feedback = s603["owner_feedback"]
    _require(
        all(
            owner_feedback[field] is True
            for field in ("accepted", "natural", "clear", "speaker_distinction")
        )
        and owner_feedback["intervals"] == "accepted",
        "s603_owner_feedback_not_accepted",
    )
    _require(
        s617["execution"]["playback_authorized"] is False
        and s617["execution"]["memory_authorized"] is False
        and render_receipt["playback_authorized"] is False
        and render_receipt["memory_authorized"] is False,
        "s617_authority_boundary_drift",
    )

    s603_segments = s603["segments"]
    s617_segments = render_receipt["segments"]
    _require(
        len(s603_segments) == len(s617_segments) == 3,
        "segment_count_drift",
    )
    segment_comparisons: list[dict[str, Any]] = []
    for reference_row, candidate_row in zip(
        s603_segments, s617_segments, strict=True
    ):
        index = reference_row["index"]
        _require(index == candidate_row["index"], f"segment_index_drift:{index}")
        _require(
            reference_row["speaker"] == candidate_row["speaker"],
            f"segment_speaker_drift:{index}",
        )
        _require(
            reference_row["cache_key"] == candidate_row["cache_key"],
            f"segment_cache_key_drift:{index}",
        )
        reference_audio = Path(reference_row["audio_path"])
        candidate_audio = Path(candidate_row["audio_path"])
        _require(
            sha256_file(reference_audio) == reference_row["audio_sha256"],
            f"s603_segment_hash_drift:{index}",
        )
        _require(
            sha256_file(candidate_audio) == candidate_row["sha256"],
            f"s617_segment_hash_drift:{index}",
        )
        comparison = compare_pcm_wav(reference_audio, candidate_audio)
        _require(comparison["format_equal"], f"segment_format_drift:{index}")
        _require(comparison["pcm_sha256_equal"], f"segment_pcm_drift:{index}")
        segment_comparisons.append(
            {
                "index": index,
                "speaker": reference_row["speaker"],
                **comparison,
            }
        )

    reference_assembly = Path(s603["assembly"]["audio_path"])
    candidate_assembly = Path(render_receipt["assembly"]["audio_path"])
    _require(
        sha256_file(reference_assembly) == s603["assembly"]["audio_sha256"],
        "s603_assembly_hash_drift",
    )
    _require(
        sha256_file(candidate_assembly) == render_receipt["assembly"]["sha256"],
        "s617_assembly_hash_drift",
    )
    assembly = compare_pcm_wav(reference_assembly, candidate_assembly)
    _require(assembly["format_equal"], "assembly_format_drift")
    _require(assembly["pcm_sha256_equal"], "assembly_pcm_drift")
    _require(
        s603["assembly"]["gap_seconds"]
        == render_receipt["assembly"]["gap_seconds"]
        == [1.0, 1.0],
        "assembly_gap_drift",
    )

    return {
        "schema": "agent_bridge.story_bounded_render_acceptance_review.v1",
        "status": "story_bounded_render_acceptance_verified",
        "decision": "accepted_by_exact_pcm_continuity_without_new_playback",
        "evidence": {
            "s603_owner_accepted_receipt_path": str(S603_RECEIPT),
            "s603_owner_accepted_receipt_sha256": sha256_file(s603_path),
            "s617_execution_result_path": str(S617_RESULT),
            "s617_execution_result_sha256": sha256_file(s617_path),
            "s617_render_receipt_path": str(render_receipt_path),
            "s617_render_receipt_sha256": sha256_file(render_receipt_path),
            "preflight_sha256": render_receipt["preflight_sha256"],
        },
        "comparison": {
            "segment_count": len(segment_comparisons),
            "segments": segment_comparisons,
            "assembly": assembly,
            "gap_seconds": [1.0, 1.0],
            "all_segment_files_exact": all(
                row["file_sha256_equal"] for row in segment_comparisons
            ),
            "all_segment_pcm_exact": all(
                row["pcm_sha256_equal"] for row in segment_comparisons
            ),
            "all_pcm_exact": all(
                row["pcm_sha256_equal"] for row in segment_comparisons
            )
            and assembly["pcm_sha256_equal"],
        },
        "machine_acceptance": {
            "all_segments_natural_eos": all(
                row["natural_eos"] for row in render_receipt["segments"]
            ),
            "assembly_non_silent": render_receipt["assembly"]["non_silent"],
            "duration_seconds": render_receipt["assembly"]["duration_seconds"],
            "sample_rate_hz": assembly["sample_rate_hz"],
            "channels": assembly["channels"],
            "sample_width_bytes": assembly["sample_width_bytes"],
            "frames": assembly["frames"],
        },
        "human_acceptance": {
            "source_stage": "s603_owner_accepted_playback",
            "prior_owner_playback_completed": True,
            "prior_owner_acceptance_verified": True,
            "prior_owner_feedback_sha256": canonical_sha256(owner_feedback),
            "inheritance_basis": "exact_pcm_sample_sequence",
            "current_playback_required": False,
            "current_playback_performed": False,
            "blind_comparison_claimed": False,
        },
        "boundaries": {
            "review_read_only": True,
            "container_bytes_and_pcm_samples_distinguished": True,
            "sensitive_receipt_fields_copied": False,
            "secret_or_nonce_accessed": False,
            "new_owner_feedback_claimed": False,
            "story_command_runtime_admitted": False,
        },
        "runtime_effects": {
            "read_secret": False,
            "consumed_nonce": False,
            "loaded_model": False,
            "executed_onnx": False,
            "rendered_audio": False,
            "played_audio": False,
            "recorded_audio": False,
            "wrote_cache": False,
            "wrote_memory": False,
        },
        "claims": {
            "s617_machine_gate_reverified": True,
            "s617_audio_content_matches_owner_accepted_s603": True,
            "assembly_container_bytes_differ": not assembly["file_sha256_equal"],
            "assembly_pcm_samples_identical": assembly["pcm_sha256_equal"],
            "human_acceptance_continuity_verified": True,
            "new_playback_unnecessary": True,
            "blind_audition_performed": False,
            "story_command_render_runtime_enabled": False,
        },
        "next_gate": "story_command_render_runtime_admission_review",
    }
