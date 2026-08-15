#!/usr/bin/env python3
"""Probe one raw-greedy CPU INT4 codec frame without audio decoding."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


MODEL_FILENAMES = (
    "talker_cache.onnx",
    "code_predictor.onnx",
    "residual_embed.onnx",
)
KV_COUNT = 56


def _runtime_effects(passed: bool) -> dict[str, Any]:
    return {
        "created_inference_sessions": 3 if passed else 0,
        "execution_count": 36 if passed else 0,
        "talker_execution_count": 4 if passed else 0,
        "predictor_execution_count": 30 if passed else 0,
        "residual_embed_execution_count": 2 if passed else 0,
        "selected_codec_ids": passed,
        "sampled_codec_ids": False,
        "generated_codec_frame_count": 1 if passed else 0,
        "cache_feedback_count_per_sequence": 1 if passed else 0,
        "decoded_waveform": False,
        "rendered_audio": False,
        "played_audio": False,
        "used_gpu": False,
        "imported_community_python": False,
    }


def run_single_frame_loop_gate(
    snapshot: Path,
    *,
    owner_authorized: bool,
    runner: Callable[[dict[str, Path], int], dict[str, Any]],
    timeout_seconds: int = 300,
    runtime_version: str = "unknown",
    runtime_executable: str = sys.executable,
) -> dict[str, Any]:
    model_dir = snapshot / "cpu_int4"
    model_paths = {name: model_dir / name for name in MODEL_FILENAMES}
    base = {
        "schema": "agent_bridge.voice_cpu_int4_single_frame_loop_probe.v1",
        "snapshot": str(snapshot.resolve()),
        "models": [f"cpu_int4/{name}" for name in MODEL_FILENAMES],
        "runtime": {
            "name": "onnxruntime",
            "version": runtime_version,
            "executable": runtime_executable,
            "provider": "CPUExecutionProvider",
        },
    }
    if not owner_authorized:
        return {
            **base,
            "status": "blocked",
            "probe": None,
            "blockers": ["owner_authorization_required"],
            "runtime_effects": _runtime_effects(False),
        }
    missing = [name for name, path in model_paths.items() if not path.is_file()]
    if missing:
        return {
            **base,
            "status": "blocked",
            "probe": None,
            "blockers": ["required_model_missing"],
            "missing_models": missing,
            "runtime_effects": _runtime_effects(False),
        }

    result = runner(model_paths, timeout_seconds)
    blockers: list[str] = []
    passed = result.get("status") == "single_frame_loop_probe_passed"
    if not passed:
        blockers.append("single_frame_loop_probe_failed")
    else:
        selection = result["selection_contract"]
        if selection != {
            "policy": "raw_argmax_exported_logits_no_suppression",
            "local_model_config_present": False,
            "codec_eos_known": False,
            "reserved_token_suppression_applied": False,
            "reference_generation_equivalence_claimed": False,
        }:
            blockers.append("selection_contract_mismatch")
        frame = result["codec_frame"]
        ids = frame.get("ids", [])
        codec_ids_valid = (
            frame.get("shape") == [1, 16]
            and frame.get("dtype") == "int64"
            and len(ids) == 16
            and isinstance(ids[0], int)
            and 0 <= ids[0] < 3072
            and all(isinstance(value, int) and 0 <= value < 2048 for value in ids[1:])
        )
        if not codec_ids_valid:
            blockers.append("codec_frame_contract_mismatch")
        embedding = result["step_embedding"]
        if (
            embedding.get("shape") != [1, 2048]
            or embedding.get("dtype") != "float32"
            or not embedding.get("all_finite")
            or not embedding.get("nonzero")
        ):
            blockers.append("step_embedding_contract_mismatch")
        second = result["second_talker_step"]
        if (
            not second["logits"].get("all_finite")
            or not second["logits"].get("nonzero")
        ):
            blockers.append("second_talker_output_mismatch")
        if (
            second["present_cache"].get("count") != KV_COUNT
            or second["present_cache"].get("all_shapes")
            != [[1, 8, 2, 128]]
            or not second["present_cache"].get("all_finite")
        ):
            blockers.append("second_cache_growth_mismatch")
        if not result.get("deterministic"):
            blockers.append("nondeterministic_sequence")
    receipt = {
        **base,
        "status": (
            "blocked" if blockers else "single_codec_frame_loop_passed_no_audio"
        ),
        "probe": result,
        "blockers": blockers,
        "runtime_effects": _runtime_effects(passed and not blockers),
    }
    return receipt


def subprocess_runner(
    paths: dict[str, Path], timeout_seconds: int
) -> dict[str, Any]:
    environment = {
        **os.environ,
        "CUDA_VISIBLE_DEVICES": "",
        "HIP_VISIBLE_DEVICES": "",
        "ROCR_VISIBLE_DEVICES": "",
    }
    model_dir = next(iter(paths.values())).parent
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--child",
                str(model_dir),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "single_frame_loop_probe_failed",
            "error_type": "TimeoutExpired",
            "error": f"single frame loop exceeded {timeout_seconds}s",
        }
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "status": "single_frame_loop_probe_failed",
            "error_type": "ChildProcessError",
            "error": (completed.stderr or "child failed")[-1000:],
        }


def _update_hash(digest: Any, label: str, value: Any) -> None:
    import numpy as np

    array = np.ascontiguousarray(value)
    digest.update(label.encode())
    digest.update(str(array.dtype).encode())
    digest.update(json.dumps(list(array.shape)).encode())
    digest.update(array.tobytes())


def _session(path: Path) -> Any:
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return ort.InferenceSession(
        str(path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )


def child_probe(model_dir: Path) -> int:
    try:
        import numpy as np

        talker = _session(model_dir / "talker_cache.onnx")
        predictor = _session(model_dir / "code_predictor.onnx")
        residual = _session(model_dir / "residual_embed.onnx")
        talker_inputs = talker.get_inputs()
        if len(talker_inputs) != 59 or len(talker.get_outputs()) != 58:
            raise ValueError("unexpected_talker_cache_contract")
        if len(predictor.get_inputs()) != 2 or len(predictor.get_outputs()) != 1:
            raise ValueError("unexpected_code_predictor_contract")
        if len(residual.get_inputs()) != 1 or len(residual.get_outputs()) != 1:
            raise ValueError("unexpected_residual_embed_contract")

        def run_sequence() -> dict[str, Any]:
            digest = hashlib.sha256()
            first_feed = {
                "inputs_embeds": np.linspace(
                    -0.01, 0.01, 2048, dtype=np.float32
                ).reshape(1, 1, 2048),
                "position_ids": np.zeros((3, 1, 1), dtype=np.int64),
                "attention_mask": np.ones((1, 1), dtype=np.int64),
            }
            for row in talker_inputs[3:]:
                first_feed[row.name] = np.zeros(
                    (1, 8, 0, 128), dtype=np.float32
                )
            first = talker.run(None, first_feed)
            for index, value in enumerate(first):
                _update_hash(digest, f"first:{index}", value)

            codec_ids = np.zeros((1, 16), dtype=np.int64)
            codec_ids[0, 0] = int(np.argmax(first[0][0, -1]))
            hidden = first[1][0, -1][None].astype(np.float32)
            for group in range(1, 16):
                group_logits = predictor.run(
                    None,
                    {
                        "talker_hidden": hidden,
                        "codec_ids": codec_ids,
                    },
                )[0]
                _update_hash(digest, f"predictor:{group}", group_logits)
                codec_ids[0, group] = int(
                    np.argmax(group_logits[0, group - 1])
                )
            _update_hash(digest, "codec_ids", codec_ids)

            step_embed = residual.run(None, {"codec_ids": codec_ids})[0]
            _update_hash(digest, "step_embed", step_embed)
            second_feed = {
                "inputs_embeds": step_embed[:, None].astype(np.float32),
                "position_ids": np.ones((3, 1, 1), dtype=np.int64),
                "attention_mask": np.ones((1, 2), dtype=np.int64),
            }
            for row, present in zip(talker_inputs[3:], first[2:]):
                second_feed[row.name] = present
            second = talker.run(None, second_feed)
            for index, value in enumerate(second):
                _update_hash(digest, f"second:{index}", value)
            return {
                "codec_ids": codec_ids,
                "step_embed": step_embed,
                "second": second,
                "sha256": digest.hexdigest(),
            }

        first_sequence = run_sequence()
        second_sequence = run_sequence()
        codec_ids = first_sequence["codec_ids"]
        step_embed = first_sequence["step_embed"]
        second = first_sequence["second"]
        second_cache = second[2:]
        cache_shapes = sorted({tuple(value.shape) for value in second_cache})
        hash_1 = first_sequence["sha256"]
        hash_2 = second_sequence["sha256"]
        result = {
            "status": "single_frame_loop_probe_passed",
            "selection_contract": {
                "policy": "raw_argmax_exported_logits_no_suppression",
                "local_model_config_present": (model_dir.parent / "config.json").is_file(),
                "codec_eos_known": False,
                "reserved_token_suppression_applied": False,
                "reference_generation_equivalence_claimed": False,
            },
            "codec_frame": {
                "shape": list(codec_ids.shape),
                "dtype": str(codec_ids.dtype),
                "ids": codec_ids[0].tolist(),
                "first_group_vocab": 3072,
                "residual_group_vocab": 2048,
            },
            "step_embedding": {
                "shape": list(step_embed.shape),
                "dtype": str(step_embed.dtype),
                "all_finite": bool(np.isfinite(step_embed).all()),
                "nonzero": bool(np.any(step_embed != 0)),
                "minimum": float(np.min(step_embed)),
                "maximum": float(np.max(step_embed)),
                "mean": float(np.mean(step_embed)),
            },
            "second_talker_step": {
                "logits": {
                    "shape": list(second[0].shape),
                    "dtype": str(second[0].dtype),
                    "all_finite": bool(np.isfinite(second[0]).all()),
                    "nonzero": bool(np.any(second[0] != 0)),
                    "minimum": float(np.min(second[0])),
                    "maximum": float(np.max(second[0])),
                    "mean": float(np.mean(second[0])),
                },
                "present_cache": {
                    "count": len(second_cache),
                    "all_shapes": [list(shape) for shape in cache_shapes],
                    "all_finite": all(
                        bool(np.isfinite(value).all())
                        for value in second_cache
                    ),
                },
            },
            "sha256_sequence_1": hash_1,
            "sha256_sequence_2": hash_2,
            "deterministic": (
                hash_1 == hash_2
                and np.array_equal(
                    first_sequence["codec_ids"],
                    second_sequence["codec_ids"],
                )
            ),
        }
        code = 0
    except Exception as error:
        result = {
            "status": "single_frame_loop_probe_failed",
            "error_type": type(error).__name__,
            "error": str(error)[-1000:],
        }
        code = 2
    print(json.dumps(result, ensure_ascii=False))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one raw-greedy CPU INT4 codec-frame loop"
    )
    parser.add_argument("--child", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--owner-authorized", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if args.child:
        return child_probe(args.child)
    if args.snapshot is None or args.receipt is None:
        parser.error("--snapshot and --receipt are required")

    import onnxruntime as ort

    receipt = run_single_frame_loop_gate(
        args.snapshot,
        owner_authorized=args.owner_authorized,
        runner=subprocess_runner,
        timeout_seconds=args.timeout_seconds,
        runtime_version=ort.__version__,
        runtime_executable=sys.executable,
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    return (
        0
        if receipt["status"] == "single_codec_frame_loop_passed_no_audio"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
