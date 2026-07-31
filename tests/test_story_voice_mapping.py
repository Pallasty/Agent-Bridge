from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_voice_mapping.py"
SCHEMA_PATH = (
    ROOT / "docs" / "design" / "voice-scene" / "story_voice_mapping.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_mapping", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan() -> dict:
    return {
        "source": {"sha256": "a" * 64},
        "cast_registry": [
            {
                "speaker_id": "speaker_narrator",
                "kind": "narrator",
                "display_name": "旁白",
                "voice_profile": {"version": 1},
            },
            {
                "speaker_id": "speaker_lin",
                "kind": "character",
                "display_name": "林默",
                "voice_profile": {"version": 1},
            },
            {
                "speaker_id": "speaker_su",
                "kind": "character",
                "display_name": "苏岚",
                "voice_profile": {"version": 1},
            },
        ],
    }


def assignments() -> dict:
    return {
        "speaker_narrator": {
            "qwen_speaker": "Vivian",
            "style_instruction": "温柔、清晰、克制地叙述。",
        },
        "speaker_lin": {
            "qwen_speaker": "Dylan",
            "style_instruction": "青年声线，冷静而坚定。",
        },
        "speaker_su": {
            "qwen_speaker": "Serena",
            "style_instruction": "温暖但带有警觉。",
        },
    }


def test_mapping_is_complete_stable_and_versioned() -> None:
    module = load_module()
    first = module.build_mapping(
        plan(), assignments(), approved_qwen_speakers={"Vivian"}
    )
    second = module.build_mapping(
        plan(), assignments(), approved_qwen_speakers={"Vivian"}
    )

    assert first == second
    assert first["status"] == "mapping_reviewable_auditions_pending"
    assert len(first["mapping_sha256"]) == 64
    assert [row["voice_profile_version"] for row in first["roles"]] == [2, 2, 2]


def test_only_owner_accepted_speaker_is_render_authorized() -> None:
    result = load_module().build_mapping(
        plan(), assignments(), approved_qwen_speakers={"Vivian"}
    )
    by_id = {row["speaker_id"]: row for row in result["roles"]}

    assert by_id["speaker_narrator"]["render_authorized"] is True
    assert by_id["speaker_lin"]["render_authorized"] is False
    assert by_id["speaker_su"]["render_authorized"] is False
    assert result["chapter_render_ready"] is False
    assert result["pending_auditions"] == ["Dylan", "Serena"]


def test_named_roles_require_explicit_unique_assignments() -> None:
    missing = assignments()
    del missing["speaker_su"]
    with pytest.raises(ValueError, match="missing voice assignment"):
        load_module().build_mapping(
            plan(), missing, approved_qwen_speakers={"Vivian"}
        )

    duplicate = assignments()
    duplicate["speaker_su"]["qwen_speaker"] = "Dylan"
    with pytest.raises(ValueError, match="qwen speaker reused"):
        load_module().build_mapping(
            plan(), duplicate, approved_qwen_speakers={"Vivian"}
        )


def test_unknown_qwen_speaker_and_unbounded_style_fail_closed() -> None:
    unknown = assignments()
    unknown["speaker_lin"]["qwen_speaker"] = "Invented"
    with pytest.raises(ValueError, match="unsupported Qwen speaker"):
        load_module().build_mapping(
            plan(), unknown, approved_qwen_speakers={"Vivian"}
        )

    verbose = assignments()
    verbose["speaker_lin"]["style_instruction"] = "太" * 121
    with pytest.raises(ValueError, match="style instruction"):
        load_module().build_mapping(
            plan(), verbose, approved_qwen_speakers={"Vivian"}
        )


def test_repository_shape_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    result = load_module().build_mapping(
        plan(), assignments(), approved_qwen_speakers={"Vivian"}
    )
    jsonschema.validate(result, json.loads(SCHEMA_PATH.read_text()))
