from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_coordinated_wiring_review.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT_PATH = VOICE_SCENE / "s5zr_story_coordinated_wiring_review_receipt.json"
SCHEMA_PATH = VOICE_SCENE / "story_coordinated_wiring_review.schema.json"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_coordinated_wiring_review", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(**overrides):
    kwargs = {
        "lib_path": ROOT / "crates" / "bridge" / "src" / "lib.rs",
        "registry_path": ROOT / "crates" / "bridge" / "src" / "mcp_tools.rs",
        "cargo_path": ROOT / "crates" / "bridge" / "Cargo.toml",
        "adapter_path": ROOT / "crates" / "bridge" / "src" / "mcp_tools" / "story.rs",
        "story_contract_path": ROOT / "crates" / "bridge" / "src" / "story_contract.rs",
        "adapter_receipt_path": VOICE_SCENE
        / "s5zq_story_mcp_adapter_isolated_receipt.json",
        "lib_worktree_overlap": True,
        "registry_worktree_overlap": True,
        "cargo_worktree_overlap": True,
        "active_cargo_processes": 2,
    }
    return load_module().build_review(**{**kwargs, **overrides})


def test_receipt_defers_shared_surface_wiring() -> None:
    result = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    assert result["status"] == "story_coordinated_wiring_review_complete"
    assert result["decision"] == {
        "selected": "defer_wiring_until_shared_surfaces_clean",
        "minimal_patch_contract_admitted": True,
        "wiring_implementation_admitted": False,
    }
    assert result["blockers"] == [
        "lib_module_tree_overlap_active",
        "registry_worktree_overlap_active",
        "cargo_manifest_overlap_active",
        "shared_cargo_activity_active",
    ]


def test_patch_contract_is_niche_fail_closed_and_dependency_free(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "mcp_tools.rs"
    registry.write_text("// pre-wiring registry fixture\n", encoding="utf-8")
    contract = build(registry_path=registry)["minimal_patch_contract"]

    assert contract["module_tree_declaration"] == "pub(crate) mod story_contract;"
    assert contract["registry_module_declaration"] == "mod story;"
    assert contract["tool_name"] == "story_command_preflight"
    assert contract["tier"] == "Niche"
    assert contract["invalid_enabled_config"] == "warn_and_leave_tool_unregistered"
    assert contract["cargo_manifest_change_required"] is False
    assert contract["eager_profile_exposure"] is False


def test_clean_surfaces_admit_implementation_review_not_execution(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "mcp_tools.rs"
    registry.write_text("// pre-wiring registry fixture\n", encoding="utf-8")
    result = build(
        registry_path=registry,
        lib_worktree_overlap=False,
        registry_worktree_overlap=False,
        cargo_worktree_overlap=False,
        active_cargo_processes=0,
    )

    assert result["blockers"] == []
    assert result["decision"]["selected"] == "admit_minimal_wiring_implementation_review"
    assert result["decision"]["wiring_implementation_admitted"] is True
    assert result["execution_authorized"] is False
    assert all(value is False for value in result["runtime_effects"].values())


def test_rejects_adapter_receipt_that_claims_runtime_effects(tmp_path: Path) -> None:
    receipt = json.loads(
        (VOICE_SCENE / "s5zq_story_mcp_adapter_isolated_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    receipt["runtime_effects"]["registered_story_command"] = True
    changed = tmp_path / "receipt.json"
    changed.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(ValueError, match="S5ZQ adapter evidence invalid"):
        build(adapter_receipt_path=changed)


def test_receipt_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
