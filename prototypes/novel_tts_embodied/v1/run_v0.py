#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Optional

from pipeline import run_pipeline, DEFAULT_CONFIG


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Legacy v0.1 compatibility runner for novel_tts_embodied."
    )
    ap.add_argument("--input", required=True, help="小说文本文件")
    ap.add_argument("--output-dir", required=True, help="输出目录")
    ap.add_argument("--voice-male", default=DEFAULT_CONFIG["voice_male"])
    ap.add_argument("--voice-female", default=DEFAULT_CONFIG["voice_female"])
    ap.add_argument("--voice-narrator", default=DEFAULT_CONFIG["voice_narrator"])
    ap.add_argument("--voice-unknown", default=DEFAULT_CONFIG["voice_unknown"])
    ap.add_argument("--tts-backend", default=DEFAULT_CONFIG["tts_backend"])
    ap.add_argument("--chapter", type=int, default=1)
    ap.add_argument("--segment-limit", type=int, default=DEFAULT_CONFIG["segment_limit"])
    ap.add_argument("--emit-plan", action="store_true", default=True)
    ap.add_argument("--no-emit-plan", dest="emit_plan", action="store_false")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--result-json", dest="result_json", action="store_true", default=True)
    ap.add_argument("--no-result-json", dest="result_json", action="store_false")
    return ap.parse_args(list(argv) if argv is not None else None)


def main() -> None:
    args = parse_args()
    cfg = {
        "voice_male": args.voice_male,
        "voice_female": args.voice_female,
        "voice_narrator": args.voice_narrator,
        "voice_unknown": args.voice_unknown,
        "tts_backend": args.tts_backend,
        "segment_limit": args.segment_limit,
    }

    output_dir = Path(args.output_dir)
    text = _read_text(Path(args.input))
    segments, manifest, result, paths = run_pipeline(
        text=text,
        output_dir=output_dir,
        config=cfg,
        chapter=args.chapter,
        emit_plan=args.emit_plan,
        dry_run=args.dry_run,
        version="novel_tts_embodied:v0.1",
    )

    if not args.dry_run:
        result_file = output_dir / "result.json"
        payload = dict(result)
        payload.update(
            {
                "mode": "run_v0",
                "manifest": {
                    "version": manifest["version"],
                    "segment_count": manifest["summary"]["segment_count"],
                },
                "segment_count": len(segments),
                "segment_path": str(paths[0]),
                "manifest_path": str(paths[1]),
            }
        )
        if args.result_json:
            result_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"result_json={result_file}")
        print(json.dumps({"status": result["status"], "manifest": result["manifest_path"], "segments": result["segments_path"]}, ensure_ascii=False))
    else:
        print(json.dumps({"status": result["status"], "segments": len(segments)}))


if __name__ == "__main__":
    main()
