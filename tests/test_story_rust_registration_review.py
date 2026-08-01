from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_rust_registration_review.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
SCHEMA_PATH = VOICE_SCENE / "story_rust_registration_review.schema.json"
RECEIPT_PATH = VOICE_SCENE / "s5zn_rust_story_registration_review_receipt.json"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_rust_registration_review", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(**overrides):
    kwargs = {
        "registry_path": ROOT / "crates" / "bridge" / "src" / "mcp_tools.rs",
        "lib_path": ROOT / "crates" / "bridge" / "src" / "lib.rs",
        "story_module_path": ROOT / "crates" / "bridge" / "src" / "story_contract.rs",
        "parity_receipt_path": VOICE_SCENE
        / "s5zm_rust_story_preflight_adapter_receipt.json",
        "prior_registration_receipt_path": VOICE_SCENE
        / "s5zg_story_command_registration_contract_receipt.json",
    }
    return load_module().build_registration_review(**{**kwargs, **overrides})


def test_review_selects_adapter_hardening_before_registration() -> None:
    result = build()

    assert result["status"] == "rust_story_registration_review_complete"
    assert result["decision"]["selected"] == "harden_native_adapter_before_registration"
    assert result["decision"]["registration_implementation_admitted"] is False
    assert result["evidence"]["s5zm_full_parity_verified"] is True
    assert result["evidence"]["current_registry_collision"] is False
    assert result["evidence"]["prior_registry_provenance_drift"] is True
    assert result["evidence"]["story_module_exported"] is False
    assert result["blockers"] == [
        "bounded_source_admission_missing",
        "configured_evidence_bundle_resolver_missing",
        "async_cancellation_contract_missing",
    ]


def test_review_keeps_tool_niche_hidden_and_non_actuating() -> None:
    result = build()

    assert result["proposed_surface"] == {
        "tool_name": "story_command_preflight",
        "tier": "Niche",
        "default_exposed": False,
        "codex_essential_exposed": False,
        "codex_voice_exposed": False,
        "activation_env": "AB_STORY_COMMAND_PREFLIGHT_ENABLE",
        "activation_env_required_value": "1",
    }
    assert result["execution_authorized"] is False
    assert all(value is False for value in result["runtime_effects"].values())
    assert result["next_gate"] == "rust_story_preflight_adapter_hardening"


def test_review_rejects_name_collision(tmp_path: Path) -> None:
    registry = tmp_path / "mcp_tools.rs"
    registry.write_text(
        'fn name(&self) -> &str { "story_command_preflight" }', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="tool name collision"):
        build(registry_path=registry)


def test_review_rejects_mutated_parity_authority(tmp_path: Path) -> None:
    receipt = json.loads(
        (VOICE_SCENE / "s5zm_rust_story_preflight_adapter_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    changed = copy.deepcopy(receipt)
    changed["runtime_effects"]["loaded_model"] = True
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(ValueError, match="S5ZM parity evidence invalid"):
        build(parity_receipt_path=path)


def test_real_review_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(build())) == []


def test_committed_receipt_exactly_matches_current_review() -> None:
    assert json.loads(RECEIPT_PATH.read_text(encoding="utf-8")) == build()
