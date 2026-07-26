#!/usr/bin/env python3
"""Fail-closed offline gate for the disposable Qwen3-TTS Rust pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import wave
from pathlib import Path


MODEL_REVISION = "85e237c12c027371202489a0ec509ded67b5e4b5"
EXPECTED_FILES = {
    "model.safetensors": {
        "size": 1_811_626_576,
        "sha256": "bc3c7e785eb961179c25450d1acff03f839e0002f2f3a5aeb67b5735c0fa2adb",
    },
    "speech_tokenizer/model.safetensors": {
        "size": 682_293_092,
        "sha256": "836b7b357f5ea43e889936a3709af68dfe3751881acefe4ecf0dbd30ba571258",
    },
}
DEFAULT_TEXT = "你好，这是 Agent Bridge 的纯 Rust 语音试验。"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_files(model_dir: Path, specs=EXPECTED_FILES) -> list[dict]:
    results = []
    for relative, expected in specs.items():
        path = model_dir / relative
        row = {
            "path": relative,
            "expected_size": expected["size"],
            "expected_sha256": expected["sha256"],
            "exists": path.is_file(),
            "size": None,
            "sha256": None,
            "verified": False,
            "reason": None,
        }
        if not row["exists"]:
            row["reason"] = "missing"
        else:
            row["size"] = path.stat().st_size
            if row["size"] != expected["size"]:
                row["reason"] = "size_mismatch"
            else:
                row["sha256"] = sha256_file(path)
                if row["sha256"] != expected["sha256"]:
                    row["reason"] = "sha256_mismatch"
                else:
                    row["verified"] = True
        results.append(row)
    return results


def build_command(
    binary: Path,
    model_dir: Path,
    output: Path,
    text: str,
    speaker: str,
    max_tokens: int,
    seed: int,
) -> list[str]:
    return [
        str(binary),
        "--model-path",
        str(model_dir),
        "--text",
        text,
        "--language",
        "chinese",
        "--device",
        "metal",
        "--dtype",
        "f16",
        "--max-tokens",
        str(max_tokens),
        "--seed",
        str(seed),
        "--output",
        str(output),
        "custom-voice",
        "--speaker",
        speaker,
    ]


def inspect_wav(path: Path) -> dict:
    with wave.open(str(path), "rb") as audio:
        return {
            "channels": audio.getnchannels(),
            "sample_rate": audio.getframerate(),
            "sample_width": audio.getsampwidth(),
            "frames": audio.getnframes(),
            "duration_seconds": (
                audio.getnframes() / audio.getframerate()
                if audio.getframerate()
                else 0.0
            ),
        }


def run_gate(
    binary: Path,
    model_dir: Path,
    output: Path,
    *,
    text: str = DEFAULT_TEXT,
    speaker: str = "Serena",
    max_tokens: int = 128,
    seed: int = 42,
    timeout_seconds: int = 900,
    specs=EXPECTED_FILES,
    runner=subprocess.run,
) -> dict:
    report = {
        "schema": "agent_bridge.qwen3_tts_rust_gate.v1",
        "ok": False,
        "verified": False,
        "verified_to": None,
        "model_revision": MODEL_REVISION,
        "model_dir": str(model_dir),
        "binary": str(binary),
        "output": str(output),
        "model_files": verify_model_files(model_dir, specs),
        "execution": {"attempted": False},
        "reason": None,
    }
    if not all(row["verified"] for row in report["model_files"]):
        report["reason"] = "model_integrity_failed"
        return report
    if not binary.is_file() or not os.access(binary, os.X_OK):
        report["reason"] = "binary_not_executable"
        return report
    if output.exists():
        report["reason"] = "output_already_exists"
        return report

    command = build_command(
        binary, model_dir, output, text, speaker, max_tokens, seed
    )
    started = time.monotonic()
    report["execution"] = {
        "attempted": True,
        "command": command,
        "timeout_seconds": timeout_seconds,
    }
    try:
        completed = runner(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        report["execution"]["elapsed_seconds"] = time.monotonic() - started
        report["reason"] = "inference_timeout"
        return report
    except OSError as exc:
        report["execution"]["elapsed_seconds"] = time.monotonic() - started
        report["execution"]["error"] = str(exc)[:500]
        report["reason"] = "inference_start_failed"
        return report

    report["execution"].update(
        {
            "elapsed_seconds": time.monotonic() - started,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
        }
    )
    if completed.returncode != 0:
        report["reason"] = "inference_failed"
        return report
    if not output.is_file():
        report["reason"] = "output_missing"
        return report

    try:
        wav = inspect_wav(output)
    except (OSError, EOFError, wave.Error) as exc:
        report["reason"] = "output_invalid_wav"
        report["output_error"] = str(exc)[:500]
        return report
    if wav["frames"] <= 0 or wav["sample_rate"] <= 0:
        report["reason"] = "output_empty_wav"
        return report

    report["output_evidence"] = {
        **wav,
        "bytes": output.stat().st_size,
        "sha256": sha256_file(output),
    }
    report["ok"] = True
    report["verified"] = True
    report["verified_to"] = "qwen3_rust_synthesized_wav"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--speaker", default="Serena")
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    report = run_gate(
        args.binary,
        args.model_dir,
        args.output,
        text=args.text,
        speaker=args.speaker,
        max_tokens=max(1, args.max_tokens),
        seed=args.seed,
        timeout_seconds=max(1, args.timeout_seconds),
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
