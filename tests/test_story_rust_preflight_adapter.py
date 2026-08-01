from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT_PATH = VOICE_SCENE / "s5zm_rust_story_preflight_adapter_receipt.json"
SCHEMA_PATH = VOICE_SCENE / "story_rust_preflight_adapter.schema.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_s5zm_receipt_binds_complete_parity_evidence() -> None:
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    evidence = receipt["evidence"]

    assert receipt["status"] == "rust_story_preflight_adapter_parity_verified"
    for path_field, hash_field in (
        ("rust_module_path", "rust_module_sha256"),
        ("rust_test_path", "rust_test_sha256"),
        ("python_preflight_path", "python_preflight_sha256"),
        ("accepted_preflight_path", "accepted_preflight_sha256"),
    ):
        assert evidence[hash_field] == sha256(ROOT / evidence[path_field])
    assert all(receipt["parity"].values())
    assert all(receipt["negative_controls"].values())
    assert all(value is False for value in receipt["runtime_effects"].values())
    assert receipt["scope"]["module_exported"] is False
    assert receipt["scope"]["mcp_registered"] is False
    assert receipt["next_gate"] == "owner_authorized_rust_story_registration_review"


def test_s5zm_receipt_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
