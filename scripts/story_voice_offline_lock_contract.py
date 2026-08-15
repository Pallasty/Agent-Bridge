#!/usr/bin/env python3
"""Build the non-executing S5S1 offline-lock and workspace contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CRITICAL_DIRECT_PINS = (
    ("python", "3.12.13", "cpython"),
    ("torch", "2.12.0+cpu", "pytorch_cpu_index"),
    ("torchvision", "0.27.0+cpu", "pytorch_cpu_index"),
    ("transformers", "4.57.3", "pypi"),
    ("olive-ai", "0.13.0", "pypi"),
    ("onnx", "1.21.0", "pypi"),
    ("onnxruntime", "1.27.0", "pypi"),
)
MINIMUM_AVAILABLE_BYTES = 128 * 1024**3


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve()


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def build_contract(
    s5s_receipt: dict[str, Any],
    s5r_receipt: dict[str, Any],
    workspace: Path,
    wheelhouse: Path,
    venv: Path,
    available_bytes: int,
) -> dict[str, Any]:
    if s5s_receipt.get("status") != "audited_lock_and_execution_blocked":
        raise ValueError("S5S toolchain audit is not the required blocked audit")
    if not s5r_receipt.get("weight_payload_fixed_revision_equivalent"):
        raise ValueError("S5R fixed-revision-equivalent weight payload is required")
    source_hashes = s5s_receipt.get("source_identity", {}).get("files", {})
    if set(source_hashes) != {
        "optimize.py",
        "user_script.py",
        "requirements.txt",
    } or any(len(value) != 64 for value in source_hashes.values()):
        raise ValueError("S5S converter source hash ledger is incomplete")
    if available_bytes < MINIMUM_AVAILABLE_BYTES:
        raise ValueError("available space is below the 128 GiB policy floor")

    destinations = {
        "workspace": _resolved(workspace),
        "wheelhouse": _resolved(wheelhouse),
        "venv": _resolved(venv),
    }
    protected = {
        "source_model": _resolved(
            Path(s5r_receipt["source"]["snapshot"])
        ),
        "current_onnx": _resolved(
            Path(s5r_receipt["current_onnx_snapshot"])
        ),
        "community_converter": _resolved(Path(s5s_receipt["snapshot"])),
    }
    for name, path in destinations.items():
        if path.exists():
            raise ValueError(f"{name} must not already exist: {path}")
        for protected_name, protected_path in protected.items():
            if _overlaps(path, protected_path):
                raise ValueError(
                    f"{name} overlaps protected path {protected_name}: {path}"
                )
    destination_items = list(destinations.items())
    for index, (left_name, left) in enumerate(destination_items):
        for right_name, right in destination_items[index + 1 :]:
            if _overlaps(left, right):
                raise ValueError(
                    f"{left_name} overlaps destination {right_name}"
                )

    direct_pins = [
        {"name": name, "version": version, "source": source}
        for name, version, source in CRITICAL_DIRECT_PINS
    ]
    full_lock = destinations["workspace"] / "locks" / "requirements.lock"
    return {
        "schema": "agent_bridge.voice_offline_lock_contract.v1",
        "status": "direct_lock_contract_ready_wheelhouse_pending",
        "inputs": {
            "s5s_status": s5s_receipt["status"],
            "weight_payload_fixed_revision_equivalent": True,
            "converter_source_hashes": source_hashes,
        },
        "dependency_lock": {
            "python_abi": "cp312",
            "platform": "manylinux_x86_64",
            "critical_direct_pins": direct_pins,
            "critical_direct_pins_exact": True,
            "transitive_lock_complete": False,
            "wheel_hash_ledger_complete": False,
            "excluded": [
                {
                    "name": "torchaudio",
                    "reason": (
                        "not_imported_by_converter_and_absent_from_official_"
                        "torch_2_12_cpu_recipe"
                    ),
                },
                {
                    "name": "onnxruntime-genai",
                    "reason": (
                        "modelbuilder_path_rejected_for_qwen_tts_and_not_"
                        "imported_by_selected_converter"
                    ),
                },
            ],
        },
        "workspace": {
            "available_bytes_observed": available_bytes,
            "minimum_available_bytes": MINIMUM_AVAILABLE_BYTES,
            "destinations_absent": True,
            "destinations_disjoint": True,
            "paths": {
                **{key: str(value) for key, value in destinations.items()},
                **{key: str(value) for key, value in protected.items()},
            },
            "future_layout": {
                "converter_copy": str(destinations["workspace"] / "source"),
                "cpu_fp32": str(
                    destinations["workspace"] / "output" / "cpu_fp32"
                ),
                "cpu_int4": str(
                    destinations["workspace"] / "output" / "cpu_int4"
                ),
                "cache": str(destinations["workspace"] / "cache"),
            },
            "run_converter_inside_community_snapshot": False,
        },
        "commands": {
            "offline_install_argv_template": [
                str(destinations["venv"] / "bin" / "python"),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(destinations["wheelhouse"]),
                "--require-hashes",
                "-r",
                str(full_lock),
            ],
            "converter_argv": None,
        },
        "readiness": {
            "offline_install_ready": False,
            "converter_execution_ready": False,
        },
        "blockers": [
            "transitive_dependency_resolution_not_run",
            "wheelhouse_not_materialized",
            "wheel_sha256_ledger_incomplete",
            "isolated_workspace_not_created",
            "offline_install_not_verified",
            "converter_execution_not_authorized",
        ],
        "next_gate": "materialize_and_hash_offline_wheelhouse",
        "runtime_effects": {
            "used_network": False,
            "created_directories": False,
            "created_external_files": False,
            "installed_packages": False,
            "loaded_source_model": False,
            "executed_converter": False,
            "executed_quantizer": False,
            "created_onnx": False,
            "used_gpu": False,
            "played_audio": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--s5s-receipt", type=Path, required=True)
    parser.add_argument("--s5r-receipt", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--venv", type=Path, required=True)
    parser.add_argument("--available-bytes", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    contract = build_contract(
        json.loads(args.s5s_receipt.read_text()),
        json.loads(args.s5r_receipt.read_text()),
        args.workspace,
        args.wheelhouse,
        args.venv,
        args.available_bytes,
    )
    rendered = json.dumps(contract, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
