from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_wiring_readiness_recheck.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
PRIOR = VOICE_SCENE / "s5zr_story_coordinated_wiring_review_receipt.json"
RECEIPT = VOICE_SCENE / "s5zs_story_wiring_readiness_recheck_receipt.json"
SCHEMA = VOICE_SCENE / "story_wiring_readiness_recheck.schema.json"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_wiring_readiness_recheck", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(**overrides):
    kwargs = {
        "prior_receipt_path": PRIOR,
        "lib_path": ROOT / "crates" / "bridge" / "src" / "lib.rs",
        "registry_path": ROOT / "crates" / "bridge" / "src" / "mcp_tools.rs",
        "cargo_path": ROOT / "crates" / "bridge" / "Cargo.toml",
        "lib_worktree_clean": False,
        "registry_worktree_clean": False,
        "cargo_worktree_clean": False,
        "active_agent_bridge_cargo_processes": 2,
    }
    return load_module().build_recheck(**{**kwargs, **overrides})


def test_receipt_distinguishes_stable_from_clean() -> None:
    result = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert result["status"] == "story_wiring_readiness_recheck_complete"
    assert result["freshness"]["all_shared_surface_hashes_unchanged"] is True
    assert result["decision"] == {
        "selected": "keep_wiring_deferred_shared_surfaces_not_clean",
        "wiring_implementation_admitted": False,
    }
    assert result["blockers"] == [
        "lib_module_tree_not_clean",
        "registry_not_clean",
        "cargo_manifest_not_clean",
        "agent_bridge_cargo_activity_active",
    ]


def test_clean_and_unchanged_surfaces_admit_next_review() -> None:
    result = build(
        lib_worktree_clean=True,
        registry_worktree_clean=True,
        cargo_worktree_clean=True,
        active_agent_bridge_cargo_processes=0,
    )

    assert result["blockers"] == []
    assert result["decision"]["selected"] == "admit_minimal_story_wiring_review"
    assert result["decision"]["wiring_implementation_admitted"] is True
    assert result["execution_authorized"] is False


def test_hash_drift_is_a_separate_blocker(tmp_path: Path) -> None:
    changed = tmp_path / "lib.rs"
    changed.write_text("// changed\n", encoding="utf-8")

    result = build(
        lib_path=changed,
        lib_worktree_clean=True,
        registry_worktree_clean=True,
        cargo_worktree_clean=True,
        active_agent_bridge_cargo_processes=0,
    )

    assert result["freshness"]["lib_hash_unchanged"] is False
    assert result["blockers"] == ["shared_surface_provenance_drift"]
    assert result["decision"]["wiring_implementation_admitted"] is False


def test_rejects_mutated_prior_authority(tmp_path: Path) -> None:
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    prior["runtime_effects"]["registered_story_command"] = True
    changed = tmp_path / "prior.json"
    changed.write_text(json.dumps(prior), encoding="utf-8")

    with pytest.raises(ValueError, match="S5ZR authority invalid"):
        build(prior_receipt_path=changed)


def test_receipt_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
