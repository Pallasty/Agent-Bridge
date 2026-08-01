import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "crates" / "bridge" / "src" / "lib.rs"
REGISTRY = ROOT / "crates" / "bridge" / "src" / "mcp_tools.rs"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"


def test_story_modules_are_declared_at_crate_and_registry_boundaries() -> None:
    lib = LIB.read_text(encoding="utf-8")
    registry = REGISTRY.read_text(encoding="utf-8")

    assert "pub(crate) mod story_contract;" in lib
    assert "mod story;" in registry
    assert "use story::{StoryCommandPreflightTool, StoryMcpConfig};" in registry


def test_runtime_registry_is_opt_in_niche_and_fail_closed() -> None:
    registry = REGISTRY.read_text(encoding="utf-8")

    assert "match StoryMcpConfig::from_env()" in registry
    assert "Arc::new(StoryCommandPreflightTool::new(config))" in registry
    assert 'tool = "story_command_preflight"' in registry
    assert "invalid story MCP configuration; tool left unregistered" in registry

    story_registration = registry.index("match StoryMcpConfig::from_env()")
    next_registry_log = registry.index("tracing::info!", story_registration)
    block = registry[story_registration:next_registry_log]
    assert "Tier::Niche" in block


def test_story_tool_is_not_promoted_to_eager_allowlists() -> None:
    registry = REGISTRY.read_text(encoding="utf-8")
    essential_start = registry.index("const CODEX_ESSENTIAL_DIRECT_EXTRAS")
    voice_start = registry.index("const CODEX_VOICE_EXTRAS")
    helper_start = registry.index("fn codex_essential_tool", voice_start)

    assert "story_command_preflight" not in registry[essential_start:voice_start]
    assert "story_command_preflight" not in registry[voice_start:helper_start]


def test_s5zt_receipt_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (VOICE_SCENE / "story_mcp_registry_wiring.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (VOICE_SCENE / "s5zt_story_mcp_registry_wiring_receipt.json").read_text(
            encoding="utf-8"
        )
    )

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
