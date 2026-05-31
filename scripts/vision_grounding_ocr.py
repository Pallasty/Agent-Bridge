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
import os
import shutil
import subprocess
import sys
import tempfile
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
                "preprocess": {
                    "crop_image": bool(getattr(args, "crop_image", False)),
                    "upscale": float(getattr(args, "upscale", 1.0) or 1.0),
                    "psm": getattr(args, "psm", None),
                },
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


def _pil_image():
    """Lazy Pillow import — only needed when --crop-image/--upscale are used."""
    try:
        from PIL import Image  # noqa: PLC0415

        return Image
    except Exception:  # pragma: no cover - environment without Pillow
        return None


def prepare_ocr_input(
    args: argparse.Namespace,
) -> tuple[Path, bool, float, str | None, str | None]:
    """Build the actual image tesseract should OCR.

    The #1803 gap: feeding a full 4K desktop frame to tesseract misses small UI text
    (sub ~30px cap-height). The fix is to crop to the region of interest and upscale it
    so the glyphs clear tesseract's resolution floor. This function applies that:

    - ``--crop-image`` crops the pixels to ``--crop-rect`` (vs the legacy behaviour where
      ``--crop-rect`` only translated coordinates and the caller pre-cropped).
    - ``--upscale F`` LANCZOS-upscales the (cropped) image by F so glyphs reach the OCR
      floor; output coordinates are divided back by F in :func:`candidate_bbox`.

    Returns ``(ocr_path, did_crop, scale, tmp_path, error)``. Backward compatible:
    with no ``--crop-image`` and ``--upscale==1.0`` it returns the original image
    untouched (``scale==1.0``, ``did_crop=False``, no temp) so existing callers and the
    external-pre-crop path are unchanged."""
    crop = parse_rect(args.crop_rect)
    want_crop = bool(getattr(args, "crop_image", False))
    upscale = float(getattr(args, "upscale", 1.0) or 1.0)
    want_upscale = abs(upscale - 1.0) > 1e-6
    if not want_crop and not want_upscale:
        return Path(args.image), False, 1.0, None, None
    if want_crop and not crop:
        return Path(args.image), False, 1.0, None, "--crop-image requires --crop-rect"
    if upscale <= 0:
        return Path(args.image), False, 1.0, None, "--upscale must be > 0"
    Image = _pil_image()
    if Image is None:
        return Path(args.image), False, 1.0, None, "Pillow required for --crop-image/--upscale"
    resampling = getattr(Image, "Resampling", None)
    lanczos = resampling.LANCZOS if resampling is not None else Image.LANCZOS
    try:
        im = Image.open(args.image).convert("RGB")
        if want_crop:
            x, y, w, h = crop["x"], crop["y"], crop["width"], crop["height"]
            im = im.crop((x, y, x + w, y + h))
        scale = upscale if want_upscale else 1.0
        if want_upscale:
            im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), lanczos)
        fd, tmp = tempfile.mkstemp(suffix=".png", prefix="vg_ocr_")
        os.close(fd)
        im.save(tmp)
        return Path(tmp), want_crop, scale, tmp, None
    except Exception as exc:  # pragma: no cover - corrupt image / IO
        return Path(args.image), False, 1.0, None, f"image preprocessing failed: {exc}"


def load_tsv(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.engine == "fixture-tsv":
        if not args.fixture_tsv:
            return "", "--fixture-tsv is required for engine=fixture-tsv"
        # fixture coords are authored in upscaled-crop space when --upscale is exercised;
        # candidate_bbox divides by this so fixtures can test the scale-aware mapping.
        args._ocr_scale = float(getattr(args, "upscale", 1.0) or 1.0)
        args._ocr_cropped = bool(getattr(args, "crop_image", False))
        try:
            return Path(args.fixture_tsv).read_text(encoding="utf-8"), None
        except OSError as exc:
            return "", f"cannot read fixture TSV: {exc}"

    if args.engine != "tesseract":
        return "", f"engine {args.engine!r} is unavailable in this runner"

    exe = shutil.which("tesseract")
    if not exe:
        return "", "tesseract not installed"
    ocr_path, did_crop, scale, tmp, prep_err = prepare_ocr_input(args)
    if prep_err:
        return "", prep_err
    # record the transform actually applied so candidate_bbox maps coords back correctly
    args._ocr_scale = scale
    args._ocr_cropped = did_crop
    psm = getattr(args, "psm", None)
    cmd = [exe, str(ocr_path), "stdout"]
    if psm is not None:
        cmd += ["--psm", str(psm)]
    cmd += ["tsv"]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        return "", "tesseract timed out"
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
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
    # OCR ran on a possibly cropped+upscaled image; map the box back to the requested
    # coordinate space. Order matters: undo the upscale first (box is in upscaled-crop
    # pixels), THEN add the crop origin (in unscaled target pixels).
    scale = float(getattr(args, "_ocr_scale", 1.0) or 1.0)
    x = float(row["left"]) / scale
    y = float(row["top"]) / scale
    width = float(row["width"]) / scale
    height = float(row["height"]) / scale
    crop = parse_rect(args.crop_rect)
    # Add the crop origin when coords must be expressed in the un-cropped space: the
    # legacy desktop+crop case (external pre-crop) OR when this runner did the crop.
    if crop and (args.coordinate_space == "desktop" or getattr(args, "_ocr_cropped", False)):
        x += crop["x"]
        y += crop["y"]
    return {
        "x": int(round(x)),
        "y": int(round(y)),
        "width": int(round(width)),
        "height": int(round(height)),
    }


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
    ap.add_argument(
        "--crop-image",
        action="store_true",
        help="actually crop the OCR input to --crop-rect before OCR (not just translate "
        "coords); fixes small-UI-text misses on full-frame images (#1803)",
    )
    ap.add_argument(
        "--upscale",
        type=float,
        default=1.0,
        help="LANCZOS upscale factor for the OCR input so <~30px UI glyphs clear "
        "tesseract's resolution floor; output coords are divided back by this factor",
    )
    ap.add_argument(
        "--psm",
        type=int,
        default=None,
        help="tesseract page segmentation mode (7=single line, 8=single word — good for "
        "a cropped button/label)",
    )
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
