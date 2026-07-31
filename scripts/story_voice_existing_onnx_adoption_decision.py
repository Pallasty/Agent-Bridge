#!/usr/bin/env python3
"""Select the existing ONNX trial lane without converting or rendering."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_VARIANTS = {
    "cpu_fp16",
    "cpu_fp32",
    "cpu_int4",
    "cuda_fp16",
    "cuda_fp32",
    "cuda_int4",
}
RUNTIME_MODULES = (
    "onnxruntime",
    "numpy",
    "transformers",
    "soundfile",
    "librosa",
)


def _six_variants_valid(snapshot: dict[str, Any]) -> bool:
    inventory = snapshot.get("inventory", {})
    listed = inventory.get("variants")
    if isinstance(listed, list):
        return set(listed) == REQUIRED_VARIANTS and not inventory.get(
            "incomplete_files", []
        )
    variants = snapshot.get("variants", {})
    return set(variants) == REQUIRED_VARIANTS and all(
        row.get("manifest_valid") for row in variants.values()
    )


def decide(
    snapshot: dict[str, Any],
    session: dict[str, Any],
    single_frame: dict[str, Any],
    original: dict[str, Any],
    offline_lock: dict[str, Any],
    runtime_facts: dict[str, bool] | None = None,
) -> dict[str, Any]:
    if not _six_variants_valid(snapshot):
        raise ValueError("six-variant ONNX inventory evidence is required")
    probed = session.get("probed_models", [])
    if (
        session.get("status") != "session_creation_passed_no_inference"
        or session.get("provider") != "CPUExecutionProvider"
        or len(probed) != 7
        or any(row.get("status") != "session_created" for row in probed)
    ):
        raise ValueError("complete CPU session evidence is required")
    if (
        single_frame.get("status")
        != "single_codec_frame_loop_passed_no_audio"
    ):
        raise ValueError("passing single-frame evidence is required")
    if not original.get("weight_payload_fixed_revision_equivalent"):
        raise ValueError("fixed-revision-equivalent original weights are required")
    if (
        offline_lock.get("status")
        != "direct_lock_contract_ready_wheelhouse_pending"
    ):
        raise ValueError("S5S1 fallback contract is required")

    facts = {
        name: bool((runtime_facts or {}).get(name, False))
        for name in RUNTIME_MODULES
    }
    missing = [name for name in RUNTIME_MODULES if not facts[name]]
    supply_chain_blockers = [
        blocker
        for blocker in snapshot.get("blockers", [])
        if blocker
        in {
            "revision_not_immutable",
            "standalone_license_file_missing",
            "python_dangerous_primitives_present",
        }
    ]
    return {
        "schema": "agent_bridge.voice_existing_onnx_adoption_decision.v1",
        "status": "existing_onnx_trial_selected",
        "active_lane": "community_cpu_int4",
        "reexport_lane": "paused_fallback_only",
        "snapshot": snapshot["snapshot"],
        "existing_onnx_evidence": {
            "six_variant_manifests_valid": True,
            "cpu_int4_sessions_created": len(probed),
            "single_codec_frame_loop_passed": True,
            "end_to_end_text_to_wav_verified": False,
        },
        "original_model": {
            "snapshot": original["source"]["snapshot"],
            "role": (
                "immutable_weight_equivalent_fallback_and_future_reference"
            ),
            "loaded": False,
        },
        "runtime_gap": {
            "observed_modules": facts,
            "missing": missing,
            "multi_gb_conversion_wheelhouse_required": False,
            "dependency_install_authorized": False,
        },
        "paused_work": {
            "wheelhouse_materialization": True,
            "olive_installation": True,
            "fixed_source_reexport": True,
            "fp32_int4_reexport_parity": True,
            "resume_condition": (
                "existing_onnx_quality_compatibility_or_lineage_failure"
            ),
        },
        "claims": {
            "publisher_lineage_verified": False,
            "production_admitted": False,
            "end_to_end_text_to_wav_verified": False,
            "mi50_verified": False,
            "human_audibility_verified": False,
        },
        "supply_chain_blockers_retained": supply_chain_blockers,
        "next_gate": (
            "existing_onnx_minimal_runtime_and_bounded_text_to_wav_trial"
        ),
        "runtime_effects": {
            "downloaded_files": False,
            "installed_packages": False,
            "loaded_original_model": False,
            "executed_converter": False,
            "created_onnx": False,
            "executed_onnx_graphs": False,
            "rendered_audio": False,
            "played_audio": False,
            "used_gpu": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-receipt", type=Path, required=True)
    parser.add_argument("--session-receipt", type=Path, required=True)
    parser.add_argument("--single-frame-receipt", type=Path, required=True)
    parser.add_argument("--original-receipt", type=Path, required=True)
    parser.add_argument("--offline-lock-receipt", type=Path, required=True)
    parser.add_argument("--runtime-facts", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = decide(
        json.loads(args.snapshot_receipt.read_text()),
        json.loads(args.session_receipt.read_text()),
        json.loads(args.single_frame_receipt.read_text()),
        json.loads(args.original_receipt.read_text()),
        json.loads(args.offline_lock_receipt.read_text()),
        json.loads(args.runtime_facts.read_text()),
    )
    rendered = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
