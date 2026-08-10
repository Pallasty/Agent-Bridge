#!/usr/bin/env python3
"""Hash-pin complete local evaluator snapshots; never download or load models."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA = "agent_bridge.qwen3_tts.evaluator_model_pin.v0"
MODELS = {
    "emotion": {"model_id": "iic/emotion2vec_plus_large", "anchors": ("configuration.json", "model.pt")},
    "speaker": {"model_id": "iic/speech_campplus_sv_zh-cn_16k-common", "anchors": ("configuration.json", "campplus_cn_common.bin")},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def pin_snapshot(kind: str, root: Path, model_id: str | None = None) -> dict:
    spec = MODELS[kind]
    model_id = model_id or spec["model_id"]
    if not root.is_dir():
        return {"kind": kind, "model_id": model_id, "status": "MISSING_SNAPSHOT", "path": str(root)}
    missing = [name for name in spec["anchors"] if not (root / name).is_file()]
    if missing:
        return {"kind": kind, "model_id": model_id, "status": "INCOMPLETE_SNAPSHOT", "path": str(root), "missing_anchors": missing}
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files.append({"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": sha256(path)})
    return {
        "kind": kind,
        "model_id": model_id,
        "status": "PINNED_LOCAL_SNAPSHOT",
        "path": str(root),
        "file_count": len(files),
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emotion-snapshot", required=True, type=Path)
    parser.add_argument("--speaker-snapshot", required=True, type=Path)
    parser.add_argument("--emotion-model-id", default=MODELS["emotion"]["model_id"])
    parser.add_argument("--speaker-model-id", default=MODELS["speaker"]["model_id"])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite output")
    snapshots = [
        pin_snapshot("emotion", args.emotion_snapshot, args.emotion_model_id),
        pin_snapshot("speaker", args.speaker_snapshot, args.speaker_model_id),
    ]
    ready = all(row["status"] == "PINNED_LOCAL_SNAPSHOT" for row in snapshots)
    report = {
        "schema": SCHEMA,
        "status": "READY_FOR_REFERENCE_MEASUREMENT" if ready else "BLOCKED_INCOMPLETE_EVALUATOR_SNAPSHOTS",
        "snapshots": snapshots,
        "allows_candidate_generation": False,
        "allows_runtime_wiring_or_promotion": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "snapshot_statuses": [row["status"] for row in snapshots]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
