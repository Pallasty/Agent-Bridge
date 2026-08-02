#!/usr/bin/env python3
"""Synthetic S624 Worker that exercises the checked-in S622 codec."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def load_codec(path: str):
    spec = importlib.util.spec_from_file_location("story_render_worker_protocol", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("codec unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def encoded(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def success_response(request_id: str) -> dict[str, object]:
    return {
        "protocol": "agent_bridge.story-render-worker.v1",
        "request_id": request_id,
        "status": "success",
        "render_id": request_id,
        "segment_count": 3,
        "assembly": {
            "sha256": "34" * 32,
            "sample_rate_hz": 24_000,
            "channels": 1,
            "frames": 72_000,
            "duration_seconds": 3.0,
        },
        "playback_authorized": False,
        "memory_authorized": False,
    }


def publish(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def main() -> int:
    mode, codec_path, contract_path, *extra = sys.argv[1:]
    codec = load_codec(codec_path)
    contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    raw_request = sys.stdin.buffer.read()
    try:
        request = codec.decode_request(raw_request, contract)
    except codec.ProtocolError as error:
        try:
            request_id = json.loads(raw_request)["request_id"]
        except (KeyError, TypeError, ValueError):
            request_id = None
        sys.stderr.write(f"synthetic codec rejection: {error.code}\n")
        sys.stdout.buffer.write(
            codec.encode_error_response(
                request_id=request_id,
                code="invalid_request",
                retryable=False,
                contract=contract,
            )
        )
        return 0

    request_id = request["request_id"]
    if mode == "success":
        response = success_response(request_id)
        codec.validate_worker_response(
            encoded(response), contract, expected_request_id=request_id
        )
        sys.stderr.write("synthetic S622 codec worker\n")
        sys.stdout.buffer.write(encoded(response))
        return 0
    if mode == "worker_error":
        sys.stdout.buffer.write(
            codec.encode_error_response(
                request_id=request_id,
                code="render_failed",
                retryable=False,
                contract=contract,
            )
        )
        return 0
    if mode == "mismatched_response":
        sys.stdout.buffer.write(encoded(success_response("56" * 16)))
        return 0
    if mode == "forbidden_response":
        response = success_response(request_id)
        response["output_directory"] = "/synthetic/forbidden"
        sys.stdout.buffer.write(encoded(response))
        return 0
    if mode == "unknown_error_code":
        response = {
            "protocol": "agent_bridge.story-render-worker.v1",
            "request_id": request_id,
            "status": "error",
            "code": "invented_error",
            "retryable": False,
        }
        sys.stdout.buffer.write(encoded(response))
        return 0
    if mode == "duplicate_response_key":
        response = encoded(success_response(request_id))
        sys.stdout.buffer.write(
            response[:-1] + b',"status":"success"}'
        )
        return 0
    if mode == "mark_success":
        publish(extra[0], "spawned")
        sys.stdout.buffer.write(encoded(success_response(request_id)))
        return 0
    if mode == "hang_after_decode":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(300)",
            ],
            close_fds=True,
        )
        publish(extra[0], f"{os.getpid()} {child.pid}")
        time.sleep(300)
    return 70


if __name__ == "__main__":
    raise SystemExit(main())
