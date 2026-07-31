#!/usr/bin/env python3
"""Prepare a revision-pinned Qwen acquisition plan without downloading files."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
REVISION = "6c3e96b6a2c593ce3e546ee699a5d944de81850e"
MODEL_WEIGHTS_BYTES = 3_833_402_552
TOKENIZER_WEIGHTS_BYTES = 682_293_092
MINIMUM_WORKSPACE_RESERVE_BYTES = 128 * 1024**3
SMALL_FILE_PATHS = (
    ".gitattributes",
    "README.md",
    "config.json",
    "generation_config.json",
    "merges.txt",
    "preprocessor_config.json",
    "tokenizer_config.json",
    "vocab.json",
    "speech_tokenizer/config.json",
    "speech_tokenizer/configuration.json",
    "speech_tokenizer/preprocessor_config.json",
)
WEIGHT_FILES = (
    ("model.safetensors", MODEL_WEIGHTS_BYTES),
    ("speech_tokenizer/model.safetensors", TOKENIZER_WEIGHTS_BYTES),
)


def _runtime_effects() -> dict[str, bool]:
    return {
        "network_requests": False,
        "created_destination": False,
        "downloaded_small_files": False,
        "downloaded_weights": False,
        "executed_converter": False,
        "executed_onnx_graphs": False,
        "replaced_current_snapshot": False,
        "used_gpu": False,
        "played_audio": False,
    }


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def build_plan(
    destination: Path,
    *,
    current_snapshot: Path,
    available_bytes: int,
    destination_exists: bool,
) -> dict[str, Any]:
    destination = destination.resolve()
    current_snapshot = current_snapshot.resolve()
    blockers = []
    if destination_exists:
        blockers.append("isolated_destination_already_exists")
    if _is_relative_to(destination, current_snapshot) or _is_relative_to(
        current_snapshot, destination
    ):
        blockers.append("destination_overlaps_current_snapshot")
    if available_bytes < MINIMUM_WORKSPACE_RESERVE_BYTES:
        blockers.append("insufficient_workspace_reserve")

    command = [
        "hf",
        "download",
        MODEL_ID,
        "--revision",
        REVISION,
        *[
            item
            for path in SMALL_FILE_PATHS
            for item in ("--include", path)
        ],
        "--local-dir",
        str(destination),
    ]
    planning_blockers = [
        "fixed_revision_sha256_ledger_pending_offline_acquisition",
        "small_files_not_downloaded",
        "fixed_revision_weights_not_authorized",
        "fixed_source_reexport_not_executed",
        "parity_not_reverified",
    ]
    return {
        "schema": "agent_bridge.voice_fixed_source_acquisition_plan.v1",
        "status": "blocked" if blockers else "offline_plan_ready",
        "official_model_id": MODEL_ID,
        "revision": REVISION,
        "revision_immutable": True,
        "destination": str(destination),
        "current_onnx_snapshot": str(current_snapshot),
        "small_files": [
            {
                "path": path,
                "expected_sha256": None,
                "hash_state": "pending_fixed_revision_offline_acquisition",
            }
            for path in SMALL_FILE_PATHS
        ],
        "weights": {
            "authorized": False,
            "download_command_emitted": False,
            "files": [
                {"path": path, "expected_bytes": size}
                for path, size in WEIGHT_FILES
            ],
            "total_bytes": MODEL_WEIGHTS_BYTES
            + TOKENIZER_WEIGHTS_BYTES,
        },
        "commands": {
            "small_files_only_argv": command,
            "post_download_hash_argv": [
                "sha256sum",
                *[str(destination / path) for path in SMALL_FILE_PATHS],
            ],
            "weight_download_command": None,
        },
        "disk_preflight": {
            "available_bytes": available_bytes,
            "minimum_workspace_reserve_bytes": (
                MINIMUM_WORKSPACE_RESERVE_BYTES
            ),
            "reserve_policy": (
                "planning_floor_not_an_export_size_estimate"
            ),
            "passes": available_bytes >= MINIMUM_WORKSPACE_RESERVE_BYTES,
        },
        "blockers": blockers + planning_blockers,
        "runtime_effects": _runtime_effects(),
    }


def _nearest_existing_ancestor(path: Path) -> Path:
    candidate = path.resolve()
    while not candidate.exists():
        if candidate.parent == candidate:
            raise FileNotFoundError(f"no existing ancestor for {path}")
        candidate = candidate.parent
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan fixed-revision small-file acquisition without I/O"
    )
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--current-snapshot", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    ancestor = _nearest_existing_ancestor(args.destination)
    available = shutil.disk_usage(ancestor).free
    receipt = build_plan(
        args.destination,
        current_snapshot=args.current_snapshot,
        available_bytes=available,
        destination_exists=args.destination.exists(),
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["status"] == "offline_plan_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
