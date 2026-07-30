#!/usr/bin/env python3
"""CPU INT4 ONNX session-creation smoke gate with no graph execution."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


CPU_PROVIDER = "CPUExecutionProvider"


def _runtime_provenance(
    version: str, executable: str, providers: list[str]
) -> dict[str, Any]:
    return {
        "name": "onnxruntime",
        "version": version,
        "executable": executable,
        "available_providers": providers,
    }


def _blocked_receipt(
    snapshot: Path,
    blocker: str,
    *,
    runtime_version: str,
    runtime_executable: str,
    available_providers: list[str],
) -> dict[str, Any]:
    return {
        "schema": "agent_bridge.voice_cpu_int4_smoke_receipt.v1",
        "status": "blocked",
        "snapshot": str(snapshot.resolve()),
        "provider": CPU_PROVIDER,
        "runtime": _runtime_provenance(
            runtime_version, runtime_executable, available_providers
        ),
        "planned_models": [],
        "probed_models": [],
        "blockers": [blocker],
        "runtime_effects": {
            "created_inference_sessions": False,
            "executed_graphs": False,
            "generated_tokens": False,
            "rendered_audio": False,
            "played_audio": False,
            "used_gpu": False,
            "imported_community_python": False,
        },
    }


def manifest_models(snapshot: Path) -> list[Path]:
    manifest_path = snapshot / "cpu_int4" / "manifest.json"
    payload = json.loads(manifest_path.read_text())
    if (
        payload.get("device") != "cpu"
        or payload.get("precision") != "int4"
        or payload.get("execution_provider") != CPU_PROVIDER
    ):
        raise ValueError("cpu_int4_manifest_contract_mismatch")
    models = []
    for row in payload["sub_models"].values():
        filename = row["filename"]
        if (
            not isinstance(filename, str)
            or Path(filename).is_absolute()
            or len(Path(filename).parts) != 1
        ):
            raise ValueError("unsafe_manifest_model_path")
        path = manifest_path.parent / filename
        if not path.is_file():
            raise FileNotFoundError(filename)
        models.append(path)
    return models


def run_smoke_gate(
    snapshot: Path,
    *,
    owner_authorized: bool,
    available_providers: list[str],
    probe: Callable[[Path, int], dict[str, Any]],
    timeout_seconds: int = 180,
    runtime_version: str = "unknown",
    runtime_executable: str = sys.executable,
) -> dict[str, Any]:
    if not owner_authorized:
        return _blocked_receipt(
            snapshot,
            "owner_authorization_required",
            runtime_version=runtime_version,
            runtime_executable=runtime_executable,
            available_providers=available_providers,
        )
    if CPU_PROVIDER not in available_providers:
        return _blocked_receipt(
            snapshot,
            "cpu_execution_provider_unavailable",
            runtime_version=runtime_version,
            runtime_executable=runtime_executable,
            available_providers=available_providers,
        )
    try:
        models = manifest_models(snapshot)
    except (OSError, ValueError, KeyError, TypeError):
        return _blocked_receipt(
            snapshot,
            "cpu_int4_manifest_invalid",
            runtime_version=runtime_version,
            runtime_executable=runtime_executable,
            available_providers=available_providers,
        )

    rows = []
    for path in models:
        result = probe(path, timeout_seconds)
        rows.append(
            {
                "path": path.relative_to(snapshot).as_posix(),
                **result,
            }
        )
    failed = any(row.get("status") != "session_created" for row in rows)
    return {
        "schema": "agent_bridge.voice_cpu_int4_smoke_receipt.v1",
        "status": (
            "blocked"
            if failed
            else "session_creation_passed_no_inference"
        ),
        "snapshot": str(snapshot.resolve()),
        "provider": CPU_PROVIDER,
        "runtime": _runtime_provenance(
            runtime_version, runtime_executable, available_providers
        ),
        "planned_models": [
            path.relative_to(snapshot).as_posix() for path in models
        ],
        "probed_models": rows,
        "blockers": ["session_creation_failed"] if failed else [],
        "runtime_effects": {
            "created_inference_sessions": bool(rows),
            "executed_graphs": False,
            "generated_tokens": False,
            "rendered_audio": False,
            "played_audio": False,
            "used_gpu": False,
            "imported_community_python": False,
        },
    }


def subprocess_probe(path: Path, timeout_seconds: int) -> dict[str, Any]:
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
            "status": "session_failed",
            "error_type": "TimeoutExpired",
            "error": f"session creation exceeded {timeout_seconds}s",
        }
    if completed.returncode != 0:
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {
                "status": "session_failed",
                "error_type": "ChildProcessError",
                "error": (completed.stderr or "child failed")[-1000:],
            }
    return json.loads(completed.stdout)


def child_probe(path: Path) -> int:
    try:
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(
            str(path),
            sess_options=options,
            providers=[CPU_PROVIDER],
        )
        result = {
            "status": "session_created",
            "providers": session.get_providers(),
            "inputs": len(session.get_inputs()),
            "outputs": len(session.get_outputs()),
        }
        code = 0
    except Exception as error:
        result = {
            "status": "session_failed",
            "error_type": type(error).__name__,
            "error": str(error)[-1000:],
        }
        code = 2
    print(json.dumps(result, ensure_ascii=False))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create CPU INT4 ONNX sessions without executing graphs"
    )
    parser.add_argument("--child", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--owner-authorized", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()
    if args.child:
        return child_probe(args.child)
    if args.snapshot is None or args.receipt is None:
        parser.error("--snapshot and --receipt are required")

    import onnxruntime as ort

    receipt = run_smoke_gate(
        args.snapshot,
        owner_authorized=args.owner_authorized,
        available_providers=ort.get_available_providers(),
        probe=subprocess_probe,
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
        if receipt["status"] == "session_creation_passed_no_inference"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
