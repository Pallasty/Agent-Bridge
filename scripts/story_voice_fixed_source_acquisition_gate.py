#!/usr/bin/env python3
"""Verify Qwen source weights against immutable official content hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
OFFICIAL_REVISION = "6c3e96b6a2c593ce3e546ee699a5d944de81850e"
EXPECTED_WEIGHTS = {
    "model.safetensors": {
        "bytes": 3_833_402_552,
        "sha256": (
            "38b1d5971bdbd982b561cccec982669a53b0537c3cf5e9bd4778ed07bb2f5137"
        ),
    },
    "speech_tokenizer/model.safetensors": {
        "bytes": 682_293_092,
        "sha256": (
            "836b7b357f5ea43e889936a3709af68dfe3751881acefe4ecf0dbd30ba571258"
        ),
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safetensors_contract(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        header_bytes = struct.unpack("<Q", handle.read(8))[0]
        header = json.loads(handle.read(header_bytes))
    tensors = [name for name in header if name != "__metadata__"]
    return {
        "header_bytes": header_bytes,
        "metadata": header.get("__metadata__"),
        "tensor_count": len(tensors),
        "first_tensor": tensors[0] if tensors else None,
        "last_tensor": tensors[-1] if tensors else None,
    }


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def verify_acquisition(
    snapshot: Path,
    *,
    current_onnx_snapshot: Path,
    expected_weights: dict[str, dict[str, Any]] = EXPECTED_WEIGHTS,
) -> dict[str, Any]:
    snapshot = snapshot.resolve()
    current_onnx_snapshot = current_onnx_snapshot.resolve()
    required = tuple(expected_weights)
    missing = [rel for rel in required if not (snapshot / rel).is_file()]
    overlap = _is_relative_to(snapshot, current_onnx_snapshot) or (
        _is_relative_to(current_onnx_snapshot, snapshot)
    )
    blockers = []
    if missing:
        blockers.append("required_weight_missing")
    if overlap:
        blockers.append("source_overlaps_current_onnx_snapshot")

    weights = []
    all_match = not missing
    parsed_headers = 0
    for rel in required:
        path = snapshot / rel
        if not path.is_file():
            continue
        actual_bytes = path.stat().st_size
        actual_sha256 = _sha256(path)
        expected = expected_weights[rel]
        matches = (
            actual_bytes == expected["bytes"]
            and actual_sha256 == expected["sha256"]
        )
        all_match = all_match and matches
        contract = _safetensors_contract(path)
        parsed_headers += 1
        weights.append(
            {
                "path": rel,
                "expected_bytes": expected["bytes"],
                "actual_bytes": actual_bytes,
                "expected_sha256": expected["sha256"],
                "actual_sha256": actual_sha256,
                "matches_official_fixed_revision": matches,
                "safetensors": contract,
            }
        )
    if not all_match and not missing:
        blockers.append("weight_payload_hash_or_size_mismatch")

    small_files = []
    if snapshot.is_dir():
        for path in sorted(snapshot.rglob("*")):
            if path.is_file() and path.name != "model.safetensors":
                small_files.append(
                    {
                        "path": path.relative_to(snapshot).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": _sha256(path),
                    }
                )
    payload_verified = all_match and not overlap
    if payload_verified:
        blockers.extend(
            [
                "fixed_revision_small_file_byte_parity_incomplete",
                "isolated_export_toolchain_not_audited",
                "converter_not_executed",
                "parity_not_reverified",
            ]
        )
    return {
        "schema": "agent_bridge.voice_fixed_source_acquisition_gate.v1",
        "status": (
            "weight_payload_fixed_revision_verified_packaging_divergent"
            if payload_verified
            else "blocked"
        ),
        "official_model_id": MODEL_ID,
        "official_revision": OFFICIAL_REVISION,
        "source": {
            "provider": "modelscope",
            "declared_revision": "master",
            "declared_revision_immutable": False,
            "snapshot": str(snapshot),
            "isolated_from_current_onnx": not overlap,
        },
        "current_onnx_snapshot": str(current_onnx_snapshot),
        "weight_payload_fixed_revision_equivalent": payload_verified,
        "packaging_exact_fixed_revision": False,
        "conversion_ready": False,
        "weights": weights,
        "small_files": small_files,
        "missing_files": missing,
        "blockers": blockers,
        "runtime_effects": {
            "hashed_weight_files": len(weights),
            "parsed_safetensors_headers": parsed_headers,
            "downloaded_files": False,
            "created_model_files": False,
            "executed_converter": False,
            "executed_model": False,
            "replaced_current_snapshot": False,
            "used_gpu": False,
            "played_audio": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify ModelScope Qwen weights against official hashes"
    )
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--current-onnx-snapshot", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify_acquisition(
        args.snapshot,
        current_onnx_snapshot=args.current_onnx_snapshot,
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["weight_payload_fixed_revision_equivalent"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
