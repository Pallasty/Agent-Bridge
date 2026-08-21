from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_qwen_remains_the_only_production_default() -> None:
    capabilities = read_json("config/tts-backend-capabilities.json")
    backends = capabilities["backends"]
    assert backends["qwen3_custom_voice"]["production_default"] is True
    assert backends["omnivoice_onnx_candidate"]["production_default"] is False
    assert backends["qwen3_custom_voice"]["natural_language_instruction"] is True
    assert backends["omnivoice_onnx_candidate"]["natural_language_instruction"] is False


def test_omnivoice_canary_is_allowlisted_and_falls_back_to_qwen() -> None:
    policy = read_json("config/omnivoice-canary.json")
    assert policy["candidate_backend"] == "omnivoice"
    assert policy["control_backend"] == "qwen3"
    assert policy["allowlisted_subjects"] == ["owner-local-pilot"]
    assert policy["fallback_to_control_on_candidate_error"] is True


def test_application_handoff_keeps_runtime_promotion_closed() -> None:
    handoff = (ROOT / "docs/reports/qwen3-tts-quantization/2026-08-20-application-handoff-v1.md").read_text()
    assert "QWEN_PRODUCTION_DEFAULT_OMNIVOICE_PILOT_ONLY" in handoff
    assert "candidate.receipt.json" in handoff
    assert "at least 5% projected model-memory saving" in handoff
    assert "negative runtime-memory delta" in handoff
