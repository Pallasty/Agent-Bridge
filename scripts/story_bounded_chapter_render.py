#!/usr/bin/env python3
"""Plan and verify a fail-closed first-chapter Qwen render."""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any, Callable


def _normalized_speech(text: str) -> str:
    return "".join(
        character
        for character in text
        if not character.isspace()
        and not unicodedata.category(character).startswith("P")
    ).casefold()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonicalize_named_entities(
    text: str, variants: dict[str, list[str]]
) -> str:
    normalized = _normalized_speech(text)
    seen: set[str] = set()
    replacements = []
    for index, (entity, alternatives) in enumerate(variants.items()):
        forms = {_normalized_speech(entity), *map(_normalized_speech, alternatives)}
        if "" in forms or seen & forms:
            raise ValueError("named entity ASR variants invalid")
        seen.update(forms)
        token = f"namedentitytoken{index}"
        replacements.extend((form, token) for form in forms)
    for form, token in sorted(replacements, key=lambda row: len(row[0]), reverse=True):
        normalized = normalized.replace(form, token)
    return normalized


def build_chapter_requests(
    plan: dict[str, Any], *, chapter_number: int
) -> dict[str, Any]:
    if (
        plan.get("status") != "chapter_voice_plan_reviewable"
        or plan.get("chapter_render_ready") is not True
    ):
        raise ValueError("chapter voice plan not render ready")
    all_segments = plan.get("segments", [])
    if not all_segments:
        raise ValueError("chapter voice plan empty")

    chapters: list[list[dict[str, Any]]] = []
    scene_gaps: list[float | None] = [None]
    current = []
    for segment in all_segments:
        current.append(segment)
        if segment.get("transition_after") == "scene_break":
            chapters.append(current)
            current = []
            scene_gaps.append(segment["pause_after_seconds"])
    if current:
        chapters.append(current)
    if chapter_number < 1 or chapter_number > len(chapters):
        raise ValueError("chapter number out of range")
    selected = chapters[chapter_number - 1]
    earlier_count = sum(len(chapter) for chapter in chapters[: chapter_number - 1])
    later_count = sum(len(chapter) for chapter in chapters[chapter_number:])

    requests = []
    for index, segment in enumerate(selected):
        requests.append(
            {
                "segment_index": index,
                "event_id": segment["event_id"],
                "voice_plan_sha256": plan["plan_sha256"],
                "text": segment["text"],
                "qwen_speaker": segment["qwen_speaker"],
                "style_instruction": segment["style_instruction"],
                "language": "Chinese",
                "frame_cap": 100,
            }
        )
    gaps = [row["pause_after_seconds"] for row in selected[:-1]]
    return {
        "schema": "agent_bridge.story_bounded_chapter_requests.v1",
        "status": "chapter_requests_reviewable",
        "chapter_number": chapter_number,
        "voice_plan_sha256": plan["plan_sha256"],
        "requests": requests,
        "assembly_gap_seconds": gaps,
        "preceding_scene_gap_seconds": scene_gaps[chapter_number - 1],
        "excluded_earlier_segments": earlier_count,
        "excluded_later_segments": later_count,
        "runtime_effects": {
            "loaded_model": False,
            "rendered_audio": False,
            "played_audio": False,
        },
    }


def build_first_chapter_requests(plan: dict[str, Any]) -> dict[str, Any]:
    return build_chapter_requests(plan, chapter_number=1)


def verify_segment_evidence(
    requests: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    *,
    named_entity_asr_variants: dict[str, list[str]] | None = None,
    audio_hash_reader: Callable[[Path], str] = _sha256_file,
) -> dict[str, Any]:
    if len(requests) != len(evidence):
        raise ValueError("segment evidence count mismatch")
    verified = []
    exact_results = []
    variants = named_entity_asr_variants or {}
    for request, observed in zip(requests, evidence, strict=True):
        event_id = request["event_id"]
        for field in ("event_id", "text", "qwen_speaker"):
            if observed.get(field) != request[field]:
                raise ValueError(f"segment provenance mismatch:{event_id}:{field}")
        if observed.get("natural_eos") is not True or not (
            0 < observed.get("generated_codec_frames", 0)
            < observed.get("frame_cap", 0)
        ):
            raise ValueError(f"natural EOS missing:{event_id}")
        if observed.get("wav_machine_valid") is not True:
            raise ValueError(f"WAV machine gate failed:{event_id}")
        claimed_hash = observed.get("audio_sha256", "")
        actual_hash = audio_hash_reader(Path(observed.get("audio_path", "")))
        if (
            len(claimed_hash) != 64
            or any(character not in "0123456789abcdef" for character in claimed_hash)
            or claimed_hash != actual_hash
        ):
            raise ValueError(f"audio hash mismatch:{event_id}")
        transcript = observed.get("asr_transcript", "")
        exact = _normalized_speech(transcript) == _normalized_speech(request["text"])
        if not exact and _canonicalize_named_entities(
            transcript, variants
        ) != _canonicalize_named_entities(request["text"], variants):
            raise ValueError(f"ASR mismatch:{event_id}")
        exact_results.append(exact)
        verified.append(observed)
    all_exact = all(exact_results)
    return {
        "status": "all_segments_machine_verified",
        "segment_count": len(verified),
        "normalized_asr_exact": all_exact,
        "named_entity_pronunciation_equivalent": not all_exact,
        "named_entity_asr_variants": variants,
        "segments": verified,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_first_chapter_requests(json.loads(args.voice_plan.read_text()))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
