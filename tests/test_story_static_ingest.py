from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_static_ingest.py"
CONTRACT_MODULE_PATH = ROOT / "scripts" / "voice_scene_contract.py"
SCHEMA_PATH = ROOT / "docs" / "design" / "voice-scene" / "story_plan.schema.json"


def load_ingest_module():
    spec = importlib.util.spec_from_file_location("story_static_ingest", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_contract_module():
    spec = importlib.util.spec_from_file_location(
        "voice_scene_contract_for_story", CONTRACT_MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_story(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# 第一章 夜雨",
                "",
                "林默（又名阿默）走进车站。",
                "林默对苏岚说：“我们得马上离开。”",
                "林默是苏岚的朋友。",
                "",
                "# 第二章 回声",
                "",
                "苏岚回答：“我听见钟声了。”",
                "苏岚打开了旧木门。",
            ]
        ),
        encoding="utf-8",
    )


def test_story_command_parses_quoted_path_and_start_selector() -> None:
    ingest = load_ingest_module()

    command = ingest.parse_story_command('/story "/tmp/长篇 小说.md" chapter 12')

    assert command == {
        "path": "/tmp/长篇 小说.md",
        "start": {"kind": "chapter", "chapter": 12},
        "dry_run": True,
    }
    assert ingest.parse_story_command("/story book.txt from-start")["start"] == {
        "kind": "from_start"
    }


def test_story_command_rejects_runtime_and_unsupported_source() -> None:
    ingest = load_ingest_module()

    with pytest.raises(ValueError, match="unsupported_story_source"):
        ingest.parse_story_command("/story book.epub from-start")
    with pytest.raises(ValueError, match="runtime_option_forbidden"):
        ingest.parse_story_command("/story book.txt from-start --play")


def test_repeated_ingest_is_byte_for_byte_deterministic(tmp_path: Path) -> None:
    ingest = load_ingest_module()
    story = tmp_path / "story.md"
    write_story(story)

    first = ingest.ingest_story(story, start={"kind": "from_start"})
    second = ingest.ingest_story(story, start={"kind": "from_start"})

    assert first == second
    assert first["status"] == "story_plan_reviewable"
    assert first["source"]["sha256"] == ingest.sha256_bytes(story.read_bytes())
    assert first["runtime_boundary"] == {
        "emits_audio": False,
        "records_audio": False,
        "writes_memory": False,
        "writes_forum": False,
        "mutates_runtime": False,
        "downloads_models": False,
    }


def test_chapter_selection_preserves_exact_source_spans(tmp_path: Path) -> None:
    ingest = load_ingest_module()
    story = tmp_path / "story.md"
    write_story(story)

    plan = ingest.ingest_story(
        story,
        start={"kind": "chapter", "chapter": 2},
    )

    assert [chapter["ordinal"] for chapter in plan["chapters"]] == [1, 2]
    assert plan["selection"]["first_chapter"] == 2
    selected = [chapter for chapter in plan["chapters"] if chapter["selected"]]
    assert [chapter["ordinal"] for chapter in selected] == [2]
    span = selected[0]["source_span"]
    source_text = story.read_text(encoding="utf-8")
    assert source_text[span["char_start"] : span["char_end"]].startswith(
        "# 第二章 回声"
    )
    assert span["line_start"] == 7
    assert span["line_end"] == 10


def test_cast_registry_merges_aliases_and_keeps_versioned_voice_stable(
    tmp_path: Path,
) -> None:
    ingest = load_ingest_module()
    story = tmp_path / "story.md"
    write_story(story)

    plan = ingest.ingest_story(story, start={"kind": "from_start"})
    cast = {
        character["display_name"]: character for character in plan["cast_registry"]
    }

    assert set(cast) == {"旁白", "林默", "苏岚"}
    assert cast["林默"]["aliases"] == ["林默", "阿默"]
    assert cast["林默"]["identity_status"] == "needs_review"
    lin_voice = cast["林默"]["voice_profile"]
    assert lin_voice["version"] == 1
    assert lin_voice["backend"] == "unassigned"
    assert lin_voice["voice"] == "unassigned"
    assert "gender" not in lin_voice
    assert lin_voice == ingest.ingest_story(
        story, start={"kind": "chapter", "chapter": 2}
    )["cast_registry"][1]["voice_profile"]


def test_relationships_events_and_uncertain_emotion_are_review_candidates(
    tmp_path: Path,
) -> None:
    ingest = load_ingest_module()
    story = tmp_path / "story.md"
    write_story(story)

    plan = ingest.ingest_story(story, start={"kind": "from_start"})

    assert any(
        relation["subject"] == "林默"
        and relation["predicate"] == "朋友"
        and relation["object"] == "苏岚"
        for relation in plan["relationships"]
    )
    assert any(event["summary"] == "苏岚打开了旧木门。" for event in plan["events"])
    assert all(item["status"] == "needs_review" for item in plan["review_queue"])
    assert {"character_identity", "voice_audition", "chapter_boundary"} <= {
        item["kind"] for item in plan["review_queue"]
    }


def test_legacy_import_rejects_placeholder_verified_and_live_arguments() -> None:
    ingest = load_ingest_module()

    errors = ingest.validate_legacy_import(
        {
            "verify_status": "verified",
            "output_file": "placeholder.wav",
            "tool_args": {"play": True, "backend": "ab-tts"},
        }
    )

    assert "legacy_placeholder_verified_forbidden" in errors
    assert "legacy_live_argument_forbidden:play" in errors
    assert "legacy_live_backend_forbidden:ab-tts" in errors


def test_cli_prints_plan_without_writing_an_output_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest = load_ingest_module()
    story = tmp_path / "story.txt"
    story.write_text("第一章 起点\n\n林默说：“出发。”", encoding="utf-8")

    exit_code = ingest.main(
        ["/story", str(story), "from-start", "--pretty"]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "story_plan_reviewable"
    assert list(tmp_path.iterdir()) == [story]


def test_generated_plan_and_embedded_voice_scene_validate(tmp_path: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    ingest = load_ingest_module()
    contract = load_contract_module()
    story = tmp_path / "story.md"
    write_story(story)

    plan = ingest.ingest_story(story, start={"kind": "from_start"})
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(plan)) == []
    assert contract.validate_scene(plan["voice_scene"]) == []
