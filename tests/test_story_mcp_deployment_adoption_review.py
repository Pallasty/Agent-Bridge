from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_mcp_deployment_adoption_review.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
SOURCE_RECEIPT = VOICE_SCENE / "s5zt_story_mcp_registry_wiring_receipt.json"
RECEIPT = VOICE_SCENE / "s5zu_story_mcp_deployment_adoption_review_receipt.json"
SCHEMA = VOICE_SCENE / "story_mcp_deployment_adoption_review.schema.json"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_mcp_deployment_adoption_review", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(**overrides):
    kwargs = {
        "source_receipt_path": SOURCE_RECEIPT,
        "source_commit": "26334149d2fc685501289b16ca5552b59a72c56a",
        "origin_commit": "9b198da9571d8a6b2975161ce1e87b50ee6a35eb",
        "source_commit_in_origin": False,
        "installed_binary_sha256": "762c27bee788045dc23681881e1011be8722d9696b2205068a75b2a7c0c045ed",
        "installed_binary_version": "agent-bridge 0.14.0 (v0.14.0-1253-g5a02c8fd-dirty; 5a02c8fdeccc)",
        "installed_binary_has_story_marker": False,
        "wrapper_has_story_activation": False,
        "machine_env_has_story_activation": False,
        "installed_mcp_processes": 7,
        "installed_mcp_processes_with_story_binary": 0,
        "live_client_tool_observed": False,
    }
    return load_module().build_review(**{**kwargs, **overrides})


def test_receipt_rejects_deployment_adoption_at_four_layers() -> None:
    result = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert result["status"] == "story_mcp_deployment_adoption_review_complete"
    assert result["decision"] == {
        "selected": "defer_deployment_until_source_and_configuration_adopted",
        "deployment_admitted": False,
        "client_refresh_admitted": False,
    }
    assert result["blockers"] == [
        "source_commit_not_in_origin_master",
        "installed_binary_missing_story_marker",
        "story_activation_not_configured",
        "running_mcp_processes_use_pre_story_binary",
        "live_client_tool_not_observed",
    ]


def test_fully_adopted_layers_admit_client_refresh_review_not_execution() -> None:
    result = build(
        source_commit_in_origin=True,
        installed_binary_has_story_marker=True,
        wrapper_has_story_activation=True,
        installed_mcp_processes_with_story_binary=7,
        live_client_tool_observed=True,
    )

    assert result["blockers"] == []
    assert result["decision"]["deployment_admitted"] is True
    assert result["decision"]["client_refresh_admitted"] is True
    assert result["execution_authorized"] is False
    assert all(value is False for value in result["runtime_effects"].values())


def test_activation_in_machine_env_is_equivalent_to_wrapper_injection() -> None:
    result = build(
        source_commit_in_origin=True,
        installed_binary_has_story_marker=True,
        machine_env_has_story_activation=True,
        installed_mcp_processes_with_story_binary=7,
        live_client_tool_observed=True,
    )

    assert "story_activation_not_configured" not in result["blockers"]


def test_rejects_mutated_source_authority(tmp_path: Path) -> None:
    source = json.loads(SOURCE_RECEIPT.read_text(encoding="utf-8"))
    source["runtime_effects"]["deployed"] = True
    changed = tmp_path / "source.json"
    changed.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match="S5ZT source authority invalid"):
        build(source_receipt_path=changed)


def test_receipt_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
