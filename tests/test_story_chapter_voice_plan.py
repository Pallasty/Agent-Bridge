from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_chapter_voice_plan.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_chapter_voice_plan", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def story_plan() -> dict:
    return {
        "status": "story_plan_reviewable",
        "source": {"sha256": "1" * 64},
        "chapters": [
            {
                "chapter_id": "chapter_1",
                "selected": True,
                "source_span": {"line_start": 1, "line_end": 5},
            },
            {
                "chapter_id": "chapter_2",
                "selected": True,
                "source_span": {"line_start": 6, "line_end": 9},
            },
        ],
        "voice_scene": {
            "timeline": [
                {
                    "event_id": "event_1",
                    "sequence": 1,
                    "source_ref": {"locator": "line=2;chars=5:10"},
                    "utterance": {"speaker_id": "narrator", "text": "雨声渐近。"},
                },
                {
                    "event_id": "event_2",
                    "sequence": 2,
                    "source_ref": {"locator": "line=4;chars=11:20"},
                    "utterance": {
                        "speaker_id": "lin",
                        "text": "林默说：“快走。”",
                    },
                },
                {
                    "event_id": "event_3",
                    "sequence": 3,
                    "source_ref": {"locator": "line=5;chars=21:30"},
                    "utterance": {"speaker_id": "su", "text": "等等。"},
                },
                {
                    "event_id": "event_4",
                    "sequence": 4,
                    "source_ref": {"locator": "line=7;chars=31:40"},
                    "utterance": {"speaker_id": "narrator", "text": "门开了。"},
                },
            ]
        },
    }


def mapping() -> dict:
    roles = []
    for speaker_id, name, voice in (
        ("narrator", "旁白", "Vivian"),
        ("lin", "林默", "Dylan"),
        ("su", "苏岚", "Serena"),
    ):
        roles.append(
            {
                "speaker_id": speaker_id,
                "display_name": name,
                "role_kind": "narrator" if speaker_id == "narrator" else "character",
                "qwen_speaker": voice,
                "style_instruction": f"{name}风格。",
                "voice_profile_version": 2,
            }
        )
    return {
        "source_sha256": "1" * 64,
        "mapping_sha256": "2" * 64,
        "roles": roles,
    }


def role_acceptance() -> dict:
    return {
        "mapping_sha256": "2" * 64,
        "claims": {
            "owner_accepted_both": True,
            "voices_distinguishable": True,
            "chapter_render_ready": True,
        },
    }


def pacing_acceptance(*, accepted: bool = True) -> dict:
    return {
        "policy": {
            "same_paragraph": 0.65,
            "speaker_turn": 1.0,
            "paragraph_break": 1.4,
            "scene_break": 2.2,
            "selection_authority": "explicit_structural_label",
            "freeform_model_guessing": False,
        },
        "claims": {"owner_pacing_accepted": accepted},
    }


def test_chapter_plan_derives_structural_transitions_deterministically() -> None:
    module = load_module()

    result = module.build_chapter_voice_plan(
        story_plan(), mapping(), role_acceptance(), pacing_acceptance()
    )

    assert result["status"] == "chapter_voice_plan_reviewable"
    assert [row["text"] for row in result["segments"]] == [
        "雨声渐近。",
        "林默说。",
        "快走。",
        "等等。",
        "门开了。",
    ]
    assert [row["qwen_speaker"] for row in result["segments"]] == [
        "Vivian",
        "Vivian",
        "Dylan",
        "Serena",
        "Vivian",
    ]
    assert [row["transition_after"] for row in result["segments"][:-1]] == [
        "paragraph_break",
        "speaker_turn",
        "speaker_turn",
        "scene_break",
    ]
    assert [row["pause_after_seconds"] for row in result["segments"][:-1]] == [
        1.4,
        1.0,
        1.0,
        2.2,
    ]
    assert result["segments"][1]["source_span"] == {
        "line": 4,
        "char_start": 11,
        "char_end": 15,
        "source_text": "林默说：",
        "normalization": "terminal_colon_to_full_stop",
    }
    assert result["segments"][2]["source_span"] == {
        "line": 4,
        "char_start": 16,
        "char_end": 19,
        "source_text": "快走。",
        "normalization": "none",
    }
    assert "transition_after" not in result["segments"][-1]
    assert result["runtime_effects"] == {
        "loaded_model": False,
        "rendered_audio": False,
        "played_audio": False,
        "registered_story_command": False,
    }
    assert result["chapter_render_ready"] is True
    assert result["review_queue"] == []
    assert result["next_gate"] == "bounded_first_chapter_qwen_render"


def test_chapter_plan_fails_closed_on_unaccepted_pacing_and_provenance() -> None:
    module = load_module()
    with pytest.raises(ValueError, match="pacing policy not accepted"):
        module.build_chapter_voice_plan(
            story_plan(), mapping(), role_acceptance(), pacing_acceptance(accepted=False)
        )

    changed = mapping()
    changed["source_sha256"] = "9" * 64
    with pytest.raises(ValueError, match="source SHA-256 mismatch"):
        module.build_chapter_voice_plan(
            story_plan(), changed, role_acceptance(), pacing_acceptance()
        )


def test_chapter_plan_rejects_missing_role_mapping() -> None:
    changed = mapping()
    changed["roles"] = changed["roles"][:-1]

    with pytest.raises(ValueError, match="voice mapping missing"):
        load_module().build_chapter_voice_plan(
            story_plan(), changed, role_acceptance(), pacing_acceptance()
        )


def test_unbalanced_attributed_dialogue_remains_review_blocked() -> None:
    changed = story_plan()
    changed["voice_scene"]["timeline"][1]["utterance"]["text"] = "林默说：“快走。"

    result = load_module().build_chapter_voice_plan(
        changed, mapping(), role_acceptance(), pacing_acceptance()
    )

    assert result["chapter_render_ready"] is False
    assert result["review_queue"] == [
        {
            "event_id": "event_2",
            "reason": "attributed_dialogue_split_ambiguous",
        }
    ]


def test_single_ascii_quote_pair_is_source_grounded() -> None:
    changed = story_plan()
    changed["voice_scene"]["timeline"][1]["utterance"]["text"] = '林默说:"快走。"'

    result = load_module().build_chapter_voice_plan(
        changed, mapping(), role_acceptance(), pacing_acceptance()
    )

    derived = [
        row for row in result["segments"] if row["source_event_id"] == "event_2"
    ]
    assert [row["text"] for row in derived] == ["林默说。", "快走。"]
    assert result["review_queue"] == []
