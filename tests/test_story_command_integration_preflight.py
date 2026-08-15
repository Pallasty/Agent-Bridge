from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_command_integration_preflight.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
SCHEMA_PATH = VOICE_SCENE / "story_command_integration_preflight.schema.json"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_command_integration_preflight", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(name: str) -> dict:
    return json.loads((VOICE_SCENE / name).read_text(encoding="utf-8"))


def inputs() -> dict:
    return {
        "voice_plan": load_json("s5zc_source_grounded_utterance_plan_receipt.json"),
        "mapping": load_json("s5x_story_voice_mapping_receipt.json"),
        "role_acceptance": load_json("s5y_character_voice_audition_receipt.json"),
        "continuity_acceptance": load_json(
            "s5ze_cross_chapter_continuity_receipt.json"
        ),
    }


def test_chapter_preflight_binds_command_provenance_and_cache_keys() -> None:
    module = load_module()
    story = VOICE_SCENE / "fixtures" / "story_s1.md"

    result = module.build_story_command_preflight(
        f'/story "{story}" chapter 2', **inputs()
    )

    assert result["status"] == "story_command_integration_preflight_reviewable"
    assert result["command"]["chapter_number"] == 2
    assert result["command"]["source_path"] == str(story.resolve())
    assert result["selection"]["selected_segments"] == 3
    assert result["selection"]["preceding_scene_gap_seconds"] == 2.2
    assert len(result["render_requests"]) == 3
    assert len({row["cache_key"] for row in result["render_requests"]}) == 3
    assert all(len(row["cache_key"]) == 64 for row in result["render_requests"])
    assert result["runtime_effects"] == {
        "registered_story_command": False,
        "loaded_model": False,
        "executed_onnx": False,
        "rendered_audio": False,
        "played_audio": False,
        "wrote_memory": False,
        "wrote_cache": False,
    }
    assert result["execution_authorized"] is False


def test_from_start_selects_first_chapter() -> None:
    module = load_module()
    story = VOICE_SCENE / "fixtures" / "story_s1.md"

    result = module.build_story_command_preflight(
        f'/story "{story}" from-start', **inputs()
    )

    assert result["command"]["chapter_number"] == 1
    assert result["selection"]["selected_segments"] == 4
    assert result["selection"]["preceding_scene_gap_seconds"] is None


def test_preflight_fails_closed_on_unaccepted_or_drifted_evidence() -> None:
    module = load_module()
    story = VOICE_SCENE / "fixtures" / "story_s1.md"
    values = inputs()

    unaccepted = copy.deepcopy(values["continuity_acceptance"])
    unaccepted["claims"]["owner_accepted"] = False
    with pytest.raises(ValueError, match="cross-chapter continuity not accepted"):
        module.build_story_command_preflight(
            f'/story "{story}" chapter 2',
            **{**values, "continuity_acceptance": unaccepted},
        )

    drifted = copy.deepcopy(values["voice_plan"])
    drifted["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="story source SHA-256 mismatch"):
        module.build_story_command_preflight(
            f'/story "{story}" chapter 2', **{**values, "voice_plan": drifted}
        )


def test_preflight_rejects_runtime_flags_and_unavailable_chapter() -> None:
    module = load_module()
    story = VOICE_SCENE / "fixtures" / "story_s1.md"

    with pytest.raises(ValueError, match="runtime_option_forbidden"):
        module.build_story_command_preflight(
            f'/story "{story}" chapter 2 --play', **inputs()
        )
    with pytest.raises(ValueError, match="story_chapter_not_found"):
        module.build_story_command_preflight(
            f'/story "{story}" chapter 3', **inputs()
        )


def test_cache_key_changes_with_voice_or_model_provenance() -> None:
    module = load_module()
    base = {
        "source_sha256": "1" * 64,
        "voice_plan_sha256": "2" * 64,
        "event_id": "event_1",
        "text": "门开了。",
        "qwen_speaker": "Vivian",
        "style_instruction": "温柔。",
        "voice_profile_version": 2,
        "model_inference_sha256": "3" * 64,
    }

    original = module.segment_cache_key(**base)
    assert original != module.segment_cache_key(
        **{**base, "style_instruction": "冷静。"}
    )
    assert original != module.segment_cache_key(
        **{**base, "model_inference_sha256": "4" * 64}
    )


def test_real_preflight_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    module = load_module()
    story = VOICE_SCENE / "fixtures" / "story_s1.md"
    result = module.build_story_command_preflight(
        f'/story "{story}" chapter 2', **inputs()
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(result)) == []
