#!/usr/bin/env python3
"""Run resumable Qwen/OmniVoice matched-duration replacement corpus synthesis."""

import argparse
import json
import random
import resource
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--model-dir", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--omnivoice-script", type=Path,
                    default=Path(__file__).with_name("omnivoice_onnx_bundle_synth.py"))
    args = ap.parse_args()
    corpus = json.loads(args.corpus.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    model = Qwen3TTSModel.from_pretrained(
        str(args.model_dir), dtype=torch.bfloat16, low_cpu_mem_usage=True
    )
    load_seconds = time.perf_counter() - started
    summary = []
    for case in corpus["cases"]:
        case_dir = args.output_dir / case["id"]
        case_dir.mkdir(exist_ok=True)
        qwen_wav = case_dir / "qwen.wav"
        qwen_report = case_dir / "qwen.json"
        if not qwen_report.exists():
            random.seed(corpus["seed"])
            np.random.seed(corpus["seed"])
            torch.manual_seed(corpus["seed"])
            started = time.perf_counter()
            wavs, sample_rate = model.generate_custom_voice(
                text=case["text"], language=case["language"],
                speaker=corpus["speaker"]
            )
            generation_seconds = time.perf_counter() - started
            waveform = np.asarray(wavs[0], dtype=np.float32)
            sf.write(qwen_wav, waveform, sample_rate, subtype="PCM_16")
            qwen = {
                "text": case["text"], "language": case["language"],
                "speaker": corpus["speaker"], "seed": corpus["seed"],
                "generation_seconds": generation_seconds,
                "audio_seconds": len(waveform) / sample_rate,
                "rtf": generation_seconds / (len(waveform) / sample_rate),
                "sample_rate": sample_rate,
                "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            }
            qwen_report.write_text(json.dumps(qwen, ensure_ascii=False, indent=2) + "\n")
        else:
            qwen = json.loads(qwen_report.read_text())

        omni_wav = case_dir / "omnivoice.wav"
        omni_report = case_dir / "omnivoice.json"
        if not omni_report.exists():
            subprocess.run([
                sys.executable, str(args.omnivoice_script), "--text", case["text"],
                "--language", case.get("omnivoice_language", case["language"]),
                "--duration", str(qwen["audio_seconds"]), "--wav", str(omni_wav),
                "--report", str(omni_report), "--seed", str(corpus["seed"]),
                "--steps", "32",
            ], check=True)
        omni = json.loads(omni_report.read_text())
        summary.append({"id": case["id"], "qwen": qwen, "omnivoice": {
            "generation_seconds": omni["generation_seconds"],
            "audio_seconds": omni["audio_seconds"], "rtf": omni["rtf"],
        }})

    report = {
        "schema": "agent_bridge.tts_replacement_corpus_gate.v0",
        "corpus": str(args.corpus.resolve()), "model_dir": str(args.model_dir.resolve()),
        "qwen_load_seconds": load_seconds, "results": summary,
    }
    (args.output_dir / "synthesis-summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
