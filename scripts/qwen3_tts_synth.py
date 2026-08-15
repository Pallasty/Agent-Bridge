#!/usr/bin/env python3
"""Explicit Qwen3-TTS CustomVoice WAV adapter for Agent-Bridge.

Run this file with the isolated Python environment that owns ``qwen-tts``; it is
intentionally not a dependency of the Agent-Bridge service or its system Python.
The wrapper writes one PCM WAV and one JSON receipt to stdout, so the caller can
retain the same file/STT and physical-playback gates used by the native macOS path.
"""
import argparse
import json
import os
import sys


# The 1.7B CustomVoice checkpoint is the expression-control baseline. The
# smaller 0.6B checkpoint remains caller-selectable but is not the default.
DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
DEFAULT_SPEAKER = "Serena"


def _device_and_dtype(requested):
    import torch

    if requested == "auto":
        requested = "mps" if torch.backends.mps.is_available() else "cpu"
    if requested == "mps":
        if not torch.backends.mps.is_available():
            raise RuntimeError("MPS was requested but is unavailable in this PyTorch build")
        return "mps", torch.float16
    if requested == "cpu":
        return "cpu", torch.float32
    raise RuntimeError("device must be auto, mps, or cpu")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--speaker", default=DEFAULT_SPEAKER)
    ap.add_argument("--instruct", default="")
    ap.add_argument("--model", default=os.environ.get("AB_QWEN3_TTS_MODEL", DEFAULT_MODEL))
    ap.add_argument("--device", choices=["auto", "mps", "cpu"],
                    default=os.environ.get("AB_QWEN3_TTS_DEVICE", "auto"))
    args = ap.parse_args()
    try:
        import soundfile as sf
        from qwen_tts import Qwen3TTSModel

        device, dtype = _device_and_dtype(args.device)
        # Do not request FlashAttention: that is a CUDA optimization, not an MPS requirement.
        model = Qwen3TTSModel.from_pretrained(args.model, device_map=device, dtype=dtype)
        wavs, sample_rate = model.generate_custom_voice(
            text=args.text,
            language="Chinese",
            speaker=args.speaker,
            instruct=args.instruct or None,
        )
        sf.write(args.output, wavs[0], sample_rate)
        print(json.dumps({
            "ok": True,
            "backend": "qwen3",
            "model": args.model,
            "voice": args.speaker,
            "sample_rate": sample_rate,
            "device": device,
            "dtype": str(dtype).removeprefix("torch."),
            "instruct_applied": bool(args.instruct),
        }, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "backend": "qwen3", "detail": str(exc)[:600]}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
