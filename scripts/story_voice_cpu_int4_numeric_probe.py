#!/usr/bin/env python3
"""Run one bounded CPU INT4 codec-embedding graph with synthetic IDs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


MODEL_RELATIVE_PATH = Path("cpu_int4/codec_embed.onnx")


def _runtime_effects(executed: bool) -> dict[str, Any]:
    return {
        "created_inference_session": executed,
        "executed_graphs": executed,
        "execution_count": 2 if executed else 0,
        "generated_tokens": False,
        "rendered_audio": False,
        "played_audio": False,
        "used_gpu": False,
        "imported_community_python": False,
    }


def run_numeric_gate(
    snapshot: Path,
    *,
    owner_authorized: bool,
    runner: Callable[[Path, int], dict[str, Any]],
    timeout_seconds: int = 120,
    runtime_version: str = "unknown",
    runtime_executable: str = sys.executable,
) -> dict[str, Any]:
    base = {
        "schema": "agent_bridge.voice_cpu_int4_numeric_probe.v1",
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
            "blockers": ["codec_embed_model_missing"],
            "runtime_effects": _runtime_effects(False),
        }

    result = runner(model, timeout_seconds)
    blockers = []
    if result.get("status") != "numeric_probe_passed":
        blockers.append("numeric_probe_failed")
    else:
        output = result["output"]
        if not output.get("all_finite"):
            blockers.append("nonfinite_output")
        if not output.get("deterministic"):
            blockers.append("nondeterministic_output")
    return {
        **base,
        "status": "blocked" if blockers else "numeric_probe_passed_no_audio",
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
            "status": "numeric_probe_failed",
            "error_type": "TimeoutExpired",
            "error": f"numeric probe exceeded {timeout_seconds}s",
        }
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "status": "numeric_probe_failed",
            "error_type": "ChildProcessError",
            "error": (completed.stderr or "child failed")[-1000:],
        }


def _array_hash(value: Any) -> str:
    import numpy as np

    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


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
        if len(inputs) != 1 or (
            inputs[0].name,
            inputs[0].type,
            len(inputs[0].shape),
        ) != ("codec_ids", "tensor(int64)", 2):
            raise ValueError("unexpected_codec_embed_input_contract")
        if len(outputs) != 1 or len(outputs[0].shape) != 3:
            raise ValueError("unexpected_codec_embed_output_contract")

        values = np.array([[0, 1, 2, 3]], dtype=np.int64)
        first = session.run(None, {"codec_ids": values})[0]
        second = session.run(None, {"codec_ids": values})[0]
        first_hash = _array_hash(first)
        second_hash = _array_hash(second)
        result = {
            "status": "numeric_probe_passed",
            "input": {
                "name": inputs[0].name,
                "dtype": inputs[0].type,
                "shape": list(values.shape),
                "values": values.reshape(-1).tolist(),
            },
            "output": {
                "name": outputs[0].name,
                "dtype": str(first.dtype),
                "shape": list(first.shape),
                "all_finite": bool(np.isfinite(first).all()),
                "minimum": float(np.min(first)),
                "maximum": float(np.max(first)),
                "mean": float(np.mean(first)),
                "sha256_run_1": first_hash,
                "sha256_run_2": second_hash,
                "deterministic": first_hash == second_hash,
            },
        }
        code = 0
    except Exception as error:
        result = {
            "status": "numeric_probe_failed",
            "error_type": type(error).__name__,
            "error": str(error)[-1000:],
        }
        code = 2
    print(json.dumps(result, ensure_ascii=False))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a bounded CPU INT4 codec-embedding numeric probe"
    )
    parser.add_argument("--child", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--owner-authorized", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    if args.child:
        return child_probe(args.child)
    if args.snapshot is None or args.receipt is None:
        parser.error("--snapshot and --receipt are required")

    import onnxruntime as ort

    receipt = run_numeric_gate(
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
    return 0 if receipt["status"] == "numeric_probe_passed_no_audio" else 2


if __name__ == "__main__":
    raise SystemExit(main())
