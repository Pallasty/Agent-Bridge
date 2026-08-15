from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT_PATH = VOICE_SCENE / "s5zk_rust_story_source_ingest_receipt.json"
SCHEMA_PATH = VOICE_SCENE / "story_rust_source_ingest.schema.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_s5zk_checkpoint_receipt_binds_python_and_fixture_evidence() -> None:
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    evidence = receipt["evidence"]

    assert receipt["status"] == "rust_story_source_ingest_parity_verified"
    # Rust files continue into later native-port stages; S5ZK retains their
    # checkpoint hashes while stable external oracle inputs stay live-bound.
    assert len(evidence["rust_module_sha256"]) == 64
    assert len(evidence["rust_test_sha256"]) == 64
    for path_field, hash_field in (
        ("python_oracle_path", "python_oracle_sha256"),
        ("fixture_path", "fixture_sha256"),
    ):
        assert evidence[hash_field] == sha256(ROOT / evidence[path_field])
    assert all(receipt["parity"].values())
    assert all(value is False for value in receipt["runtime_effects"].values())
    assert receipt["scope"]["module_exported"] is False
    assert receipt["scope"]["mcp_registered"] is False
    assert receipt["next_gate"] == "rust_story_voice_plan_parity"


def test_s5zk_receipt_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
