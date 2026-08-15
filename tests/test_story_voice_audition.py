from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_voice_audition.py"
MATRIX_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_backend_capabilities.json"
)
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_audition.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location("story_voice_audition", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backend_matrix_is_explicit_and_blocks_unknown_license() -> None:
    audition = load_module()
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

    assert audition.validate_backend_matrix(matrix) == []
    sherpa = next(
        row for row in matrix["backends"] if row["backend_id"] == "sherpa-aishell3"
    )
    assert sherpa["speaker_count"] == 174
    assert sherpa["speaker_metadata"]["gender_inference_allowed"] is False
    assert sherpa["license"]["status"] == "unverified"
    assert sherpa["promotion"]["production_eligible"] is False
    assert sherpa["runtime"]["default_enabled"] is False


def test_audition_plan_is_blinded_deterministic_and_version_bound() -> None:
    audition = load_module()
    request = {
        "scene_id": "scene_story_zh_s5",
        "backend_id": "sherpa-aishell3",
        "model_artifact_sha256": "a" * 64,
        "voice_profile_version": 1,
        "roles": [
            {"role_id": "narrator", "speaker_id": 10},
            {"role_id": "character_lin", "speaker_id": 33},
            {"role_id": "character_su", "speaker_id": 99},
        ],
        "reference_text": "夜色落在旧车站，钥匙仍藏在时钟下面。",
    }

    first = audition.build_audition_plan(request)
    second = audition.build_audition_plan(request)

    assert first == second
    assert first["status"] == "audition_plan_ready_no_audio"
    assert [row["blind_label"] for row in first["items"]] == ["voice_a", "voice_b", "voice_c"]
    assert {row["speaker_id"] for row in first["items"]} == {10, 33, 99}
    assert all(row["text"] == request["reference_text"] for row in first["items"])
    assert first["runtime_effects"] == {
        "downloads_models": False,
        "renders_audio": False,
        "plays_audio": False,
        "writes_memory": False,
    }


def test_audition_plan_rejects_duplicate_speaker_or_missing_required_role() -> None:
    audition = load_module()
    base = {
        "scene_id": "scene_story_zh_s5",
        "backend_id": "sherpa-aishell3",
        "model_artifact_sha256": "a" * 64,
        "voice_profile_version": 1,
        "reference_text": "测试文本。",
    }
    duplicate = dict(
        base,
        roles=[
            {"role_id": "narrator", "speaker_id": 10},
            {"role_id": "character_lin", "speaker_id": 10},
            {"role_id": "character_su", "speaker_id": 99},
        ],
    )
    with pytest.raises(ValueError, match="speaker_id_must_be_distinct"):
        audition.build_audition_plan(duplicate)

    missing = dict(
        base,
        roles=[
            {"role_id": "narrator", "speaker_id": 10},
            {"role_id": "character_lin", "speaker_id": 33},
        ],
    )
    with pytest.raises(ValueError, match="narrator_and_two_characters_required"):
        audition.build_audition_plan(missing)


def passing_review() -> dict:
    return {
        "plan_id": "audition_plan_example",
        "model_artifact_sha256": "a" * 64,
        "items": [
            {
                "blind_label": "voice_a",
                "role_id": "narrator",
                "speaker_id": 10,
                "artifact_sha256": "1" * 64,
                "human": {
                    "audible": True,
                    "intelligibility": 4,
                    "naturalness": 4,
                    "role_fit": 4,
                },
                "asr": {"reference": "旧车站", "transcript": "旧车站"},
            },
            {
                "blind_label": "voice_b",
                "role_id": "character_lin",
                "speaker_id": 33,
                "artifact_sha256": "2" * 64,
                "human": {
                    "audible": True,
                    "intelligibility": 4,
                    "naturalness": 4,
                    "role_fit": 4,
                },
                "asr": {"reference": "旧车站", "transcript": "旧车站"},
            },
            {
                "blind_label": "voice_c",
                "role_id": "character_su",
                "speaker_id": 99,
                "artifact_sha256": "3" * 64,
                "human": {
                    "audible": True,
                    "intelligibility": 4,
                    "naturalness": 4,
                    "role_fit": 4,
                },
                "asr": {"reference": "旧车站", "transcript": "旧车站"},
            },
        ],
        "pairwise_distinguishable": [
            ["voice_a", "voice_b"],
            ["voice_a", "voice_c"],
            ["voice_b", "voice_c"],
        ],
        "owner_confirmed": True,
        "real_person_voice_clone": False,
    }


def test_review_fails_closed_without_owner_or_with_weak_intelligibility() -> None:
    audition = load_module()
    review = passing_review()
    review["owner_confirmed"] = False
    result = audition.evaluate_review(review)
    assert result["status"] == "review_incomplete"
    assert "owner_confirmation_missing" in result["blockers"]

    review = passing_review()
    review["items"][1]["asr"]["transcript"] = "完全不同"
    result = audition.evaluate_review(review)
    assert result["status"] == "review_incomplete"
    assert "asr_cer_above_threshold:voice_b" in result["blockers"]


def test_review_accepts_narrator_plus_two_distinct_verified_voices() -> None:
    audition = load_module()
    result = audition.evaluate_review(passing_review())

    assert result["status"] == "story_chinese_multispeaker_verified"
    assert result["verified_role_count"] == 3
    assert result["all_pairs_distinguishable"] is True
    assert result["max_cer"] == 0.0
    assert result["writes_canon"] is False


def test_audition_schema_accepts_plan_and_rejects_runtime_effects() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    audition = load_module()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    plan = audition.build_audition_plan(
        {
            "scene_id": "scene_story_zh_s5",
            "backend_id": "sherpa-aishell3",
            "model_artifact_sha256": "a" * 64,
            "voice_profile_version": 1,
            "roles": [
                {"role_id": "narrator", "speaker_id": 10},
                {"role_id": "character_lin", "speaker_id": 33},
                {"role_id": "character_su", "speaker_id": 99},
            ],
            "reference_text": "测试文本。",
        }
    )
    jsonschema.validate(plan, schema)

    plan["runtime_effects"]["plays_audio"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(plan, schema)
