from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "scripts" / "story_voice_existing_onnx_adoption_decision.py"
)
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_existing_onnx_adoption_decision.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_existing_onnx_adoption_decision", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence() -> dict:
    return {
        "snapshot": {
            "status": "blocked",
            "snapshot": "/models/community-onnx",
            "variants": {
                name: {"manifest_valid": True}
                for name in (
                    "cpu_fp32",
                    "cpu_fp16",
                    "cpu_int4",
                    "cuda_fp32",
                    "cuda_fp16",
                    "cuda_int4",
                )
            },
            "blockers": [
                "revision_not_immutable",
                "standalone_license_file_missing",
                "python_dangerous_primitives_present",
            ],
        },
        "session": {
            "status": "session_creation_passed_no_inference",
            "provider": "CPUExecutionProvider",
            "planned_models": [f"cpu_int4/model-{i}.onnx" for i in range(7)],
            "probed_models": [
                {"path": f"cpu_int4/model-{i}.onnx", "status": "session_created"}
                for i in range(7)
            ],
        },
        "single_frame": {
            "status": "single_codec_frame_loop_passed_no_audio",
            "runtime_effects": {
                "rendered_audio": False,
                "played_audio": False,
                "used_gpu": False,
            },
        },
        "original": {
            "weight_payload_fixed_revision_equivalent": True,
            "source": {"snapshot": "/models/original"},
        },
        "offline_lock": {
            "status": "direct_lock_contract_ready_wheelhouse_pending",
            "readiness": {
                "offline_install_ready": False,
                "converter_execution_ready": False,
            },
        },
    }


def test_existing_onnx_becomes_active_trial_lane() -> None:
    decision = load_module().decide(**evidence())

    assert decision["status"] == "existing_onnx_trial_selected"
    assert decision["active_lane"] == "community_cpu_int4"
    assert decision["reexport_lane"] == "paused_fallback_only"
    assert decision["existing_onnx_evidence"] == {
        "six_variant_manifests_valid": True,
        "cpu_int4_sessions_created": 7,
        "single_codec_frame_loop_passed": True,
        "end_to_end_text_to_wav_verified": False,
    }


def test_original_weights_are_retained_without_reload_or_conversion() -> None:
    decision = load_module().decide(**evidence())

    assert decision["original_model"]["role"] == (
        "immutable_weight_equivalent_fallback_and_future_reference"
    )
    assert decision["original_model"]["loaded"] is False
    assert decision["runtime_effects"]["executed_converter"] is False
    assert decision["runtime_effects"]["downloaded_files"] is False


def test_missing_runtime_is_small_gap_not_wheelhouse_authorization() -> None:
    decision = load_module().decide(
        **evidence(),
        runtime_facts={
            "onnxruntime": True,
            "numpy": True,
            "transformers": False,
            "soundfile": False,
            "librosa": False,
        },
    )

    assert decision["next_gate"] == (
        "existing_onnx_minimal_runtime_and_bounded_text_to_wav_trial"
    )
    assert decision["runtime_gap"]["missing"] == [
        "transformers",
        "soundfile",
        "librosa",
    ]
    assert decision["runtime_gap"]["multi_gb_conversion_wheelhouse_required"] is False
    assert decision["runtime_gap"]["dependency_install_authorized"] is False


def test_decision_fails_closed_without_session_or_single_frame_evidence() -> None:
    facts = evidence()
    facts["session"]["status"] = "blocked"
    with pytest.raises(ValueError, match="CPU session evidence"):
        load_module().decide(**facts)

    facts = evidence()
    facts["single_frame"]["status"] = "blocked"
    with pytest.raises(ValueError, match="single-frame evidence"):
        load_module().decide(**facts)


def test_decision_keeps_supply_chain_and_mi50_claims_blocked() -> None:
    decision = load_module().decide(**evidence())

    assert decision["claims"]["publisher_lineage_verified"] is False
    assert decision["claims"]["production_admitted"] is False
    assert decision["claims"]["mi50_verified"] is False
    assert decision["claims"]["human_audibility_verified"] is False


def test_repository_shape_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    decision = load_module().decide(**evidence())
    jsonschema.validate(decision, json.loads(SCHEMA_PATH.read_text()))
