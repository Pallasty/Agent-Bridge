#!/usr/bin/env python3
"""Check ABot-World runtime prerequisites without loading the model."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

SCHEMA = "agent_bridge.abot_world_runtime_preflight.v0"
REQUIRED_MODULES = ("torch", "diffusers", "transformers", "accelerate", "safetensors")
REQUIRED_CHECKPOINTS = (
    "Wan2.2_VAE.pth",
    "taew2_2.pth",
    "models_t5_umt5-xxl-enc-bf16.pth",
    "diffusion_pytorch_model.safetensors",
)


def nvidia_probe() -> dict[str, object]:
    binary = shutil.which("nvidia-smi")
    if not binary:
        return {"available": False, "reason": "nvidia-smi_not_found"}
    try:
        result = subprocess.run(
            [binary, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {"available": False, "reason": f"probe_error:{type(error).__name__}"}
    return {
        "available": result.returncode == 0 and bool(result.stdout.strip()),
        "summary": result.stdout.strip(),
        "returncode": result.returncode,
    }


def preflight(model_root: Path) -> dict[str, object]:
    root = model_root.expanduser().resolve()
    modules = {name: importlib.util.find_spec(name) is not None for name in REQUIRED_MODULES}
    checkpoints = {name: (root / name).is_file() for name in REQUIRED_CHECKPOINTS}
    reasons: list[str] = []
    if platform.system() != "Linux":
        reasons.append("official_runtime_target_is_linux")
    if platform.machine() not in {"x86_64", "amd64"}:
        reasons.append("official_runtime_target_is_x86_64")
    gpu = nvidia_probe()
    if not gpu["available"]:
        reasons.append("nvidia_gpu_unavailable")
    if sys.version_info < (3, 12):
        reasons.append("python_3_12_required_by_upstream_setup")
    missing_modules = [name for name, present in modules.items() if not present]
    if missing_modules:
        reasons.append("missing_python_modules:" + ",".join(missing_modules))
    missing_checkpoints = [name for name, present in checkpoints.items() if not present]
    if missing_checkpoints:
        reasons.append("missing_checkpoint_files:" + ",".join(missing_checkpoints))
    return {
        "schema": SCHEMA,
        "model_root": str(root),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "gpu": gpu,
        "python_modules": modules,
        "checkpoint_files": checkpoints,
        "admission": {
            "ready": not reasons,
            "verdict": "ready" if not reasons else "blocked",
            "reasons": reasons,
            "load_attempted": False,
            "inference_attempted": False,
            "runtime_admitted": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = preflight(args.model_root)
    rendered = json.dumps(result, ensure_ascii=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["admission"]["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
