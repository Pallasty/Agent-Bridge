#!/usr/bin/env python3
"""Measure the frozen Qwen3-TTS FP16 baseline through Worker v1.

This is an offline evidence collector. It never changes the worker, model, or
promotion state. Human listening and STT are represented explicitly as pending
unless an operator supplies a separate, reviewed result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import time
import wave
from pathlib import Path


PROTOCOL = "ab.tts.worker.v1"
SCHEMA = "agent_bridge.qwen3_tts.fp16_baseline.v0"


def request(socket_path: str, payload: dict, timeout: float) -> dict:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(socket_path)
        client.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode())
        raw = bytearray()
        while len(raw) < 65536:
            chunk = client.recv(4096)
            if not chunk:
                break
            raw.extend(chunk)
            if b"\n" in chunk:
                break
        if not raw:
            raise RuntimeError("worker returned no receipt")
        return json.loads(raw.split(b"\n", 1)[0].decode())
    finally:
        client.close()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wav_info(path: Path) -> dict:
    with wave.open(str(path), "rb") as audio:
        frames = audio.getnframes()
        rate = audio.getframerate()
        channels = audio.getnchannels()
        sample_width = audio.getsampwidth()
    return {
        "frames": frames,
        "sample_rate": rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "duration_seconds": frames / rate if rate else None,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if not args.corpus.is_file():
        parser.error(f"corpus not found: {args.corpus}")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error(f"output directory must be empty: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    cases = corpus["cases"][: args.limit] if args.limit else corpus["cases"]
    health = request(args.socket, {"op": "health"}, args.timeout)
    if health.get("protocol") != PROTOCOL or health.get("ok") is not True:
        raise RuntimeError(f"worker health contract failed: {health}")
    rows = []
    started = time.time()
    for index, case in enumerate(cases, 1):
        output = args.output_dir / f"{index:02d}-{case['id']}.wav"
        started_case = time.monotonic()
        receipt = request(args.socket, {
            "op": "synthesize", "text": case["text"], "output": str(output),
            "speaker": case["speaker"], "instruct": case.get("instruct", ""),
        }, args.timeout)
        elapsed = time.monotonic() - started_case
        row = {"case": case, "receipt": receipt, "elapsed_seconds": elapsed,
               "stt": {"status": "not_run"},
               "human": {"status": "pending"}}
        if receipt.get("ok") is True and output.is_file() and output.stat().st_size:
            info = wav_info(output)
            row["audio"] = info
            row["rtf"] = elapsed / info["duration_seconds"] if info["duration_seconds"] else None
            row["status"] = "ok"
        else:
            row["status"] = "failed"
        rows.append(row)
        print(json.dumps({"index": index, "id": case["id"], "status": row["status"]}, ensure_ascii=False), flush=True)
    report = {
        "schema": SCHEMA,
        "status": "FP16_BASELINE_CAPTURED" if all(r["status"] == "ok" for r in rows) else "PARTIAL_FAILURE",
        "created_unix": int(started),
        "corpus": {"path": str(args.corpus), "sha256": sha256(args.corpus), "cases": len(cases)},
        "worker_health": health,
        "authority": "fp16_mps_worker_v1",
        "metrics_boundary": {
            "speech_token_agreement": "unsupported_by_worker_contract",
            "speech_token_kl": "unsupported_by_worker_contract",
            "stt": "not_run",
            "human_intelligibility_naturalness": "pending",
        },
        "summary": {"cases": len(rows), "succeeded": sum(r["status"] == "ok" for r in rows),
                    "failed": sum(r["status"] != "ok" for r in rows)},
        "rows": rows,
    }
    (args.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["status"] == "FP16_BASELINE_CAPTURED" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
