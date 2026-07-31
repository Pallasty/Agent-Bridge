#!/usr/bin/env python3
"""Reconcile a hash-bound Qwen config with ONNX metadata, fail closed on provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable


MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
MODEL_FILENAMES = (
    "talker_cache.onnx",
    "code_predictor.onnx",
    "residual_embed.onnx",
)
HF_CONFIG_COMMIT = "6c3e96b6a2c593ce3e546ee699a5d944de81850e"
HF_CONFIG_URL = (
    "https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/"
    f"blob/{HF_CONFIG_COMMIT}/config.json"
)


def _runtime_effects(created_sessions: bool) -> dict[str, Any]:
    return {
        "created_inference_sessions": 3 if created_sessions else 0,
        "executed_graphs": False,
        "downloaded_weights": False,
        "generated_codec_frames": False,
        "decoded_waveform": False,
        "played_audio": False,
        "used_gpu": False,
        "imported_community_python": False,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _config_contract(config: dict[str, Any]) -> dict[str, Any]:
    talker = config["talker_config"]
    predictor = talker["code_predictor_config"]
    return {
        "model_size": config.get("tts_model_size"),
        "model_type": config.get("tts_model_type"),
        "talker_vocab_size": talker.get("vocab_size"),
        "talker_hidden_size": talker.get("hidden_size"),
        "num_code_groups": talker.get("num_code_groups"),
        "num_hidden_layers": talker.get("num_hidden_layers"),
        "num_key_value_heads": talker.get("num_key_value_heads"),
        "head_dim": talker.get("head_dim"),
        "codec_pad_id": talker.get("codec_pad_id"),
        "codec_bos_id": talker.get("codec_bos_id"),
        "codec_eos_token_id": talker.get("codec_eos_token_id"),
        "predictor_vocab_size": predictor.get("vocab_size"),
        "predictor_hidden_size": predictor.get("hidden_size"),
        "predictor_num_code_groups": predictor.get("num_code_groups"),
    }


def _contracts_match(
    config: dict[str, Any], graphs: dict[str, Any]
) -> bool:
    talker = graphs["talker_cache"]
    predictor = graphs["code_predictor"]
    residual = graphs["residual_embed"]
    return all(
        (
            config["model_size"] == "1b7",
            config["model_type"] == "custom_voice",
            config["talker_vocab_size"] == talker["logits_width"] == 3072,
            config["talker_hidden_size"] == talker["hidden_width"] == 2048,
            config["num_code_groups"] == 16,
            config["num_hidden_layers"] * 2 == talker["kv_input_count"] == 56,
            config["num_key_value_heads"] == talker["kv_heads"] == 8,
            config["head_dim"] == talker["head_dim"] == 128,
            config["predictor_vocab_size"]
            == predictor["logits_width"]
            == 2048,
            config["talker_hidden_size"]
            == predictor["hidden_width"]
            == 2048,
            config["predictor_num_code_groups"] - 1
            == predictor["group_count"]
            == 15,
            predictor["codec_input_width"] == 16,
            residual["codec_input_width"] == 16,
            config["talker_hidden_size"]
            == residual["output_width"]
            == 2048,
            config["codec_pad_id"] == 2148,
            config["codec_bos_id"] == 2149,
            config["codec_eos_token_id"] == 2150,
        )
    )


def run_config_provenance_gate(
    snapshot: Path,
    config_path: Path,
    *,
    expected_config_sha256: str,
    owner_authorized: bool,
    inspector: Callable[[dict[str, Path]], dict[str, Any]],
    fixed_huggingface_config_locally_acquired: bool = False,
) -> dict[str, Any]:
    model_dir = snapshot / "cpu_int4"
    model_paths = {name: model_dir / name for name in MODEL_FILENAMES}
    status_path = snapshot / "STATUS.md"
    base = {
        "schema": "agent_bridge.voice_config_provenance_gate.v1",
        "snapshot": str(snapshot.resolve()),
        "official_model_id": MODEL_ID,
        "official_config": {
            "observed_provider": "modelscope",
            "observed_revision": "master",
            "observed_revision_immutable": False,
            "path": str(config_path.resolve()),
            "expected_sha256": expected_config_sha256,
            "fixed_huggingface_commit": HF_CONFIG_COMMIT,
            "fixed_huggingface_url": HF_CONFIG_URL,
            "fixed_huggingface_config_locally_acquired": (
                fixed_huggingface_config_locally_acquired
            ),
        },
        "converter_provenance": {
            "declared_model_id": MODEL_ID,
            "declared_source_revision": None,
            "status_path": str(status_path.resolve()),
        },
    }
    if not owner_authorized:
        return {
            **base,
            "status": "blocked",
            "config_graph_compatible": None,
            "reference_generation_ready": False,
            "config_contract": None,
            "graph_contracts": None,
            "blockers": ["owner_authorization_required"],
            "runtime_effects": _runtime_effects(False),
        }
    if not config_path.is_file():
        return {
            **base,
            "status": "blocked",
            "config_graph_compatible": None,
            "reference_generation_ready": False,
            "config_contract": None,
            "graph_contracts": None,
            "blockers": ["official_config_missing"],
            "runtime_effects": _runtime_effects(False),
        }
    actual_sha256 = _sha256(config_path)
    base["official_config"]["actual_sha256"] = actual_sha256
    if actual_sha256 != expected_config_sha256:
        return {
            **base,
            "status": "blocked",
            "config_graph_compatible": None,
            "reference_generation_ready": False,
            "config_contract": None,
            "graph_contracts": None,
            "blockers": ["official_config_hash_mismatch"],
            "runtime_effects": _runtime_effects(False),
        }
    missing = [name for name, path in model_paths.items() if not path.is_file()]
    if missing:
        return {
            **base,
            "status": "blocked",
            "config_graph_compatible": None,
            "reference_generation_ready": False,
            "config_contract": None,
            "graph_contracts": None,
            "missing_models": missing,
            "blockers": ["required_model_missing"],
            "runtime_effects": _runtime_effects(False),
        }

    config = json.loads(config_path.read_text())
    contract = _config_contract(config)
    graphs = inspector(model_paths)
    compatible = _contracts_match(contract, graphs)
    status_text = status_path.read_text() if status_path.is_file() else ""
    identity_declared = MODEL_ID in status_text
    blockers = []
    if not identity_declared:
        blockers.append("converter_model_identity_missing")
    if not compatible:
        blockers.append("config_graph_contract_mismatch")
    blockers.append("converter_source_revision_missing")
    blockers.append("observed_modelscope_revision_mutable")
    if not fixed_huggingface_config_locally_acquired:
        blockers.append("fixed_huggingface_config_not_locally_acquired")
    safe_incomplete = compatible and identity_declared
    return {
        **base,
        "status": (
            "configuration_compatible_provenance_incomplete"
            if safe_incomplete
            else "blocked"
        ),
        "config_graph_compatible": compatible,
        "reference_generation_ready": False,
        "config_contract": contract,
        "graph_contracts": graphs,
        "blockers": blockers,
        "runtime_effects": _runtime_effects(True),
    }


def inspect_graph_contracts(paths: dict[str, Path]) -> dict[str, Any]:
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1

    def session(name: str):
        return ort.InferenceSession(
            str(paths[name]),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )

    talker = session("talker_cache.onnx")
    predictor = session("code_predictor.onnx")
    residual = session("residual_embed.onnx")
    talker_inputs = talker.get_inputs()
    talker_outputs = talker.get_outputs()
    predictor_inputs = predictor.get_inputs()
    predictor_outputs = predictor.get_outputs()
    residual_inputs = residual.get_inputs()
    residual_outputs = residual.get_outputs()
    return {
        "talker_cache": {
            "logits_width": talker_outputs[0].shape[-1],
            "hidden_width": talker_outputs[1].shape[-1],
            "kv_input_count": len(talker_inputs[3:]),
            "kv_heads": talker_inputs[3].shape[1],
            "head_dim": talker_inputs[3].shape[-1],
        },
        "code_predictor": {
            "group_count": predictor_outputs[0].shape[-2],
            "logits_width": predictor_outputs[0].shape[-1],
            "hidden_width": predictor_inputs[0].shape[-1],
            "codec_input_width": predictor_inputs[1].shape[-1],
        },
        "residual_embed": {
            "codec_input_width": residual_inputs[0].shape[-1],
            "output_width": residual_outputs[0].shape[-1],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile Qwen configuration provenance with ONNX metadata"
    )
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-config-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--owner-authorized", action="store_true")
    parser.add_argument(
        "--fixed-huggingface-config-locally-acquired",
        action="store_true",
    )
    args = parser.parse_args()
    receipt = run_config_provenance_gate(
        args.snapshot,
        args.config,
        expected_config_sha256=args.expected_config_sha256,
        owner_authorized=args.owner_authorized,
        inspector=inspect_graph_contracts,
        fixed_huggingface_config_locally_acquired=(
            args.fixed_huggingface_config_locally_acquired
        ),
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    return (
        0
        if receipt["status"]
        == "configuration_compatible_provenance_incomplete"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
