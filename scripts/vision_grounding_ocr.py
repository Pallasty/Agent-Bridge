#!/usr/bin/env python3
"""OCR-only reference runner for Linux Computer Use vision grounding.

This is a non-mutating T7 probe for forum thread #79. It converts OCR text boxes
into `vision_grounding_result.v0` candidates that T6 can later consume in
dry-run/preflight mode. It does not click, type, or control the desktop.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any


SCHEMA = "vision_grounding_result.v0"


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def parse_rect(value: str | None) -> dict[str, int] | None:
    if not value:
        return None
    parts = [int(p) for p in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("rect must be x,y,width,height")
    return {"x": parts[0], "y": parts[1], "width": parts[2], "height": parts[3]}


def make_base(args: argparse.Namespace, image_hash: str) -> dict[str, Any]:
    request_id = args.request_id or str(uuid.uuid4())
    window_rect = parse_rect(args.window_rect)
    crop_rect = parse_rect(args.crop_rect)
    return {
        "schema": SCHEMA,
        "request_id": request_id,
        "request": {
            "schema": "vision_grounding_request.v0",
            "snapshot": {
                "snapshot_id": args.snapshot_id,
                "snapshot_hash": args.snapshot_hash,
                "schema": args.snapshot_schema,
                "captured_at": args.snapshot_captured_at,
            },
            "image": {
                "path": str(args.image),
                "hash": image_hash,
                "kind": args.image_kind,
                "coordinate_space": args.coordinate_space,
                "output": args.output,
                "crop_rect": crop_rect,
            },
            "target_window": {
                "window_id": int(args.window_id) if args.window_id is not None else None,
                "pid": int(args.pid) if args.pid is not None else None,
                "app_id": args.app_id,
                "title_hash": args.title_hash,
                "rect": window_rect,
                "grounding": "vision",
            },
            "hint": {
                "task": args.task,
                "text": args.hint_text,
                "role": args.hint_role,
                "language": args.language,
            },
        },
        "source": {
            "engine": args.engine,
            "engine_version": None,
            "model_hash": None,
            "image_hash": image_hash,
        },
        "status": "ok",
        "candidates": [],
        "errors": [],
        "elapsed_ms": None,
    }


def load_tsv(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.engine == "fixture-tsv":
        if not args.fixture_tsv:
            return "", "--fixture-tsv is required for engine=fixture-tsv"
        try:
            return Path(args.fixture_tsv).read_text(encoding="utf-8"), None
        except OSError as exc:
            return "", f"cannot read fixture TSV: {exc}"

    if args.engine != "tesseract":
        return "", f"engine {args.engine!r} is unavailable in this runner"

    exe = shutil.which("tesseract")
    if not exe:
        return "", "tesseract not installed"
    cmd = [exe, str(args.image), "stdout", "tsv"]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        return "", "tesseract timed out"
    if proc.returncode != 0:
        return "", proc.stderr.strip() or f"tesseract exited {proc.returncode}"
    return proc.stdout, None


def parse_conf(value: str) -> float | None:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return None
    if conf < 0:
        return None
    return max(0.0, min(conf / 100.0, 1.0))


def role_guess(text: str, args: argparse.Namespace, matched_hint: bool) -> str:
    if matched_hint and args.hint_role:
        return args.hint_role
    lowered = text.strip().lower()
    if lowered in {"ok", "cancel", "save", "apply", "open", "close", "yes", "no"}:
        return "button"
    return "text"


def risk_notes(label: str, confidence: float) -> list[str]:
    notes: list[str] = []
    if confidence < 0.65:
        notes.append("low_confidence")
    if label.strip().lower() in {"delete", "remove", "send", "pay", "submit"}:
        notes.append("near_destructive_label")
    return notes


def candidate_bbox(row: dict[str, str], args: argparse.Namespace) -> dict[str, int]:
    x = int(float(row["left"]))
    y = int(float(row["top"]))
    width = int(float(row["width"]))
    height = int(float(row["height"]))
    crop = parse_rect(args.crop_rect)
    if args.coordinate_space == "desktop" and crop:
        x += crop["x"]
        y += crop["y"]
    return {"x": x, "y": y, "width": width, "height": height}


def tsv_candidates(tsv_text: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    reader = csv.DictReader(tsv_text.splitlines(), delimiter="\t")
    candidates: list[dict[str, Any]] = []
    hint = (args.hint_text or "").strip().lower()
    window_ref = {
        "window_id": int(args.window_id) if args.window_id is not None else None,
        "pid": int(args.pid) if args.pid is not None else None,
        "app_id": args.app_id,
    }
    for row in reader:
        text = (row.get("text") or "").strip()
        conf = parse_conf(row.get("conf", ""))
        if not text or conf is None:
            continue
        bbox = candidate_bbox(row, args)
        matched_hint = bool(hint and hint in text.lower())
        cid = f"vg-{len(candidates) + 1:03d}"
        candidates.append({
            "candidate_id": cid,
            "window_ref": window_ref,
            "bbox": bbox,
            "coordinate_space": args.coordinate_space,
            "center": {
                "x": bbox["x"] + bbox["width"] // 2,
                "y": bbox["y"] + bbox["height"] // 2,
            },
            "role_guess": role_guess(text, args, matched_hint),
            "label": text,
            "label_hash": sha256_text(text),
            "confidence": round(conf, 4),
            "evidence": {
                "ocr_text": text,
                "visual_features": ["text-like"],
                "matched_hint": matched_hint,
            },
            "risk_notes": risk_notes(text, conf),
        })
    return candidates


def build_result(args: argparse.Namespace) -> dict[str, Any]:
    start = time.time()
    image = Path(args.image)
    image_hash = args.image_hash or (sha256_file(image) if image.exists() else None)
    result = make_base(args, image_hash or "sha256:missing-image")
    if not image.exists():
        result["status"] = "error"
        result["errors"].append({"code": "image_missing", "message": str(image)})
        result["elapsed_ms"] = int((time.time() - start) * 1000)
        return result

    tsv_text, error = load_tsv(args)
    if error:
        result["status"] = "error"
        result["errors"].append({"code": "engine_unavailable", "message": error})
        result["elapsed_ms"] = int((time.time() - start) * 1000)
        return result

    result["candidates"] = tsv_candidates(tsv_text, args)
    if not result["candidates"]:
        result["status"] = "no_candidates"
    result["elapsed_ms"] = int((time.time() - start) * 1000)
    return result


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="non-mutating OCR vision grounding runner")
    ap.add_argument("--image", required=True)
    ap.add_argument("--engine", choices=["tesseract", "fixture-tsv", "none"], default="tesseract")
    ap.add_argument("--fixture-tsv")
    ap.add_argument("--request-id")
    ap.add_argument("--snapshot-id", required=True)
    ap.add_argument("--snapshot-hash", required=True)
    ap.add_argument("--snapshot-schema", default="desktop_snapshot/v0.5")
    ap.add_argument("--snapshot-captured-at")
    ap.add_argument("--image-hash")
    ap.add_argument("--image-kind", choices=["desktop", "output", "window"], default="window")
    ap.add_argument("--coordinate-space", choices=["desktop", "output", "window"], default="window")
    ap.add_argument("--output")
    ap.add_argument("--crop-rect")
    ap.add_argument("--window-id")
    ap.add_argument("--pid")
    ap.add_argument("--app-id")
    ap.add_argument("--title-hash")
    ap.add_argument("--window-rect")
    ap.add_argument("--task", default="find text")
    ap.add_argument("--hint-text")
    ap.add_argument("--hint-role", default="unknown")
    ap.add_argument("--language", default="auto")
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--compact", action="store_true")
    return ap


def main() -> int:
    args = parser().parse_args()
    result = build_result(args)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=None if args.compact else 2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
