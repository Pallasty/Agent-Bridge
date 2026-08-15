#!/usr/bin/env python3
"""Agent Bridge adapter for the pinned, default-off OmniVoice ONNX candidate."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--manifest", type=Path)
    args = ap.parse_args()
    language = "Chinese" if any("\u3400" <= char <= "\u9fff" for char in args.text) else "English"
    bundle = Path(__file__).with_name("omnivoice_onnx_bundle_synth.py")
    with tempfile.TemporaryDirectory(prefix="ab-omnivoice-receipt-") as raw:
        report = Path(raw) / "report.json"
        command = [sys.executable, str(bundle), "--text", args.text,
                   "--language", language, "--wav", str(args.output),
                   "--report", str(report), "--steps", "32"]
        if args.manifest:
            command.extend(["--manifest", str(args.manifest)])
        proc = subprocess.run(command, capture_output=True, text=True)
        if proc.returncode != 0 or not args.output.is_file() or not report.is_file():
            print(json.dumps({"ok": False, "backend": "omnivoice",
                              "detail": (proc.stderr or proc.stdout)[-600:]}, ensure_ascii=False))
            return 1
        data = json.loads(report.read_text())
    bundle_receipt = data["bundle"]
    print(json.dumps({
        "ok": True, "backend": "omnivoice", "runtime": "onnxruntime",
        "voice": "auto", "sample_rate": 24000, "language": language.lower(),
        "manifest": bundle_receipt["manifest"],
        "manifest_status": bundle_receipt["manifest_status"],
        "hashes_verified": bundle_receipt["hashes_verified"],
        "steps": bundle_receipt["decode_steps"], "rtf": data["rtf"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
