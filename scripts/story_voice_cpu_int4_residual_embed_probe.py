#!/usr/bin/env python3
"""Probe CPU INT4 residual embedding without forwarding its output."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


MODEL_RELATIVE_PATH = Path("cpu_int4/residual_embed.onnx")
CODEC_FIXTURE = list(range(16))


def _runtime_effects(executed: bool) -> dict[str, Any]:
    return {
        "created_inference_session": executed,
        "executed_graphs": executed,
        "execution_count": 2 if executed else 0,
        "forwarded_step_embedding": False,
        "generated_codec_frame": False,
        "decoded_waveform": False,
        "played_audio": False,
        "used_gpu": False,
        "imported_community_python": False,
    }


def run_residual_embed_gate(
    snapshot: Path,
    *,
    owner_authorized: bool,
    runner: Callable[[Path, int], dict[str, Any]],
    timeout_seconds: int = 300,
    runtime_version: str = "unknown",
    runtime_executable: str = sys.executable,
) -> dict[str, Any]:
    base = {
        "schema": "agent_bridge.voice_cpu_int4_residual_embed_probe.v1",
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
            "blockers": ["residual_embed_model_missing"],
            "runtime_effects": _runtime_effects(False),
        }

    result = runner(model, timeout_seconds)
    blockers: list[str] = []
    passed = result.get("status") == "residual_embed_probe_passed"
    if not passed:
        blockers.append("residual_embed_probe_failed")
    else:
        output = result["output"]
        if (
            output.get("name") != "step_embed"
            or output.get("shape") != [1, 2048]
            or output.get("dtype") != "float32"
        ):
            blockers.append("output_contract_mismatch")
        if not output.get("all_finite"):
            blockers.append("nonfinite_output")
        if not output.get("nonzero"):
            blockers.append("degenerate_zero_output")
        if not result.get("deterministic"):
            blockers.append("nondeterministic_output")
    return {
        **base,
        "status": (
            "blocked"
            if blockers
            else "residual_embed_probe_passed_no_forwarding"
        ),
        "probe": result,
        "blockers": blockers,
        "runtime_effects": _runtime_effects(passed),
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
            "status": "residual_embed_probe_failed",
            "error_type": "TimeoutExpired",
            "error": f"residual embed probe exceeded {timeout_seconds}s",
        }
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "status": "residual_embed_probe_failed",
            "error_type": "ChildProcessError",
            "error": (completed.stderr or "child failed")[-1000:],
        }


def _array_hash(name: str, value: Any) -> str:
    import numpy as np

    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
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
        if len(inputs) != 1 or len(outputs) != 1:
            raise ValueError("unexpected_residual_embed_io_count")
        if (
            inputs[0].name,
            inputs[0].type,
            len(inputs[0].shape),
        ) != ("codec_ids", "tensor(int64)", 2):
            raise ValueError("unexpected_codec_ids_contract")
        if (
            outputs[0].name,
            outputs[0].type,
            len(outputs[0].shape),
        ) != ("step_embed", "tensor(float)", 2):
            raise ValueError("unexpected_step_embed_contract")

        codec_ids = np.asarray([CODEC_FIXTURE], dtype=np.int64)
        first = session.run(None, {"codec_ids": codec_ids})[0]
        second = session.run(None, {"codec_ids": codec_ids})[0]
        hash_1 = _array_hash(outputs[0].name, first)
        hash_2 = _array_hash(outputs[0].name, second)
        result = {
            "status": "residual_embed_probe_passed",
            "input": {
                "name": inputs[0].name,
                "shape": list(codec_ids.shape),
                "dtype": str(codec_ids.dtype),
                "fixture": CODEC_FIXTURE,
            },
            "output": {
                "name": outputs[0].name,
                "shape": list(first.shape),
                "dtype": str(first.dtype),
                "all_finite": bool(np.isfinite(first).all()),
                "nonzero": bool(np.any(first != 0)),
                "minimum": float(np.min(first)),
                "maximum": float(np.max(first)),
                "mean": float(np.mean(first)),
            },
            "sha256_run_1": hash_1,
            "sha256_run_2": hash_2,
            "deterministic": hash_1 == hash_2,
        }
        code = 0
    except Exception as error:
        result = {
            "status": "residual_embed_probe_failed",
            "error_type": type(error).__name__,
            "error": str(error)[-1000:],
        }
        code = 2
    print(json.dumps(result, ensure_ascii=False))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run bounded CPU INT4 residual embedding probe"
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

    receipt = run_residual_embed_gate(
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
        if receipt["status"] == "residual_embed_probe_passed_no_forwarding"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
