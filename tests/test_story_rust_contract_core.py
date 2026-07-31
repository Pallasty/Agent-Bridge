from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT_PATH = VOICE_SCENE / "s5zj_rust_story_contract_core_receipt.json"
SCHEMA_PATH = VOICE_SCENE / "story_rust_contract_core.schema.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_s5zj_receipt_is_source_bound_and_non_actuating() -> None:
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    assert receipt["status"] == "rust_contract_core_parity_verified"
    assert receipt["evidence"]["rust_module_sha256"] == sha256(
        ROOT / receipt["evidence"]["rust_module_path"]
    )
    assert receipt["evidence"]["rust_test_sha256"] == sha256(
        ROOT / receipt["evidence"]["rust_test_path"]
    )
    assert all(receipt["parity"].values())
    assert all(value is False for value in receipt["runtime_effects"].values())
    assert receipt["scope"]["module_exported"] is False
    assert receipt["scope"]["mcp_registered"] is False
    assert receipt["next_gate"] == "rust_story_source_ingest_parity"


def test_s5zj_receipt_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
