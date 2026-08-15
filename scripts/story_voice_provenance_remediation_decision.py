#!/usr/bin/env python3
"""Select a fail-closed provenance remediation path for the Qwen ONNX snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
ONNX_REPOSITORY = "onnx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice"
ONNX_UPLOAD_COMMIT = "0ac9e3de55c326eec31a3cdf3b2dcd98cc86ff82"
OFFICIAL_MODEL_COMMIT = "6c3e96b6a2c593ce3e546ee699a5d944de81850e"
MODEL_WEIGHTS_BYTES = 3_833_402_552
TOKENIZER_WEIGHTS_BYTES = 682_293_092


def _runtime_effects() -> dict[str, bool]:
    return {
        "downloaded_files": False,
        "executed_converter": False,
        "executed_onnx_graphs": False,
        "replaced_current_snapshot": False,
        "used_gpu": False,
        "played_audio": False,
        "wrote_global_memory": False,
        "wrote_forum": False,
    }


def _safe_s5o(receipt: dict[str, Any]) -> bool:
    provenance = receipt.get("converter_provenance", {})
    return all(
        (
            receipt.get("schema")
            == "agent_bridge.voice_config_provenance_gate.v1",
            receipt.get("official_model_id") == MODEL_ID,
            receipt.get("status")
            == "configuration_compatible_provenance_incomplete",
            receipt.get("config_graph_compatible") is True,
            receipt.get("reference_generation_ready") is False,
            provenance.get("declared_model_id") == MODEL_ID,
            provenance.get("declared_source_revision") is None,
        )
    )


def build_decision(
    s5o_receipt: dict[str, Any],
    public_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Build a decision only; never download, execute, or mutate model files."""
    base = {
        "schema": "agent_bridge.voice_provenance_remediation_decision.v1",
        "official_model_id": MODEL_ID,
        "reference_generation_ready": False,
        "runtime_effects": _runtime_effects(),
    }
    if not _safe_s5o(s5o_receipt):
        return {
            **base,
            "status": "blocked",
            "selected_path": None,
            "path_a": None,
            "path_b": None,
            "blockers": ["s5o_receipt_not_safe_incomplete"],
        }

    source_revision = public_evidence.get("declared_base_model_revision")
    artifact_bound = public_evidence.get("artifact_bound_attestation") is True
    path_a_closable = bool(source_revision) and artifact_bound
    path_a = {
        "name": "recover_artifact_lineage",
        "status": (
            "artifact_bound_lineage_available"
            if path_a_closable
            else "published_evidence_insufficient"
        ),
        "onnx_repository": public_evidence.get("onnx_repository"),
        "onnx_upload_commit": public_evidence.get("onnx_upload_commit"),
        "declared_base_model_id": public_evidence.get(
            "declared_base_model_id"
        ),
        "declared_base_model_revision": source_revision,
        "artifact_bound_attestation": artifact_bound,
        "can_close_lineage": path_a_closable,
    }
    path_b = {
        "name": "fixed_source_reexport",
        "status": (
            "fallback_not_started"
            if path_a_closable
            else "selected_not_started"
        ),
        "official_model_commit": OFFICIAL_MODEL_COMMIT,
        "minimum_weight_payload": {
            "model_safetensors_bytes": MODEL_WEIGHTS_BYTES,
            "speech_tokenizer_weights_bytes": TOKENIZER_WEIGHTS_BYTES,
            "total_bytes": MODEL_WEIGHTS_BYTES + TOKENIZER_WEIGHTS_BYTES,
        },
        "stages": [
            "B0_acquire_and_hash_fixed_revision_small_files",
            "B1_authorize_and_acquire_fixed_revision_weights",
            "B2_audit_and_pin_isolated_export_toolchain",
            "B3_export_cpu_fp32_reference_lane",
            "B4_verify_component_and_full_greedy_parity_then_quantization",
            "B5_separately_authorize_snapshot_adoption",
        ],
        "owner_authorization_required_before_weights": True,
    }
    if path_a_closable:
        return {
            **base,
            "status": "artifact_lineage_recovery_available",
            "selected_path": "A_recover_artifact_lineage",
            "path_a": path_a,
            "path_b": path_b,
            "blockers": [
                "artifact_lineage_verification_not_executed",
                "parity_not_reverified",
            ],
        }
    return {
        **base,
        "status": "fixed_source_reexport_selected_authorization_required",
        "selected_path": "B_fixed_source_reexport",
        "path_a": path_a,
        "path_b": path_b,
        "blockers": [
            "converter_artifact_bound_attestation_missing",
            "fixed_revision_small_files_not_locally_acquired",
            "fixed_revision_weights_not_authorized",
            "fixed_source_reexport_not_executed",
            "parity_not_reverified",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Choose a provenance remediation path without model effects"
    )
    parser.add_argument("--s5o-receipt", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    evidence = {
        "onnx_repository": ONNX_REPOSITORY,
        "onnx_upload_commit": ONNX_UPLOAD_COMMIT,
        "declared_base_model_id": MODEL_ID,
        "declared_base_model_revision": None,
        "artifact_bound_attestation": False,
    }
    decision = build_decision(
        json.loads(args.s5o_receipt.read_text()), evidence
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(decision, ensure_ascii=False))
    return 0 if decision["selected_path"] is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
