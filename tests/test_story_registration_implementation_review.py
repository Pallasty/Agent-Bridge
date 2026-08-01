from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "story_registration_implementation_review.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
SCHEMA = VOICE_SCENE / "story_registration_implementation_review.schema.json"
RECEIPT = VOICE_SCENE / "s5zp_story_registration_implementation_review_receipt.json"


def load_module():
    spec = importlib.util.spec_from_file_location("story_registration_review", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(**overrides):
    kwargs = {
        "registry_path": ROOT / "crates/bridge/src/mcp_tools.rs",
        "lib_path": ROOT / "crates/bridge/src/lib.rs",
        "story_module_path": ROOT / "crates/bridge/src/story_contract.rs",
        "mcp_server_path": ROOT / "crates/mcp/src/server.rs",
        "hardening_receipt_path": VOICE_SCENE
        / "s5zo_story_preflight_adapter_hardening_receipt.json",
        "registry_worktree_overlap": True,
        "lib_worktree_overlap": True,
    }
    return load_module().build_review(**{**kwargs, **overrides})


def test_review_selects_isolated_adapter_before_registry_wiring() -> None:
    result = build()

    assert result["status"] == "story_registration_implementation_review_complete"
    assert result["decision"] == {
        "selected": "isolated_adapter_before_registry_wiring",
        "isolated_adapter_implementation_admitted": True,
        "registry_wiring_admitted": False,
    }
    assert result["blockers"] == [
        "mcp_future_drop_cancellation_guard_missing",
        "registry_worktree_overlap_active",
        "lib_module_tree_overlap_active",
    ]
    assert result["next_gate"] == "isolated_rust_story_mcp_adapter"


def test_review_defines_hidden_fail_closed_surface() -> None:
    result = build()

    assert result["proposed_surface"]["tool_name"] == "story_command_preflight"
    assert result["proposed_surface"]["tier"] == "Niche"
    assert result["proposed_surface"]["toolset_extras"] == []
    assert result["proposed_surface"]["activation_env"] == (
        "AB_STORY_COMMAND_PREFLIGHT_ENABLE"
    )
    assert result["adapter_contract"]["future_drop_cancel_guard_required"] is True
    assert result["adapter_contract"]["complete_config_required_before_exposure"] is True
    assert result["execution_authorized"] is False
    assert all(value is False for value in result["runtime_effects"].values())


def test_review_rejects_existing_tool_name(tmp_path: Path) -> None:
    registry = tmp_path / "mcp_tools.rs"
    registry.write_text('const NAME: &str = "story_command_preflight";', encoding="utf-8")

    with pytest.raises(ValueError, match="tool name collision"):
        build(registry_path=registry)


def test_review_rejects_invalid_s5zo_authority(tmp_path: Path) -> None:
    receipt = json.loads(
        (VOICE_SCENE / "s5zo_story_preflight_adapter_hardening_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    receipt["scope"]["mcp_registered"] = True
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(ValueError, match="S5ZO hardening evidence invalid"):
        build(hardening_receipt_path=path)


def test_real_review_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(build())) == []


def test_committed_s5zp_receipt_validates_as_historical_review() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
