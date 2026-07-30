#!/usr/bin/env python3
"""Run exactly two CPU INT4 talker steps with one bounded KV feedback."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


MODEL_RELATIVE_PATH = Path("cpu_int4/talker_cache.onnx")
KV_COUNT = 56


def _runtime_effects(
    executed: bool, feedback_verified: bool = False
) -> dict[str, Any]:
    return {
        "created_inference_session": executed,
        "executed_graphs": executed,
        "execution_count": 4 if feedback_verified else 0,
        "produced_kv_cache": feedback_verified,
        "fed_back_kv_cache": feedback_verified,
        "cache_feedback_count_per_sequence": 1 if feedback_verified else 0,
        "sampled_codec_ids": False,
        "generated_tokens": False,
        "rendered_audio": False,
        "played_audio": False,
        "used_gpu": False,
        "imported_community_python": False,
    }


def run_cache_feedback_gate(
    snapshot: Path,
    *,
    owner_authorized: bool,
    runner: Callable[[Path, int], dict[str, Any]],
    timeout_seconds: int = 300,
    runtime_version: str = "unknown",
    runtime_executable: str = sys.executable,
) -> dict[str, Any]:
    base = {
        "schema": "agent_bridge.voice_cpu_int4_cache_feedback_probe.v1",
        "snapshot": str(snapshot.resolve()),
        "model": MODEL_RELATIVE_PATH.as_posix(),
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
    model = snapshot / MODEL_RELATIVE_PATH
    if not model.is_file():
        return {
            **base,
            "status": "blocked",
            "probe": None,
            "blockers": ["talker_cache_model_missing"],
            "runtime_effects": _runtime_effects(False),
        }

    result = runner(model, timeout_seconds)
    blockers: list[str] = []
    feedback_verified = result.get("status") == "cache_feedback_probe_passed"
    if not feedback_verified:
        blockers.append("cache_feedback_probe_failed")
    else:
        first = result["first_step"]
        second = result["second_step"]
        if (
            first["past_length"] != 0
            or first["present_cache"].get("count") != KV_COUNT
            or first["present_cache"].get("all_shapes")
            != [[1, 8, 1, 128]]
            or not first["present_cache"].get("all_finite")
        ):
            blockers.append("first_cache_contract_mismatch")
        if (
            second["past_length"] != 1
            or second["present_cache"].get("count") != KV_COUNT
            or second["present_cache"].get("all_shapes")
            != [[1, 8, 2, 128]]
            or not second["present_cache"].get("all_finite")
        ):
            blockers.append("second_cache_growth_mismatch")
        if (
            not second["logits"].get("all_finite")
            or not second["hidden"].get("all_finite")
        ):
            blockers.append("nonfinite_second_step_output")
        if not second["logits"].get("nonzero"):
            blockers.append("degenerate_second_step_logits")
        if not result.get("deterministic"):
            blockers.append("nondeterministic_sequence")
    return {
        **base,
        "status": (
            "blocked"
            if blockers
            else "talker_cache_feedback_passed_no_sampling"
        ),
        "probe": result,
        "blockers": blockers,
        "runtime_effects": _runtime_effects(
            executed=feedback_verified,
            feedback_verified=feedback_verified,
        ),
    }


def subprocess_runner(path: Path, timeout_seconds: int) -> dict[str, Any]:
    environment = {
        **os.environ,
        "CUDA_VISIBLE_DEVICES": "",
        "HIP_VISIBLE_DEVICES": "",
        "ROCR_VISIBLE_DEVICES": "",
    }
    try:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--child", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "cache_feedback_probe_failed",
            "error_type": "TimeoutExpired",
            "error": f"cache feedback probe exceeded {timeout_seconds}s",
        }
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "status": "cache_feedback_probe_failed",
            "error_type": "ChildProcessError",
            "error": (completed.stderr or "child failed")[-1000:],
        }


def _sequence_hash(names: list[str], steps: list[list[Any]]) -> str:
    import numpy as np

    digest = hashlib.sha256()
    for step_index, values in enumerate(steps):
        digest.update(f"step:{step_index}".encode())
        for name, value in zip(names, values):
            array = np.ascontiguousarray(value)
            digest.update(name.encode())
            digest.update(str(array.dtype).encode())
            digest.update(json.dumps(list(array.shape)).encode())
            digest.update(array.tobytes())
    return digest.hexdigest()


def _step_summary(values: list[Any], past_length: int) -> dict[str, Any]:
    import numpy as np

    cache = values[2:]
    cache_shapes = sorted({tuple(value.shape) for value in cache})
    return {
        "past_length": past_length,
        "logits": {
            "shape": list(values[0].shape),
            "dtype": str(values[0].dtype),
            "all_finite": bool(np.isfinite(values[0]).all()),
            "nonzero": bool(np.any(values[0] != 0)),
            "minimum": float(np.min(values[0])),
            "maximum": float(np.max(values[0])),
            "mean": float(np.mean(values[0])),
        },
        "hidden": {
            "shape": list(values[1].shape),
            "dtype": str(values[1].dtype),
            "all_finite": bool(np.isfinite(values[1]).all()),
        },
        "present_cache": {
            "count": len(cache),
            "all_shapes": [list(shape) for shape in cache_shapes],
            "all_finite": all(
                bool(np.isfinite(value).all()) for value in cache
            ),
        },
    }


def child_probe(path: Path) -> int:
    try:
        import numpy as np
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(
            str(path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        inputs = session.get_inputs()
        outputs = session.get_outputs()
        if len(inputs) != 59 or len(outputs) != 58:
            raise ValueError("unexpected_talker_cache_io_count")
        head_contract = [
            ("inputs_embeds", "tensor(float)", 3),
            ("position_ids", "tensor(int64)", 3),
            ("attention_mask", "tensor(int64)", 2),
        ]
        for row, expected in zip(inputs[:3], head_contract):
            if (row.name, row.type, len(row.shape)) != expected:
                raise ValueError(f"unexpected_{expected[0]}_contract")
        if len(inputs[3:]) != KV_COUNT:
            raise ValueError("unexpected_kv_input_count")
        if any(row.type != "tensor(float)" for row in inputs[3:]):
            raise ValueError("unexpected_kv_input_dtype")

        first_embedding = np.linspace(
            -0.01, 0.01, 2048, dtype=np.float32
        ).reshape(1, 1, 2048)
        second_embedding = np.linspace(
            0.01, -0.01, 2048, dtype=np.float32
        ).reshape(1, 1, 2048)

        def run_sequence() -> list[list[Any]]:
            first_feed = {
                "inputs_embeds": first_embedding,
                "position_ids": np.zeros((3, 1, 1), dtype=np.int64),
                "attention_mask": np.ones((1, 1), dtype=np.int64),
            }
            for row in inputs[3:]:
                first_feed[row.name] = np.zeros(
                    (1, 8, 0, 128), dtype=np.float32
                )
            first = session.run(None, first_feed)
            if len(first[2:]) != KV_COUNT:
                raise ValueError("unexpected_first_present_count")

            second_feed = {
                "inputs_embeds": second_embedding,
                "position_ids": np.ones((3, 1, 1), dtype=np.int64),
                "attention_mask": np.ones((1, 2), dtype=np.int64),
            }
            for row, present in zip(inputs[3:], first[2:]):
                second_feed[row.name] = present
            second = session.run(None, second_feed)
            return [first, second]

        sequence_1 = run_sequence()
        sequence_2 = run_sequence()
        output_names = [row.name for row in outputs]
        hash_1 = _sequence_hash(output_names, sequence_1)
        hash_2 = _sequence_hash(output_names, sequence_2)
        result = {
            "status": "cache_feedback_probe_passed",
            "sequence_contract": {
                "sequence_count": 2,
                "steps_per_sequence": 2,
                "first_position": 0,
                "second_position": 1,
                "second_attention_length": 2,
                "first_embedding_fixture": "bounded_linear_-0.01_0.01",
                "second_embedding_fixture": "bounded_linear_0.01_-0.01",
            },
            "first_step": _step_summary(sequence_1[0], 0),
            "second_step": _step_summary(sequence_1[1], 1),
            "sha256_sequence_1": hash_1,
            "sha256_sequence_2": hash_2,
            "deterministic": hash_1 == hash_2,
        }
        code = 0
    except Exception as error:
        result = {
            "status": "cache_feedback_probe_failed",
            "error_type": type(error).__name__,
            "error": str(error)[-1000:],
        }
        code = 2
    print(json.dumps(result, ensure_ascii=False))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one bounded CPU INT4 talker cache feedback step"
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

    receipt = run_cache_feedback_gate(
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
        if receipt["status"] == "talker_cache_feedback_passed_no_sampling"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
