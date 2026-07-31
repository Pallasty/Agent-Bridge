from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_rust_adapter_architecture_decision.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
SCHEMA_PATH = VOICE_SCENE / "story_rust_adapter_architecture_decision.schema.json"
PYTHON_MODULES = [
    ROOT / "scripts" / "story_static_ingest.py",
    ROOT / "scripts" / "story_chapter_voice_plan.py",
    ROOT / "scripts" / "story_bounded_chapter_render.py",
    ROOT / "scripts" / "story_command_integration_preflight.py",
    ROOT / "scripts" / "story_command_inprocess_adapter.py",
]


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_rust_adapter_architecture_decision", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(**overrides):
    kwargs = {
        "bridge_cargo_path": ROOT / "crates" / "bridge" / "Cargo.toml",
        "workspace_cargo_path": ROOT / "Cargo.toml",
        "deploy_script_path": ROOT / "scripts" / "deploy_from_master.sh",
        "python_module_paths": PYTHON_MODULES,
        "adapter_receipt_path": VOICE_SCENE
        / "s5zh_story_command_inprocess_adapter_receipt.json",
    }
    return load_module().build_architecture_decision(**{**kwargs, **overrides})


def test_decision_selects_incremental_rust_native_port() -> None:
    result = build()

    assert result["status"] == "architecture_decision_accepted_static"
    assert result["decision"]["selected"] == "incremental_rust_native_port"
    assert result["decision"]["embedded_python"] == "rejected_for_current_scope"
    assert result["evidence"]["bridge_has_pyo3"] is False
    assert result["evidence"]["rust_primitives_available"] == {
        "serde_json": True,
        "sha2": True,
    }
    assert result["evidence"]["python_third_party_imports"] == []
    assert result["evidence"]["python_total_lines"] == 1694
    assert result["evidence"]["native_binary_deploy_contract"] is True


def test_decision_preserves_python_as_non_authoritative_parity_oracle() -> None:
    result = build()

    assert result["migration"]["python_role"] == "test_oracle_only"
    assert result["migration"]["runtime_authority_transfer"] is False
    assert [stage["id"] for stage in result["migration"]["stages"]] == [
        "S5ZJ",
        "S5ZK",
        "S5ZL",
        "S5ZM",
    ]
    assert all(stage["registered_mcp_tool"] is False for stage in result["migration"]["stages"])


def test_decision_fails_closed_on_new_python_dependency(tmp_path: Path) -> None:
    module = tmp_path / "story.py"
    module.write_text("import numpy\n", encoding="utf-8")

    with pytest.raises(ValueError, match="third-party Python dependency requires review"):
        build(python_module_paths=[*PYTHON_MODULES[:-1], module])


def test_decision_fails_closed_if_pyo3_dependency_appears(tmp_path: Path) -> None:
    cargo = tmp_path / "Cargo.toml"
    cargo.write_text("[dependencies]\npyo3 = \"0.23\"\nserde_json = \"1\"\nsha2 = \"0.10\"\n", encoding="utf-8")

    with pytest.raises(ValueError, match="embedded-Python dependency evidence changed"):
        build(bridge_cargo_path=cargo)


def test_decision_is_deterministic_and_non_actuating() -> None:
    first = build()
    second = build()

    assert first == second
    assert len(first["decision_sha256"]) == 64
    assert first["execution_authorized"] is False
    assert all(value is False for value in first["runtime_effects"].values())
    assert first["next_gate"] == "rust_story_contract_core"


def test_real_decision_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(build())) == []
