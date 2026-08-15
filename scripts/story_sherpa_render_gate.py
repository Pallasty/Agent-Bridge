#!/usr/bin/env python3
"""S5B integrity-gated Sherpa three-voice render and Chinese ASR receipt."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, Callable


MODEL_ASSET_SPECS = {
    "date.fst": {
        "size": 59154,
        "sha256": "eb8aa079ae3cb81d8f4404992f39d61a0cb990947512b5b8d1e54d1f6980e718",
    },
    "lexicon.txt": {
        "size": 2042943,
        "sha256": "ab2e61d357551e7b24ddd965d924aca784c20165ff58c150794e539c6b5e9e35",
    },
    "model.onnx": {
        "size": 30482262,
        "sha256": "5511d651b7840c0a93a6bbfd4afd070a2c7f39ca1ec3ff2ecd73191519bbb852",
    },
    "new_heteronym.fst": {
        "size": 21974,
        "sha256": "ca14b2127e27baa571664e4bb791e143e7425f56a6bc29db08d74f97e6aa4e29",
    },
    "number.fst": {
        "size": 64482,
        "sha256": "743f402181fcfebf76cc2f0546b71fa26476e626fbe4e460fb7b4c3a7a8bd5bd",
    },
    "phone.fst": {
        "size": 88630,
        "sha256": "1ac2b6fa56b1442320c4de7db08353bab8963a2b57f365eebcdd3a2d3562f8d7",
    },
    "rule.far": {
        "size": 180717014,
        "sha256": "b090ed05e333fe125b62d8b1de5f1a1d4579fb237c606e7ac0b84707c863a01f",
    },
    "speakers.txt": {
        "size": 1392,
        "sha256": "50a825fc9a89172eee04a4d68869d933d0eca0d847f3b6fcffff9514cc72442d",
    },
    "tokens.txt": {
        "size": 1671,
        "sha256": "50b45a7b7de1752fd3c7b4755661c285f1547f59186eca2281089a81307ad953",
    },
}
SHERPA_ASR_BINARY_SHA256 = (
    "801fbe5b3269f55f1e29421092a6b0d2f492d1ea0b94e9210a26533b89cd522b"
)
SHERPA_ASR_MODEL_SPECS = {
    "tiny-encoder.int8.onnx": {
        "size": 12937772,
        "sha256": "d24fb083ae3b1041fc24e97971d60e280c9342201fbb67b0ab428a8b4a51a434",
    },
    "tiny-decoder.int8.onnx": {
        "size": 89855401,
        "sha256": "d2fece8dd42771f1df975c6c0445770d0c292bf7547c2cae04a6c0cc57540925",
    },
    "tiny-tokens.txt": {
        "size": 816730,
        "sha256": "b34b360dbb493e781e479794586d661700670d65564001f23024971d1f2fa126",
    },
}
SENSE_VOICE_MODEL_SPECS = {
    "LICENSE": {
        "size": 71,
        "sha256": "221c6df10b0931a5629adad671ea48fb7747e034c414b6d2bfa275bc3dd4ea17",
    },
    "model.int8.onnx": {
        "size": 239233841,
        "sha256": "c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51",
    },
    "tokens.txt": {
        "size": 315894,
        "sha256": "f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc",
    },
}
MAX_CER = 0.2


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_model_dir(
    model_dir: Path,
    *,
    specs: dict[str, dict[str, Any]] = MODEL_ASSET_SPECS,
) -> list[dict[str, Any]]:
    rows = []
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
        if not path.is_file():
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
        rows.append(row)
    return rows


def _character_error_rate(reference: str, transcript: str) -> float:
    path = Path(__file__).with_name("story_voice_audition.py")
    spec = importlib.util.spec_from_file_location("s5_audition_for_render", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("audition_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.character_error_rate(reference, transcript)


def inspect_wav(path: Path) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "valid": False,
        "path": path.name,
        "sha256": None,
        "channels": None,
        "sample_width": None,
        "sample_rate": None,
        "frames": None,
        "duration_seconds": None,
        "reason": None,
    }
    try:
        with wave.open(str(path), "rb") as audio:
            evidence.update(
                {
                    "channels": audio.getnchannels(),
                    "sample_width": audio.getsampwidth(),
                    "sample_rate": audio.getframerate(),
                    "frames": audio.getnframes(),
                }
            )
    except (OSError, EOFError, wave.Error) as error:
        evidence["reason"] = f"invalid_wav:{error}"
        return evidence
    if (
        evidence["channels"] != 1
        or evidence["sample_width"] != 2
        or evidence["sample_rate"] <= 0
        or evidence["frames"] <= 0
    ):
        evidence["reason"] = "unsupported_or_empty_pcm"
        return evidence
    evidence["duration_seconds"] = evidence["frames"] / evidence["sample_rate"]
    evidence["sha256"] = sha256_file(path)
    evidence["valid"] = True
    evidence["reason"] = "verified_pcm_wav"
    return evidence


def _parse_receipt(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def _base_report(
    plan: dict[str, Any],
    binary: Path,
    model_dir: Path,
    output_dir: Path,
    model_files: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": "agent_bridge.story_sherpa_render_pack.v1",
        "plan_id": plan.get("plan_id"),
        "status": "blocked",
        "blockers": [],
        "binary": str(binary),
        "binary_sha256": None,
        "model_dir": str(model_dir),
        "model_files": model_files,
        "output_dir": str(output_dir),
        "execution": {"attempted": False},
        "artifacts": [],
        "runtime_effects": {
            "downloads_models": False,
            "renders_audio": False,
            "plays_audio": False,
            "writes_memory": False,
        },
    }


def render_pack(
    plan: dict[str, Any],
    *,
    binary: Path,
    model_dir: Path,
    output_dir: Path,
    specs: dict[str, dict[str, Any]] = MODEL_ASSET_SPECS,
    runner: Callable[..., Any] = subprocess.run,
    asr: Callable[[Path, str], dict[str, Any]] | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    model_files = verify_model_dir(model_dir, specs=specs)
    report = _base_report(plan, binary, model_dir, output_dir, model_files)
    if not all(row["verified"] for row in model_files):
        report["blockers"] = ["model_integrity_failed"]
        return report
    if not binary.is_file() or not os.access(binary, os.X_OK):
        report["blockers"] = ["binary_not_executable"]
        return report
    if output_dir.exists():
        report["blockers"] = ["output_dir_already_exists"]
        return report
    items = plan.get("items", [])
    if (
        plan.get("status") != "audition_plan_ready_no_audio"
        or len(items) != 3
        or len({row.get("blind_label") for row in items}) != 3
        or len({row.get("speaker_id") for row in items}) != 3
    ):
        report["blockers"] = ["audition_plan_invalid"]
        return report

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    partial = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.partial-",
            dir=output_dir.parent,
        )
    )
    report["binary_sha256"] = sha256_file(binary)
    report["execution"] = {"attempted": True, "completed_items": 0}
    report["runtime_effects"]["renders_audio"] = True
    voice_map = ",".join(
        f"{row['blind_label']}={row['speaker_id']}" for row in items
    )
    environment = os.environ.copy()
    environment.update(
        {
            "AB_TTS_SHERPA_MODEL_DIR": str(model_dir),
            "AB_TTS_SHERPA_VOICE_MAP": voice_map,
        }
    )
    try:
        for item in items:
            label = item["blind_label"]
            wav_path = partial / f"{label}.wav"
            command = [
                str(binary),
                "--text",
                item["text"],
                "--voice",
                label,
                "--speed",
                "1.0",
                "--out",
                str(wav_path),
            ]
            try:
                process = runner(
                    command,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    env=environment,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                report["status"] = "failed"
                report["blockers"] = [f"render_timeout:{label}"]
                return report
            except OSError:
                report["status"] = "failed"
                report["blockers"] = [f"render_start_failed:{label}"]
                return report
            receipt = _parse_receipt(process.stdout)
            if process.returncode != 0 or receipt.get("ok") is not True:
                report["status"] = "failed"
                report["blockers"] = [f"render_failed:{label}"]
                return report
            wav = inspect_wav(wav_path)
            if not wav["valid"]:
                report["status"] = "failed"
                report["blockers"] = [f"wav_validation_failed:{label}"]
                return report
            artifact = {
                "blind_label": label,
                "role_id": item["role_id"],
                "speaker_id": item["speaker_id"],
                "voice_profile_version": item["voice_profile_version"],
                "reference_text": item["text"],
                "synth_receipt": {
                    "backend": receipt.get("backend"),
                    "sample_rate": receipt.get("sample_rate"),
                    "speakers": receipt.get("speakers"),
                },
                "wav": wav,
                "asr": None,
            }
            if asr is not None:
                asr_receipt = asr(wav_path, item["text"])
                if asr_receipt.get("ok") is not True:
                    report["status"] = "failed"
                    report["blockers"] = [f"asr_failed:{label}"]
                    return report
                cer = _character_error_rate(
                    item["text"], str(asr_receipt.get("transcript", ""))
                )
                artifact["asr"] = dict(asr_receipt, cer=cer)
                if cer > MAX_CER:
                    report["blockers"].append(
                        f"asr_cer_above_threshold:{label}"
                    )
            report["artifacts"].append(artifact)
            report["execution"]["completed_items"] += 1

        report["blockers"] = sorted(set(report["blockers"]))
        if asr is None:
            report["status"] = "three_voice_rendered_asr_pending"
            report["blockers"] = ["asr_pending"]
        elif report["blockers"]:
            report["status"] = "three_voice_rendered_asr_review_failed"
        else:
            report["status"] = "three_voice_render_asr_verified"
        receipt_path = partial / "render_receipt.json"
        receipt_path.write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        partial.rename(output_dir)
        return report
    finally:
        if partial.exists():
            shutil.rmtree(partial)


class WhisperAsr:
    def __init__(
        self,
        *,
        binary: Path,
        model: Path,
        model_sha256: str,
        ffmpeg: str = "ffmpeg",
        timeout_seconds: int = 120,
    ) -> None:
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError("whisper_binary_not_executable")
        if not model.is_file() or sha256_file(model) != model_sha256:
            raise ValueError("whisper_model_integrity_failed")
        self.binary = binary
        self.model = model
        self.model_sha256 = model_sha256
        self.ffmpeg = ffmpeg
        self.timeout_seconds = timeout_seconds

    def __call__(self, audio_path: Path, _reference: str) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="ab-s5b-asr-") as root:
            normalized = Path(root) / "input.wav"
            conversion = subprocess.run(
                [
                    self.ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(audio_path),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(normalized),
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            if conversion.returncode != 0:
                return {"ok": False, "error": "asr_audio_conversion_failed"}
            process = subprocess.run(
                [
                    str(self.binary),
                    "-m",
                    str(self.model),
                    "-f",
                    str(normalized),
                    "-l",
                    "zh",
                    "-nt",
                    "-np",
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        if process.returncode != 0:
            return {"ok": False, "error": "whisper_inference_failed"}
        return {
            "ok": True,
            "transcript": process.stdout.strip(),
            "model": self.model.name,
            "model_sha256": self.model_sha256,
        }


class SherpaWhisperAsr:
    def __init__(
        self,
        *,
        binary: Path,
        runtime_lib_dir: Path,
        model_dir: Path,
        binary_sha256: str = SHERPA_ASR_BINARY_SHA256,
        specs: dict[str, dict[str, Any]] = SHERPA_ASR_MODEL_SPECS,
        encoder_name: str = "tiny-encoder.int8.onnx",
        decoder_name: str = "tiny-decoder.int8.onnx",
        tokens_name: str = "tiny-tokens.txt",
        runner: Callable[..., Any] = subprocess.run,
        timeout_seconds: int = 120,
    ) -> None:
        if (
            not binary.is_file()
            or not os.access(binary, os.X_OK)
            or sha256_file(binary) != binary_sha256
        ):
            raise ValueError("sherpa_asr_binary_integrity_failed")
        model_rows = verify_model_dir(model_dir, specs=specs)
        if not all(row["verified"] for row in model_rows):
            raise ValueError("sherpa_asr_model_integrity_failed")
        self.binary = binary
        self.runtime_lib_dir = runtime_lib_dir
        self.model_dir = model_dir
        self.encoder_name = encoder_name
        self.decoder_name = decoder_name
        self.tokens_name = tokens_name
        self.runner = runner
        self.timeout_seconds = timeout_seconds
        bundle_identity = {
            row["path"]: row["sha256"] for row in model_rows
        }
        self.model_sha256 = hashlib.sha256(
            json.dumps(
                bundle_identity,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def __call__(self, audio_path: Path, _reference: str) -> dict[str, Any]:
        command = [
            str(self.binary),
            f"--whisper-encoder={self.model_dir / self.encoder_name}",
            f"--whisper-decoder={self.model_dir / self.decoder_name}",
            f"--tokens={self.model_dir / self.tokens_name}",
            "--whisper-language=zh",
            "--whisper-task=transcribe",
            "--whisper-tail-paddings=300",
            "--model-type=whisper",
            "--num-threads=4",
            str(audio_path),
        ]
        environment = os.environ.copy()
        environment["LD_LIBRARY_PATH"] = str(self.runtime_lib_dir)
        try:
            process = self.runner(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=environment,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "sherpa_whisper_timeout"}
        except OSError:
            return {"ok": False, "error": "sherpa_whisper_start_failed"}
        if process.returncode != 0:
            return {"ok": False, "error": "sherpa_whisper_inference_failed"}
        receipt = _parse_receipt(process.stdout)
        transcript = str(receipt.get("text", "")).strip()
        if not transcript:
            return {"ok": False, "error": "sherpa_whisper_empty_transcript"}
        return {
            "ok": True,
            "transcript": transcript,
            "language": receipt.get("lang", "zh"),
            "model": "sherpa-onnx-whisper-tiny-int8",
            "model_sha256": self.model_sha256,
        }


class SherpaSenseVoiceAsr:
    def __init__(
        self,
        *,
        binary: Path,
        runtime_lib_dir: Path,
        model_dir: Path,
        binary_sha256: str = SHERPA_ASR_BINARY_SHA256,
        specs: dict[str, dict[str, Any]] = SENSE_VOICE_MODEL_SPECS,
        runner: Callable[..., Any] = subprocess.run,
        timeout_seconds: int = 120,
    ) -> None:
        if (
            not binary.is_file()
            or not os.access(binary, os.X_OK)
            or sha256_file(binary) != binary_sha256
        ):
            raise ValueError("sherpa_asr_binary_integrity_failed")
        model_rows = verify_model_dir(model_dir, specs=specs)
        if not all(row["verified"] for row in model_rows):
            raise ValueError("sense_voice_model_integrity_failed")
        self.binary = binary
        self.runtime_lib_dir = runtime_lib_dir
        self.model_dir = model_dir
        self.runner = runner
        self.timeout_seconds = timeout_seconds
        bundle_identity = {
            row["path"]: row["sha256"] for row in model_rows
        }
        self.model_sha256 = hashlib.sha256(
            json.dumps(
                bundle_identity,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def __call__(self, audio_path: Path, _reference: str) -> dict[str, Any]:
        command = [
            str(self.binary),
            f"--sense-voice-model={self.model_dir / 'model.int8.onnx'}",
            f"--tokens={self.model_dir / 'tokens.txt'}",
            "--sense-voice-language=zh",
            "--sense-voice-use-itn=true",
            "--model-type=sense_voice",
            "--num-threads=4",
            str(audio_path),
        ]
        environment = os.environ.copy()
        environment["LD_LIBRARY_PATH"] = str(self.runtime_lib_dir)
        try:
            process = self.runner(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=environment,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "sense_voice_timeout"}
        except OSError:
            return {"ok": False, "error": "sense_voice_start_failed"}
        if process.returncode != 0:
            return {"ok": False, "error": "sense_voice_inference_failed"}
        receipt = _parse_receipt(process.stdout)
        transcript = str(receipt.get("text", "")).strip()
        if not transcript:
            return {"ok": False, "error": "sense_voice_empty_transcript"}
        return {
            "ok": True,
            "transcript": transcript,
            "language": receipt.get("lang", "<|zh|>"),
            "model": "sherpa-onnx-sense-voice-int8-2024-07-17",
            "model_sha256": self.model_sha256,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--whisper-cli", type=Path)
    parser.add_argument("--whisper-model", type=Path)
    parser.add_argument("--whisper-model-sha256")
    parser.add_argument("--sherpa-asr-runtime", type=Path)
    parser.add_argument("--sherpa-asr-model-dir", type=Path)
    parser.add_argument("--sense-voice-model-dir", type=Path)
    args = parser.parse_args()
    asr = None
    if args.sense_voice_model_dir:
        if not args.sherpa_asr_runtime:
            parser.error("Sherpa ASR runtime is required for SenseVoice")
        if args.sherpa_asr_model_dir:
            parser.error("choose exactly one Sherpa ASR model")
        asr = SherpaSenseVoiceAsr(
            binary=args.sherpa_asr_runtime / "bin" / "sherpa-onnx-offline",
            runtime_lib_dir=args.sherpa_asr_runtime / "lib",
            model_dir=args.sense_voice_model_dir,
        )
    elif args.sherpa_asr_runtime or args.sherpa_asr_model_dir:
        if not (args.sherpa_asr_runtime and args.sherpa_asr_model_dir):
            parser.error("both Sherpa ASR arguments are required together")
        if args.whisper_cli or args.whisper_model or args.whisper_model_sha256:
            parser.error("choose exactly one ASR adapter")
        asr = SherpaWhisperAsr(
            binary=args.sherpa_asr_runtime / "bin" / "sherpa-onnx-offline",
            runtime_lib_dir=args.sherpa_asr_runtime / "lib",
            model_dir=args.sherpa_asr_model_dir,
        )
    if args.whisper_cli or args.whisper_model or args.whisper_model_sha256:
        if not (
            args.whisper_cli
            and args.whisper_model
            and args.whisper_model_sha256
        ):
            parser.error("all whisper arguments are required together")
        asr = WhisperAsr(
            binary=args.whisper_cli,
            model=args.whisper_model,
            model_sha256=args.whisper_model_sha256,
        )
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    result = render_pack(
        plan,
        binary=args.binary,
        model_dir=args.model_dir,
        output_dir=args.output_dir,
        asr=asr,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "three_voice_render_asr_verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
