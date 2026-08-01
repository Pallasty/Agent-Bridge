from __future__ import annotations

import json
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT = VOICE_SCENE / "s603_story_fixture_bounded_render_receipt.json"
SCHEMA = VOICE_SCENE / "story_fixture_bounded_render.schema.json"


def test_s603_receipt_validates_and_preserves_execution_boundary() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    jsonschema.validate(receipt, schema)
    assert [row["speaker"] for row in receipt["segments"]] == [
        "Vivian",
        "Serena",
        "Vivian",
    ]
    assert receipt["assembly"]["gap_seconds"] == [1.0, 1.0]
    assert receipt["owner_feedback"]["accepted"] is True
    assert receipt["runtime_effects"]["wrote_memory"] is False
    assert receipt["claims"]["story_command_render_executor_enabled"] is False
    assert receipt["next_gate"] == "story_bounded_render_execution_contract"
