#!/usr/bin/env python3
"""Isolated, non-promoting probe for a same-family Qwen3-TTS GGUF candidate."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

BACKEND = "qwen3-tts-1.7b-customvoice"
MIN_SAMPLE_RATE = 24_000


def build_command(runtime, talker, codec, voice, text, output, instruct, seed):
    """Build the exact explicit-model CrispASR invocation; never use -m auto."""
    command = [
        str(runtime), "--backend", BACKEND, "-m", str(talker),
        "--codec-model", str(codec), "--voice", voice,
        "--tts", text, "--tts-output", str(output), "--seed", str(seed),
    ]
    if instruct:
        command.extend(["--instruct", instruct])
    return command


def wav_sample_rate(path):
    """Read the WAV fmt sample rate without a third-party decoder."""
    with Path(path).open("rb") as handle:
        if handle.read(4) != b"RIFF":
            raise ValueError("output is not a RIFF WAV")
        handle.read(4)
        if handle.read(4) != b"WAVE":
            raise ValueError("output is not a WAVE file")
        while True:
            chunk = handle.read(4)
            if len(chunk) != 4:
                raise ValueError("WAV fmt chunk is missing")
            size_raw = handle.read(4)
            if len(size_raw) != 4:
                raise ValueError("truncated WAV chunk size")
            size = int.from_bytes(size_raw, "little")
            if chunk == b"fmt ":
                payload = handle.read(size)
                if len(payload) < 8:
                    raise ValueError("truncated WAV fmt chunk")
                return int.from_bytes(payload[4:8], "little")
            handle.seek(size + (size % 2), 1)


def validate_paths(runtime, talker, codec, output):
    errors = []
    for label, path in (("runtime", runtime), ("talker", talker), ("codec", codec)):
        if not path.is_file():
            errors.append(f"missing {label}: {path}")
    if not output.is_absolute():
        errors.append("output must be an absolute path")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description="probe Qwen3 1.7B CustomVoice GGUF without promotion")
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--talker", required=True, type=Path)
    parser.add_argument("--codec", required=True, type=Path)
    parser.add_argument("--voice", default="vivian")
    parser.add_argument("--text", default="同源量化语音候选正在进行独立验收。")
    parser.add_argument("--instruct", default="")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args(argv)
    timeout = max(10.0, min(args.timeout, 600.0))
    errors = validate_paths(args.runtime, args.talker, args.codec, args.output)
    result = {
        "ok": False,
        "promotion": "blocked_pending_quality_and_human_acceptance",
        "engine": "crispasr-gguf",
        "backend": BACKEND,
        "talker": str(args.talker),
        "codec": str(args.codec),
        "voice": args.voice,
        "instruct_requested": bool(args.instruct),
        "seed": args.seed,
    }
    if errors:
        result["errors"] = errors
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    command = build_command(args.runtime, args.talker, args.codec, args.voice, args.text,
                            args.output, args.instruct, args.seed)
    result["command"] = command
    started = time.monotonic()
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        result["errors"] = [f"candidate synthesis exceeded {timeout:g} seconds"]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    result["elapsed_s"] = round(time.monotonic() - started, 3)
    result["exit_code"] = completed.returncode
    result["stderr"] = completed.stderr[-2000:]
    if completed.returncode != 0 or not args.output.is_file() or args.output.stat().st_size == 0:
        result["errors"] = ["candidate did not produce a non-empty WAV"]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    try:
        sample_rate = wav_sample_rate(args.output)
    except ValueError as exc:
        result["errors"] = [str(exc)]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    result["output"] = str(args.output)
    result["output_bytes"] = args.output.stat().st_size
    result["sample_rate"] = sample_rate
    if sample_rate < MIN_SAMPLE_RATE:
        result["errors"] = [f"sample rate {sample_rate} is below {MIN_SAMPLE_RATE}"]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    result["ok"] = True
    result["next_gate"] = "same-prompt Qwen-FP16 comparison, STT, and human playback"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
