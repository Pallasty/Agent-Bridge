from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs/design/voice-scene"
RECEIPT = VOICE_SCENE / "s5zq_story_mcp_adapter_isolated_receipt.json"
SCHEMA = VOICE_SCENE / "story_mcp_adapter_isolated.schema.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_s5zq_receipt_is_schema_valid_and_source_bound() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
    for path_key, hash_key in (
        ("adapter_path", "adapter_sha256"),
        ("test_path", "test_sha256"),
    ):
        assert receipt["evidence"][hash_key] == sha256(
            ROOT / receipt["evidence"][path_key]
        )


def test_s5zq_retains_registration_and_runtime_nonclaims() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert all(receipt["claims"].values())
    assert all(receipt["negative_controls"].values())
    assert all(value is False for value in receipt["scope"].values())
    assert all(value is False for value in receipt["runtime_effects"].values())
    assert receipt["next_gate"] == "coordinated_story_module_and_registry_wiring_review"
