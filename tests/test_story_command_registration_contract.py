from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_command_registration_contract.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
SCHEMA_PATH = VOICE_SCENE / "story_command_registration_contract.schema.json"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_command_registration_contract", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(**overrides):
    module = load_module()
    kwargs = {
        "preflight_receipt_path": VOICE_SCENE
        / "s5zf_story_command_integration_preflight_receipt.json",
        "preflight_schema_path": VOICE_SCENE
        / "story_command_integration_preflight.schema.json",
        "preflight_script_path": ROOT
        / "scripts"
        / "story_command_integration_preflight.py",
        "registry_source_path": ROOT / "crates" / "bridge" / "src" / "mcp_tools.rs",
    }
    return module.build_registration_contract(**{**kwargs, **overrides})


def test_contract_defines_default_hidden_read_only_tool_boundary() -> None:
    result = build()

    assert result["status"] == "story_command_static_registration_contract_reviewable"
    assert result["tool"]["name"] == "story_command_preflight"
    assert result["tool"]["proposed_tier"] == "Niche"
    assert result["tool"]["proposed_toolset_extras"] == []
    assert result["activation"] == {
        "compiled_registered": False,
        "current_registry_collision": False,
        "registry_source_path": str(
            (ROOT / "crates" / "bridge" / "src" / "mcp_tools.rs").resolve()
        ),
        "registry_source_sha256": result["activation"]["registry_source_sha256"],
        "default_exposed": False,
        "codex_essential_exposed": False,
        "codex_voice_exposed": False,
        "activation_env": "AB_STORY_COMMAND_PREFLIGHT_ENABLE",
        "activation_env_required_value": "1",
        "activation_env_evaluated": False,
    }
    assert len(result["activation"]["registry_source_sha256"]) == 64
    assert result["execution_authorized"] is False
    assert all(value is False for value in result["runtime_effects"].values())


def test_input_schema_only_accepts_static_source_and_start_selector() -> None:
    result = build()
    schema = result["tool"]["input_schema"]

    assert schema["required"] == ["source_path", "start", "dry_run"]
    assert schema["properties"]["dry_run"] == {"const": True}
    assert set(schema["properties"]) == {"source_path", "start", "dry_run"}
    encoded = json.dumps(schema, sort_keys=True)
    assert all(
        forbidden not in encoded
        for forbidden in ("play", "record", "write_memory", "download_model")
    )


def test_contract_hash_binds_preflight_implementation_and_schema() -> None:
    result = build()

    assert len(result["handler"]["preflight_script_sha256"]) == 64
    assert len(result["handler"]["preflight_schema_sha256"]) == 64
    assert (
        result["handler"]["accepted_preflight_sha256"]
        == "6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb"
    )
    assert len(result["contract_sha256"]) == 64
    assert result == build()


def test_contract_fails_closed_if_tool_name_already_exists(tmp_path: Path) -> None:
    registry = tmp_path / "mcp_tools.rs"
    registry.write_text(
        'fn name(&self) -> &str { "story_command_preflight" }', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="tool name already present"):
        build(registry_source_path=registry)


def test_contract_rejects_execution_authority_in_preflight(tmp_path: Path) -> None:
    receipt = json.loads(
        (VOICE_SCENE / "s5zf_story_command_integration_preflight_receipt.json")
        .read_text(encoding="utf-8")
    )
    receipt["execution_authorized"] = True
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(ValueError, match="preflight execution boundary invalid"):
        build(preflight_receipt_path=path)


def test_real_contract_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(build())) == []
