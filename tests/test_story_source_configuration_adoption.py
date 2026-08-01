from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_source_configuration_adoption.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT = VOICE_SCENE / "s5zv_story_source_configuration_adoption_receipt.json"
SCHEMA = VOICE_SCENE / "story_source_configuration_adoption.schema.json"
ENV_FRAGMENT = VOICE_SCENE / "story_fixture_pilot.machine.env"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_source_configuration_adoption", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(**overrides):
    kwargs = {
        "source_root": VOICE_SCENE / "fixtures",
        "evidence_root": VOICE_SCENE,
        "voice_plan_path": VOICE_SCENE
        / "s5zc_source_grounded_utterance_plan_receipt.json",
        "mapping_path": VOICE_SCENE / "s5x_story_voice_mapping_receipt.json",
        "role_acceptance_path": VOICE_SCENE
        / "s5y_character_voice_audition_receipt.json",
        "continuity_path": VOICE_SCENE
        / "s5ze_cross_chapter_continuity_receipt.json",
        "source_commit": "26334149d2fc685501289b16ca5552b59a72c56a",
        "origin_commit": "9b198da9571d8a6b2975161ce1e87b50ee6a35eb",
        "source_commit_in_origin": False,
        "max_source_bytes": 1048576,
    }
    return load_module().build_adoption(**{**kwargs, **overrides})


def test_receipt_prepares_fixture_pilot_but_keeps_origin_blocker() -> None:
    result = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert result["status"] == "story_fixture_configuration_ready_source_pending"
    assert result["decision"] == {
        "configuration_adoptable": True,
        "source_adopted": False,
        "deployment_dry_run_admitted": False,
    }
    assert result["blockers"] == ["source_commit_not_in_origin_master"]
    assert result["scope"]["fixture_pilot_only"] is True
    assert result["scope"]["general_novel_library_admitted"] is False


def test_rendered_fragment_is_complete_hash_bound_and_non_secret() -> None:
    result = build()
    rendered = load_module().render_env(result["environment"])

    assert rendered == ENV_FRAGMENT.read_text(encoding="utf-8")
    assert rendered.count("export AB_STORY_") == 12
    assert "AB_STORY_COMMAND_PREFLIGHT_ENABLE='1'" in rendered
    assert "TOKEN" not in rendered
    assert "SECRET" not in rendered
    assert all(item["sha256_verified"] for item in result["evidence_files"])


def test_hash_override_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="evidence SHA-256 mismatch"):
        build(expected_mapping_sha256="0" * 64)


def test_missing_source_root_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="source root is not a directory"):
        build(source_root=tmp_path / "missing")


def test_receipt_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
