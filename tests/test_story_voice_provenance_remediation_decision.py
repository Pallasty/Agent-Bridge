from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "scripts" / "story_voice_provenance_remediation_decision.py"
)
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_provenance_remediation_decision.schema.json"
)
S5O_RECEIPT = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "s5o_config_provenance_gate.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_provenance_remediation_decision", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def s5o_fixture() -> dict:
    return {
        "schema": "agent_bridge.voice_config_provenance_gate.v1",
        "official_model_id": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "status": "configuration_compatible_provenance_incomplete",
        "config_graph_compatible": True,
        "reference_generation_ready": False,
        "converter_provenance": {
            "declared_model_id": (
                "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
            ),
            "declared_source_revision": None,
        },
    }


def public_evidence(source_revision=None) -> dict:
    return {
        "onnx_repository": (
            "onnx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice"
        ),
        "onnx_upload_commit": (
            "0ac9e3de55c326eec31a3cdf3b2dcd98cc86ff82"
        ),
        "declared_base_model_id": (
            "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
        ),
        "declared_base_model_revision": source_revision,
        "artifact_bound_attestation": False,
    }


def test_missing_public_source_revision_selects_fixed_source_reexport() -> None:
    decision = load_module().build_decision(
        s5o_fixture(), public_evidence()
    )

    assert decision["status"] == (
        "fixed_source_reexport_selected_authorization_required"
    )
    assert decision["selected_path"] == "B_fixed_source_reexport"
    assert decision["path_a"]["can_close_lineage"] is False
    assert decision["path_b"]["status"] == "selected_not_started"
    assert decision["reference_generation_ready"] is False
    assert decision["blockers"] == [
        "converter_artifact_bound_attestation_missing",
        "fixed_revision_small_files_not_locally_acquired",
        "fixed_revision_weights_not_authorized",
        "fixed_source_reexport_not_executed",
        "parity_not_reverified",
    ]


def test_decision_has_no_runtime_or_model_mutation_effects() -> None:
    decision = load_module().build_decision(
        s5o_fixture(), public_evidence()
    )

    assert decision["runtime_effects"] == {
        "downloaded_files": False,
        "executed_converter": False,
        "executed_onnx_graphs": False,
        "replaced_current_snapshot": False,
        "used_gpu": False,
        "played_audio": False,
        "wrote_global_memory": False,
        "wrote_forum": False,
    }


def test_unattested_revision_cannot_close_path_a() -> None:
    decision = load_module().build_decision(
        s5o_fixture(),
        public_evidence(
            "6c3e96b6a2c593ce3e546ee699a5d944de81850e"
        ),
    )

    assert decision["path_a"]["can_close_lineage"] is False
    assert decision["selected_path"] == "B_fixed_source_reexport"


def test_artifact_bound_attestation_can_reopen_path_a() -> None:
    evidence = public_evidence(
        "6c3e96b6a2c593ce3e546ee699a5d944de81850e"
    )
    evidence["artifact_bound_attestation"] = True

    decision = load_module().build_decision(s5o_fixture(), evidence)

    assert decision["status"] == "artifact_lineage_recovery_available"
    assert decision["selected_path"] == "A_recover_artifact_lineage"
    assert decision["path_a"]["can_close_lineage"] is True
    assert decision["reference_generation_ready"] is False


def test_inconsistent_s5o_receipt_fails_closed() -> None:
    receipt = s5o_fixture()
    receipt["reference_generation_ready"] = True

    decision = load_module().build_decision(receipt, public_evidence())

    assert decision["status"] == "blocked"
    assert decision["selected_path"] is None
    assert decision["blockers"] == ["s5o_receipt_not_safe_incomplete"]


def test_repository_receipt_validates_against_schema() -> None:
    jsonschema = __import__("jsonschema")
    receipt = json.loads(S5O_RECEIPT.read_text())
    decision = load_module().build_decision(receipt, public_evidence())
    schema = json.loads(SCHEMA_PATH.read_text())

    jsonschema.validate(decision, schema)
