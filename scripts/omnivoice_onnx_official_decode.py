#!/usr/bin/env python3
"""Run OmniVoice's official iterative decoding semantics over split ONNX components."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import soundfile as sf


def log_softmax(values):
    maximum = values.max(axis=-1, keepdims=True)
    shifted = values - maximum
    return shifted - np.log(np.exp(shifted).sum(axis=-1, keepdims=True))


def schedule(target_frames, codebooks, steps, shift):
    linear = np.linspace(0.0, 1.0, steps + 1)
    times = shift * linear / (1 + (shift - 1) * linear)
    total = target_frames * codebooks
    remaining = total
    result = []
    for step in range(steps):
        count = remaining if step == steps - 1 else min(
            math.ceil(total * (times[step + 1] - times[step])), remaining
        )
        result.append(int(count))
        remaining -= int(count)
    if remaining != 0 or sum(result) != total:
        raise AssertionError("invalid reveal schedule")
    return result


def session(path):
    options = ort.SessionOptions()
    options.log_severity_level = 3
    return ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])


def forward(sessions, input_ids, audio_mask):
    embeddings = sessions["embeddings"].run(
        ["inputs_embeds"], {"input_ids": input_ids, "audio_mask": audio_mask}
    )[0]
    batch, sequence, _ = embeddings.shape
    attention = np.ones((batch, 1, sequence, sequence), dtype=np.bool_)
    hidden = sessions["llm"].run(
        ["hidden_states"], {"inputs_embeds": embeddings, "attention_mask": attention}
    )[0]
    return sessions["heads"].run(["logits"], {"hidden_states": hidden})[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--llm", type=Path, required=True)
    parser.add_argument("--heads", type=Path, required=True)
    parser.add_argument("--decoder", type=Path, required=True)
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument("--guidance-scale", type=float, default=2.0)
    parser.add_argument("--t-shift", type=float, default=0.1)
    parser.add_argument("--layer-penalty", type=float, default=5.0)
    parser.add_argument("--position-temperature", type=float, default=5.0)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    for path in (args.wav, args.report):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite {path}")
    source = np.load(args.prompt)
    conditional = source["conditional_input_ids"].copy()
    unconditional = source["unconditional_input_ids"].copy()
    conditional_mask = source["conditional_audio_mask"]
    unconditional_mask = source["unconditional_audio_mask"]
    target_frames = int(source["target_len"])
    codebooks = conditional.shape[1]
    mask_id = 1024
    generated = np.full((1, codebooks, target_frames), mask_id, dtype=np.int64)
    reveal_counts = schedule(target_frames, codebooks, args.steps, args.t_shift)
    rng = np.random.default_rng(args.seed)
    layer_ids = np.arange(codebooks, dtype=np.float32).reshape(1, codebooks, 1)
    sessions = {"embeddings": session(args.embeddings), "llm": session(args.llm),
                "heads": session(args.heads)}
    started = time.monotonic()
    trace = []
    for step, count in enumerate(reveal_counts):
        conditional_logits = forward(sessions, conditional, conditional_mask)[:, :, -target_frames:, :]
        unconditional_logits = forward(sessions, unconditional, unconditional_mask)[:, :, -target_frames:, :]
        conditional_lp = log_softmax(conditional_logits)
        unconditional_lp = log_softmax(unconditional_logits)
        guided = log_softmax(conditional_lp + args.guidance_scale * (conditional_lp - unconditional_lp))
        guided[..., mask_id] = -np.inf
        predicted = guided.argmax(axis=-1)
        scores = guided.max(axis=-1) - layer_ids * args.layer_penalty
        uniform = np.clip(rng.random(scores.shape), 1e-10, 1 - 1e-10)
        scores = scores / args.position_temperature + -np.log(-np.log(uniform))
        scores[generated != mask_id] = -np.inf
        indices = np.argpartition(scores.ravel(), -count)[-count:]
        flat_generated = generated.ravel()
        flat_generated[indices] = predicted.ravel()[indices]
        generated = flat_generated.reshape(generated.shape)
        conditional[:, :, -target_frames:] = generated
        unconditional[:, :, -target_frames:] = generated
        trace.append({"step": step + 1, "revealed": count,
                      "remaining": int(np.sum(generated == mask_id))})
    generation_seconds = time.monotonic() - started
    if np.any(generated == mask_id):
        raise AssertionError("decoding completed with masked tokens")
    decoder = session(args.decoder)
    decode_started = time.monotonic()
    waveform = decoder.run(["waveform_24k"], {"codes": generated[0, :, None, :]})[0].squeeze()
    decode_seconds = time.monotonic() - decode_started
    waveform = waveform.astype(np.float32)
    raw_peak = float(np.max(np.abs(waveform)))
    if raw_peak > 1e-6:
        waveform = waveform / raw_peak * 0.5
    args.wav.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.wav, waveform, 24000, subtype="PCM_16")
    report = {"schema": "agent_bridge.omnivoice_onnx_official_decode.v0",
              "prompt": str(args.prompt),
              "components": {"embeddings": str(args.embeddings), "llm": str(args.llm),
                             "heads": str(args.heads), "decoder": str(args.decoder)},
              "config": {"steps": args.steps, "guidance_scale": args.guidance_scale,
                         "t_shift": args.t_shift, "layer_penalty": args.layer_penalty,
                         "position_temperature": args.position_temperature, "seed": args.seed},
              "target_frames": target_frames, "generation_seconds": generation_seconds,
              "decode_seconds": decode_seconds, "audio_samples": int(waveform.size),
              "audio_seconds": float(waveform.size / 24000),
              "rtf": float(generation_seconds / (waveform.size / 24000)),
              "waveform": {"finite": bool(np.isfinite(waveform).all()), "raw_peak": raw_peak,
                           "peak": float(np.max(np.abs(waveform))),
                           "rms": float(np.sqrt(np.mean(waveform * waveform)))},
              "trace": trace, "wav": str(args.wav)}
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("generation_seconds", "decode_seconds", "audio_seconds", "rtf", "waveform")}, indent=2))


if __name__ == "__main__":
    main()
