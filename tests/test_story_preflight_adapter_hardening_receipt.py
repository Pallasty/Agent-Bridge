from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT = VOICE_SCENE / "s5zo_story_preflight_adapter_hardening_receipt.json"
SCHEMA = VOICE_SCENE / "story_preflight_adapter_hardening.schema.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_s5zo_receipt_is_schema_valid_and_source_bound() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
    assert receipt["evidence"]["rust_module_sha256"] == sha256(
        ROOT / receipt["evidence"]["rust_module_path"]
    )
    assert receipt["evidence"]["rust_test_sha256"] == sha256(
        ROOT / receipt["evidence"]["rust_test_path"]
    )


def test_s5zo_keeps_registration_and_runtime_nonclaims() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert all(receipt["hardening"].values())
    assert all(receipt["negative_controls"].values())
    assert all(value is False for value in receipt["scope"].values())
    assert all(value is False for value in receipt["runtime_effects"].values())
    assert receipt["next_gate"] == (
        "owner_authorized_rust_story_registration_implementation_review"
    )
