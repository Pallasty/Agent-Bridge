#!/usr/bin/env python3
"""Synthesize text with a pinned OmniVoice ONNX composition manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

import numpy as np
import onnxruntime as ort
import soundfile as sf
from scipy.signal import resample_poly
from tokenizers import Tokenizer


DEFAULT_MANIFEST = Path(
    "/Data/Models/onnx-controls/OmniVoice-staged-quantization/"
    "recommended-fp16-embeddings.json"
)
DECODE_SCRIPT = Path(__file__).with_name("omnivoice_onnx_official_decode.py")
LANGUAGE_IDS = {"english": "en", "en": "en", "chinese": "zh", "zh": "zh"}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(manifest, verify_hashes=True):
    required = {"tokenizer", "embeddings", "llm", "heads", "decoder"}
    missing = required - set(manifest.get("components", {}))
    if missing:
        raise ValueError(f"manifest missing components: {sorted(missing)}")
    for name, item in manifest["components"].items():
        path = Path(item["path"])
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            raise ValueError(f"{name} path/size mismatch: {path}")
        if verify_hashes and sha256(path) != item["sha256"]:
            raise ValueError(f"{name} SHA-256 mismatch: {path}")
        external = item.get("external_data")
        if external:
            ext_path = Path(external["path"])
            if not ext_path.is_file() or ext_path.stat().st_size != external["bytes"]:
                raise ValueError(f"{name} external-data path/size mismatch: {ext_path}")
            if verify_hashes and sha256(ext_path) != external["sha256"]:
                raise ValueError(f"{name} external-data SHA-256 mismatch: {ext_path}")


def character_weight(text):
    total = 0.0
    for char in text:
        code = ord(char)
        category = unicodedata.category(char)
        if char == " ":
            value = 0.2
        elif category.startswith("M"):
            value = 0.0
        elif category.startswith(("P", "S")):
            value = 0.5
        elif category.startswith("Z"):
            value = 0.2
        elif category.startswith("N"):
            value = 3.5
        elif 0x3040 <= code <= 0x30FF:
            value = 2.2
        elif 0x2E80 <= code <= 0x9FFF or 0xF900 <= code <= 0xFAFF or code > 0x20000:
            value = 3.0
        elif 0xAC00 <= code <= 0xD7AF:
            value = 2.5
        else:
            value = 1.0
        total += value
    return total


def estimate_target_frames(text, ref_text="Nice to meet you.", ref_frames=25):
    reference_weight = character_weight(ref_text)
    raw = character_weight(text) / (reference_weight / float(ref_frames))
    estimated = 50.0 * (raw / 50.0) ** (1.0 / 3.0) if raw < 50.0 else raw
    return max(1, int(estimated))


def combine_text(text, ref_text=None):
    combined = f"{ref_text.strip()} {text.strip()}" if ref_text else text.strip()
    combined = re.sub(r"[\r\n]+", "", combined).replace("（", "(").replace("）", ")")
    combined = re.sub(r"[ \t]+", " ", combined)
    combined = re.sub(r"(?<=[\u4e00-\u9fff])\s+|\s+(?=[\u4e00-\u9fff])", "", combined)
    return combined


def build_prompt(tokenizer_path, text, language, duration=None, frame_rate=25,
                 ref_text=None, ref_codes=None):
    language_id = LANGUAGE_IDS.get(language.lower(), language)
    ref_frames = ref_codes.shape[-1] if ref_codes is not None else 25
    target_frames = (max(1, int(round(duration * frame_rate))) if duration is not None else
                     estimate_target_frames(text, ref_text or "Nice to meet you.", ref_frames))
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    denoise = "<|denoise|>" if ref_codes is not None else ""
    style = f"{denoise}<|lang_start|>{language_id}<|lang_end|><|instruct_start|>None<|instruct_end|>"
    wrapped = f"<|text_start|>{combine_text(text, ref_text)}<|text_end|>"
    style_ids = np.asarray(tokenizer.encode(style).ids, dtype=np.int64)
    text_ids = np.asarray(tokenizer.encode(wrapped).ids, dtype=np.int64)
    target = np.full(target_frames, 1024, dtype=np.int64)
    if ref_codes is None:
        sequence = np.concatenate((style_ids, text_ids, target))
        conditional = np.tile(sequence[None, None, :], (1, 8, 1))
        ref_frames = 0
    else:
        codes = np.asarray(ref_codes, dtype=np.int64)
        if codes.ndim != 2 or codes.shape[0] != 8:
            raise ValueError(f"ref_codes must have shape (8, frames), got {codes.shape}")
        conditional = np.stack([
            np.concatenate((style_ids, text_ids, codes[index], target)) for index in range(8)
        ])[None, :, :]
        sequence = conditional[0, 0]
    unconditional = np.tile(target[None, None, :], (1, 8, 1))
    conditional_mask = np.zeros((1, sequence.size), dtype=np.bool_)
    conditional_mask[:, -(target_frames + ref_frames):] = True
    unconditional_mask = np.ones((1, target_frames), dtype=np.bool_)
    return {
        "conditional_input_ids": conditional,
        "conditional_audio_mask": conditional_mask,
        "unconditional_input_ids": unconditional,
        "unconditional_audio_mask": unconditional_mask,
        "target_len": np.asarray(target_frames, dtype=np.int64),
        "conditional_length": np.asarray(sequence.size, dtype=np.int64),
        "language": np.asarray(language_id),
    }


def encode_reference(audio_path, components):
    waveform, sample_rate = sf.read(audio_path, dtype="float32", always_2d=False)
    if waveform.ndim > 1:
        waveform = waveform.mean(axis=1)
    wav24 = (resample_poly(waveform, 24000, sample_rate).astype(np.float32)
             if sample_rate != 24000 else waveform)
    wav16 = (resample_poly(waveform, 16000, sample_rate).astype(np.float32)
             if sample_rate != 16000 else waveform)
    options = ort.SessionOptions()
    options.log_severity_level = 3
    def load(name):
        return ort.InferenceSession(components[name]["path"], options,
                                    providers=["CPUExecutionProvider"])
    acoustic = load("acoustic_encoder").run(
        ["acoustic_features"], {"waveform_24k": wav24[None, None, :].astype(np.float16)}
    )[0]
    semantic = load("semantic_encoder").run(
        ["semantic_features"], {"waveform_16k": wav16[None, :].astype(np.float16)}
    )[0]
    frames = min(acoustic.shape[2], semantic.shape[2])
    codes = load("quantizer_encoder").run(
        ["codes"], {"acoustic_features": acoustic[:, :, :frames],
                    "semantic_features": semantic[:, :, :frames]}
    )[0]
    return codes[:, 0, :]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--text", required=True)
    parser.add_argument("--language", required=True, help="English/en, Chinese/zh, or OmniVoice language ID")
    parser.add_argument("--duration", type=float,
                        help="Optional duration override; otherwise use the bundled estimator validated for English/Chinese")
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--steps", type=int, default=32,
                        help="Iterative reveal steps; 32 preserves the official default")
    parser.add_argument("--ref-audio", type=Path)
    parser.add_argument("--ref-text")
    parser.add_argument("--skip-hash-verification", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    validate_manifest(manifest, verify_hashes=not args.skip_hash_verification)
    components = manifest["components"]
    if (args.ref_audio is None) != (args.ref_text is None):
        parser.error("--ref-audio and --ref-text must be provided together")
    if args.ref_audio is not None:
        encoder_names = {"acoustic_encoder", "semantic_encoder", "quantizer_encoder"}
        if not encoder_names.issubset(components):
            parser.error("manifest does not contain reference encoder components")
        ref_codes = encode_reference(args.ref_audio, components)
    else:
        ref_codes = None
    prompt = build_prompt(components["tokenizer"]["path"], args.text, args.language,
                          args.duration, ref_text=args.ref_text, ref_codes=ref_codes)
    args.wav.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="omnivoice-onnx-prompt-", dir=args.report.parent) as raw:
        prompt_path = Path(raw) / "prompt.npz"
        np.savez(prompt_path, **prompt)
        command = [
            sys.executable, str(DECODE_SCRIPT), "--prompt", str(prompt_path),
            "--embeddings", components["embeddings"]["path"],
            "--llm", components["llm"]["path"], "--heads", components["heads"]["path"],
            "--decoder", components["decoder"]["path"], "--wav", str(args.wav),
            "--report", str(args.report), "--seed", str(args.seed),
            "--steps", str(args.steps),
        ]
        subprocess.run(command, check=True)
    report = json.loads(args.report.read_text())
    report["prompt"] = "bundle-generated from pinned tokenizer, text, language, and duration"
    report["bundle"] = {
        "manifest": str(args.manifest.resolve()),
        "manifest_status": manifest.get("status"),
        "hashes_verified": not args.skip_hash_verification,
        "text": args.text,
        "language": str(prompt["language"]),
        "requested_duration_seconds": args.duration,
        "duration_source": "explicit" if args.duration is not None else "rule_estimator",
        "effective_duration_seconds": int(prompt["target_len"]) / 25.0,
        "target_frames": int(prompt["target_len"]),
        "mode": "voice_clone" if ref_codes is not None else "auto_voice",
        "reference_audio": str(args.ref_audio.resolve()) if args.ref_audio else None,
        "reference_text": args.ref_text,
        "reference_frames": int(ref_codes.shape[-1]) if ref_codes is not None else 0,
        "decode_steps": args.steps,
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"wav": str(args.wav), "report": str(args.report),
                      "bundle": report["bundle"], "rtf": report["rtf"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
