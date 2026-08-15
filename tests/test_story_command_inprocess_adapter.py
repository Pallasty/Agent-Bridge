from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_command_inprocess_adapter.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
SCHEMA_PATH = VOICE_SCENE / "story_command_inprocess_adapter.schema.json"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_command_inprocess_adapter", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence_paths() -> dict:
    return {
        "registration_contract_path": VOICE_SCENE
        / "s5zg_story_command_registration_contract_receipt.json",
        "voice_plan_path": VOICE_SCENE
        / "s5zc_source_grounded_utterance_plan_receipt.json",
        "mapping_path": VOICE_SCENE / "s5x_story_voice_mapping_receipt.json",
        "role_acceptance_path": VOICE_SCENE
        / "s5y_character_voice_audition_receipt.json",
        "continuity_acceptance_path": VOICE_SCENE
        / "s5ze_cross_chapter_continuity_receipt.json",
    }


def request(*, chapter: int = 2) -> dict:
    return {
        "source_path": str(VOICE_SCENE / "fixtures" / "story_s1.md"),
        "start": {"kind": "chapter", "chapter": chapter},
        "dry_run": True,
    }


def test_adapter_calls_preflight_in_same_python_process() -> None:
    module = load_module()

    result, trace = module.run_inprocess_story_preflight(
        request(), **evidence_paths()
    )

    assert result["status"] == "story_command_integration_preflight_reviewable"
    assert result["command"]["chapter_number"] == 2
    assert result["selection"]["selected_segments"] == 3
    assert trace == {
        "adapter": "python_direct_function_call",
        "same_process": True,
        "used_shell": False,
        "spawned_subprocess": False,
        "registered_mcp_tool": False,
    }


def test_adapter_rejects_non_contract_fields_and_non_dry_run() -> None:
    module = load_module()

    with pytest.raises(ValueError, match="adapter request fields invalid"):
        module.run_inprocess_story_preflight(
            {**request(), "play": True}, **evidence_paths()
        )
    with pytest.raises(ValueError, match="adapter requires dry_run=true"):
        module.run_inprocess_story_preflight(
            {**request(), "dry_run": False}, **evidence_paths()
        )


def test_adapter_rejects_drifted_bound_implementation(tmp_path: Path) -> None:
    module = load_module()
    drifted = tmp_path / "preflight.py"
    drifted.write_text("# drift\n", encoding="utf-8")

    with pytest.raises(ValueError, match="preflight script SHA-256 mismatch"):
        module.run_inprocess_story_preflight(
            request(), preflight_script_path=drifted, **evidence_paths()
        )


def test_adapter_source_has_no_shell_or_subprocess_path() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    called_names = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "subprocess" not in imported_roots
    assert "os" not in imported_roots
    assert {"system", "popen", "spawn", "run", "call", "check_output"}.isdisjoint(
        called_names
    )


def test_adapter_receipt_keeps_rust_and_runtime_nonclaims() -> None:
    module = load_module()

    receipt = module.build_adapter_receipt(request(), **evidence_paths())

    assert receipt["status"] == "python_inprocess_adapter_verified"
    assert receipt["preflight"]["preflight_sha256"] == (
        "6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb"
    )
    assert receipt["claims"]["python_same_process_direct_call"] is True
    assert receipt["claims"]["rust_inprocess_adapter_proven"] is False
    assert receipt["claims"]["mcp_tool_registered"] is False
    assert all(value is False for value in receipt["runtime_effects"].values())
    assert receipt["next_gate"] == "rust_inprocess_story_preflight_design"


def test_real_adapter_receipt_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    receipt = load_module().build_adapter_receipt(request(), **evidence_paths())

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
