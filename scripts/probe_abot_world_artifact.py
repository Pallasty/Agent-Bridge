#!/usr/bin/env python3
"""Offline ABot-World artifact inventory.

This probe intentionally has no ML/runtime dependencies. It inventories a
checkpoint directory, reads only small metadata files, and emits a stable
manifest. It never imports torch, opens model weights, or starts inference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

SCHEMA = "agent_bridge.abot_world_artifact_probe.v0"
DEFAULT_METADATA = ("config.json", "configuration.json")
DEFAULT_MAX_METADATA_BYTES = 1_048_576


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_metadata(root: Path, name: str) -> dict[str, Any] | None:
    path = root / name
    if not path.is_file() or path.stat().st_size > DEFAULT_MAX_METADATA_BYTES:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def inventory(root: Path, hash_content: bool = False) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"model root is not a directory: {root}")

    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        stat = path.stat()
        item: dict[str, Any] = {"path": relative, "bytes": stat.st_size}
        if hash_content:
            item["sha256"] = sha256_file(path)
        files.append(item)

    manifest_input = json.dumps(files, ensure_ascii=True, separators=(",", ":")).encode()
    metadata = {name: read_json_metadata(root, name) for name in DEFAULT_METADATA}
    metadata = {name: value for name, value in metadata.items() if value is not None}
    return {
        "schema": SCHEMA,
        "probe": {
            "mode": "offline_artifact_inventory",
            "runtime_admitted": False,
            "model_loaded": False,
            "inference_executed": False,
            "weights_content_hashed": hash_content,
        },
        "model": {
            "provider_id": "abot-world.local",
            "model_id": "ABot-World-0-5B-LF",
            "root": str(root),
            "metadata": metadata,
        },
        "files": files,
        "artifact_manifest_sha256": sha256_bytes(manifest_input),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_root", type=Path)
    parser.add_argument("--hash-content", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = inventory(args.model_root, hash_content=args.hash_content)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    rendered = json.dumps(result, ensure_ascii=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
