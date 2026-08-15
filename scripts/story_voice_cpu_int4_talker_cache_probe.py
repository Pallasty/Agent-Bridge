#!/usr/bin/env python3
"""Run one bounded zero-cache CPU INT4 talker step without feedback."""

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


def _runtime_effects(executed: bool) -> dict[str, Any]:
    return {
        "created_inference_session": executed,
        "executed_graphs": executed,
        "execution_count": 2 if executed else 0,
        "produced_kv_cache": executed,
        "fed_back_kv_cache": False,
        "sampled_codec_ids": False,
        "generated_tokens": False,
        "rendered_audio": False,
        "played_audio": False,
        "used_gpu": False,
        "imported_community_python": False,
    }


def run_talker_gate(
    snapshot: Path,
    *,
    owner_authorized: bool,
    runner: Callable[[Path, int], dict[str, Any]],
    timeout_seconds: int = 300,
    runtime_version: str = "unknown",
    runtime_executable: str = sys.executable,
) -> dict[str, Any]:
    base = {
        "schema": "agent_bridge.voice_cpu_int4_talker_cache_probe.v1",
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
    blockers = []
    if result.get("status") != "talker_cache_probe_passed":
        blockers.append("talker_cache_probe_failed")
    else:
        if (
            result["present_cache"].get("count") != KV_COUNT
            or result["present_cache"].get("all_shapes") != [[1, 8, 1, 128]]
            or not result["present_cache"].get("all_finite")
        ):
            blockers.append("present_cache_contract_mismatch")
        if (
            not result["logits"].get("all_finite")
            or not result["hidden"].get("all_finite")
        ):
            blockers.append("nonfinite_output")
        if not result["logits"].get("nonzero"):
            blockers.append("degenerate_zero_logits")
        if not result.get("deterministic"):
            blockers.append("nondeterministic_output")
    return {
        **base,
        "status": (
            "blocked"
            if blockers
            else "talker_single_step_passed_no_sampling"
        ),
        "probe": result,
        "blockers": blockers,
        "runtime_effects": _runtime_effects(True),
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
            "status": "talker_cache_probe_failed",
            "error_type": "TimeoutExpired",
            "error": f"talker cache probe exceeded {timeout_seconds}s",
        }
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "status": "talker_cache_probe_failed",
            "error_type": "ChildProcessError",
            "error": (completed.stderr or "child failed")[-1000:],
        }


def _outputs_hash(names: list[str], values: list[Any]) -> str:
    import numpy as np

    digest = hashlib.sha256()
    for name, value in zip(names, values):
        array = np.ascontiguousarray(value)
        digest.update(name.encode())
        digest.update(str(array.dtype).encode())
        digest.update(json.dumps(list(array.shape)).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


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

        feed = {
            "inputs_embeds": np.linspace(
                -0.01,
                0.01,
                2048,
                dtype=np.float32,
            ).reshape(1, 1, 2048),
            "position_ids": np.zeros((3, 1, 1), dtype=np.int64),
            "attention_mask": np.ones((1, 1), dtype=np.int64),
        }
        for row in inputs[3:]:
            feed[row.name] = np.zeros((1, 8, 0, 128), dtype=np.float32)
        first = session.run(None, feed)
        second = session.run(None, feed)
        output_names = [row.name for row in outputs]
        first_hash = _outputs_hash(output_names, first)
        second_hash = _outputs_hash(output_names, second)
        cache = first[2:]
        cache_shapes = sorted({tuple(value.shape) for value in cache})
        result = {
            "status": "talker_cache_probe_passed",
            "input_contract": {
                "input_count": len(inputs),
                "current_length": 1,
                "past_length": 0,
                "kv_input_count": len(inputs[3:]),
                "embedding_fixture": "bounded_linear_-0.01_0.01",
            },
            "logits": {
                "shape": list(first[0].shape),
                "dtype": str(first[0].dtype),
                "all_finite": bool(np.isfinite(first[0]).all()),
                "nonzero": bool(np.any(first[0] != 0)),
                "minimum": float(np.min(first[0])),
                "maximum": float(np.max(first[0])),
                "mean": float(np.mean(first[0])),
            },
            "hidden": {
                "shape": list(first[1].shape),
                "dtype": str(first[1].dtype),
                "all_finite": bool(np.isfinite(first[1]).all()),
            },
            "present_cache": {
                "count": len(cache),
                "all_shapes": [list(shape) for shape in cache_shapes],
                "all_finite": all(
                    bool(np.isfinite(value).all()) for value in cache
                ),
            },
            "sha256_run_1": first_hash,
            "sha256_run_2": second_hash,
            "deterministic": first_hash == second_hash,
        }
        code = 0
    except Exception as error:
        result = {
            "status": "talker_cache_probe_failed",
            "error_type": type(error).__name__,
            "error": str(error)[-1000:],
        }
        code = 2
    print(json.dumps(result, ensure_ascii=False))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one bounded zero-cache CPU INT4 talker step"
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

    receipt = run_talker_gate(
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
        if receipt["status"] == "talker_single_step_passed_no_sampling"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
