from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "story_source_origin_adoption.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT = VOICE_SCENE / "s5zw_story_source_origin_adoption_receipt.json"
SCHEMA = VOICE_SCENE / "story_source_origin_adoption.schema.json"


def load_module():
    spec = importlib.util.spec_from_file_location("story_source_origin_adoption", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_receipt_records_dual_remote_adoption_without_runtime_claims() -> None:
    result = json.loads(RECEIPT.read_text(encoding="utf-8"))
    rebuilt = load_module().build_adoption(
        local_head="682cce5a48547bc7285b9d087dd452568e0974e3",
        gitlab_head="682cce5a48547bc7285b9d087dd452568e0974e3",
        github_head="682cce5a48547bc7285b9d087dd452568e0974e3",
        configuration_fragment_path=VOICE_SCENE / "story_fixture_pilot.machine.env",
    )

    assert result == rebuilt
    assert result["status"] == "story_source_origin_adopted"
    assert result["decision"] == {
        "source_adopted": True,
        "configuration_installed": False,
        "deployment_dry_run_admitted": False,
    }
    assert result["remotes"]["all_equal"] is True
    assert result["next_gate"] == "story_fixture_configuration_installation_review"
    assert all(value is False for value in result["runtime_effects"].values())


def test_mismatched_remote_fails_closed() -> None:
    with pytest.raises(ValueError, match="remote adoption mismatch"):
        load_module().build_adoption(
            local_head="a" * 40,
            gitlab_head="a" * 40,
            github_head="b" * 40,
            configuration_fragment_path=VOICE_SCENE / "story_fixture_pilot.machine.env",
        )


def test_receipt_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
