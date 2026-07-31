from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_bounded_chapter_render.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_bounded_chapter_render", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def voice_plan() -> dict:
    segments = []
    rows = [
        ("event_1", "Vivian", "雨声渐近。", "same_paragraph", 0.65),
        ("event_2.narration", "Vivian", "林默说。", "speaker_turn", 1.0),
        ("event_2.dialogue", "Dylan", "快走。", "speaker_turn", 1.0),
        ("event_3", "Vivian", "门关上了。", "scene_break", 2.2),
        ("event_4", "Serena", "我听见了。", None, None),
    ]
    for index, (event_id, speaker, text, transition, pause) in enumerate(rows):
        row = {
            "segment_index": index,
            "event_id": event_id,
            "qwen_speaker": speaker,
            "style_instruction": f"{speaker} style",
            "text": text,
        }
        if transition:
            row["transition_after"] = transition
            row["pause_after_seconds"] = pause
        segments.append(row)
    return {
        "status": "chapter_voice_plan_reviewable",
        "chapter_render_ready": True,
        "plan_sha256": "1" * 64,
        "segments": segments,
    }


def test_first_chapter_requests_stop_at_scene_break_without_trailing_pause() -> None:
    result = load_module().build_first_chapter_requests(voice_plan())

    assert [row["event_id"] for row in result["requests"]] == [
        "event_1",
        "event_2.narration",
        "event_2.dialogue",
        "event_3",
    ]
    assert result["assembly_gap_seconds"] == [0.65, 1.0, 1.0]
    assert all(row["voice_plan_sha256"] == "1" * 64 for row in result["requests"])
    assert result["excluded_later_segments"] == 1


def test_first_chapter_requests_require_review_ready_plan() -> None:
    blocked = voice_plan()
    blocked["chapter_render_ready"] = False
    with pytest.raises(ValueError, match="chapter voice plan not render ready"):
        load_module().build_first_chapter_requests(blocked)


def evidence(requests: list[dict]) -> list[dict]:
    return [
        {
            "event_id": row["event_id"],
            "text": row["text"],
            "qwen_speaker": row["qwen_speaker"],
            "natural_eos": True,
            "generated_codec_frames": 20,
            "frame_cap": 100,
            "audio_path": f"/{row['segment_index']}.wav",
            "audio_sha256": str(row["segment_index"]) * 64,
            "wav_machine_valid": True,
            "asr_transcript": row["text"].replace("。", ""),
        }
        for row in requests
    ]


def test_segment_evidence_requires_natural_eos_wav_and_normalized_exact_asr() -> None:
    module = load_module()
    requests = module.build_first_chapter_requests(voice_plan())["requests"]

    hash_reader = lambda path: path.stem * 64
    result = module.verify_segment_evidence(
        requests, evidence(requests), audio_hash_reader=hash_reader
    )

    assert result["status"] == "all_segments_machine_verified"
    assert result["segment_count"] == 4
    assert result["normalized_asr_exact"] is True

    truncated = evidence(requests)
    truncated[1]["natural_eos"] = False
    with pytest.raises(ValueError, match="natural EOS missing"):
        module.verify_segment_evidence(
            requests, truncated, audio_hash_reader=hash_reader
        )

    wrong_asr = evidence(requests)
    wrong_asr[2]["asr_transcript"] = "错误内容"
    with pytest.raises(ValueError, match="ASR mismatch"):
        module.verify_segment_evidence(
            requests, wrong_asr, audio_hash_reader=hash_reader
        )

    wrong_hash = evidence(requests)
    with pytest.raises(ValueError, match="audio hash mismatch"):
        module.verify_segment_evidence(
            requests,
            wrong_hash,
            audio_hash_reader=lambda _path: "f" * 64,
        )


def test_asr_allows_only_explicit_named_entity_homophones() -> None:
    module = load_module()
    requests = module.build_first_chapter_requests(voice_plan())["requests"]
    requests[0]["text"] = "林默走进车站。"
    observed = evidence(requests)
    observed[0]["text"] = "林默走进车站。"
    observed[0]["asr_transcript"] = "林墨走进车站"

    result = module.verify_segment_evidence(
        requests,
        observed,
        named_entity_asr_variants={"林默": ["林墨", "林末"]},
        audio_hash_reader=lambda path: path.stem * 64,
    )

    assert result["normalized_asr_exact"] is False
    assert result["named_entity_pronunciation_equivalent"] is True

    observed[0]["asr_transcript"] = "林墨离开车站"
    with pytest.raises(ValueError, match="ASR mismatch"):
        module.verify_segment_evidence(
            requests,
            observed,
            named_entity_asr_variants={"林默": ["林墨", "林末"]},
            audio_hash_reader=lambda path: path.stem * 64,
        )
