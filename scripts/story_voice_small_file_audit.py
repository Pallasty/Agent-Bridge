#!/usr/bin/env python3
"""Acquire and statically audit allowlisted small files from a fixed revision."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
from pathlib import Path, PurePosixPath
from typing import Any, Callable


DEFAULT_REVISION = "3717103c6fa278c1810e97672c02b185a7239737"
DEFAULT_REPOSITORY = "pltobing/Qwen3-TTS-Streaming-ONNX"
DEFAULT_PATHS = [
    "README.md",
    "requirements.txt",
    "test_qwen3-tts-streaming_onnx.py",
    "configs/config.json",
    "configs/speech_tokenizer_config.json",
    "configs/preprocessor_config.json",
    "configs/tokenizer_config.json",
    "configs/vocab.json",
    "configs/merges.txt",
    "src/inference/qwen3_tts_inferencer_onnx.py",
    "src/utils/audio_utils.py",
]
ALLOWED_SUFFIXES = {".py", ".json", ".txt", ".md"}
ALLOWED_NAMES = {".gitattributes", ".gitignore", "LICENSE", "NOTICE"}
FORBIDDEN_SUFFIXES = {
    ".onnx",
    ".safetensors",
    ".bin",
    ".pt",
    ".pth",
    ".ckpt",
    ".gguf",
    ".wav",
    ".flac",
    ".mp3",
    ".ogg",
    ".m4a",
    ".npy",
    ".npz",
}
FORBIDDEN_DIRECTORIES = {
    "qwen3-tts_onnx",
    "audio_ref",
    "audio_synth",
    "logs",
}
NETWORK_IMPORTS = {
    "aiohttp",
    "ftplib",
    "httpx",
    "requests",
    "socket",
    "urllib3",
}
PROCESS_MODULES = {"subprocess", "multiprocessing"}
DYNAMIC_CALLS = {"eval", "exec", "compile", "__import__"}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_relative_path(value: str) -> PurePosixPath | None:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts:
        return None
    if any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path


def validate_allowlist(paths: list[str]) -> dict[str, Any]:
    forbidden = []
    for value in paths:
        path = _safe_relative_path(value)
        if path is None:
            forbidden.append(value)
            continue
        suffix = path.suffix.lower()
        if (
            any(part in FORBIDDEN_DIRECTORIES for part in path.parts)
            or suffix in FORBIDDEN_SUFFIXES
            or (
                suffix not in ALLOWED_SUFFIXES
                and path.name not in ALLOWED_NAMES
            )
        ):
            forbidden.append(value)
    return {"ok": not forbidden, "forbidden": forbidden}


def fetch_bounded(
    url: str,
    max_bytes: int,
    *,
    timeout_seconds: int = 30,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> bytes:
    command = [
        "curl",
        "--fail",
        "--silent",
        "--show-error",
        "--location",
        "--proto",
        "=https",
        "--max-time",
        str(timeout_seconds),
        "--max-filesize",
        str(max_bytes),
        "--user-agent",
        "agent-bridge-s5f-small-file-audit/1",
        url,
    ]
    try:
        completed = runner(
            command,
            shell=False,
            capture_output=True,
            timeout=timeout_seconds + 5,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise OSError("transport_timeout") from error
    if completed.returncode != 0:
        raise OSError(f"transport_failed:curl_{completed.returncode}")
    payload = completed.stdout
    if len(payload) > max_bytes:
        raise ValueError("file_size_limit_exceeded")
    return payload


def acquire_small_files(
    *,
    repository: str,
    revision: str,
    paths: list[str],
    output_dir: Path,
    fetch: Callable[[str, int], bytes] = fetch_bounded,
    max_file_bytes: int = 8 * 1024 * 1024,
    max_total_bytes: int = 32 * 1024 * 1024,
) -> dict[str, Any]:
    runtime_effects = {
        "downloaded_weights": False,
        "executed_community_code": False,
        "installed_dependencies": False,
        "started_containers": False,
        "used_gpu": False,
        "played_audio": False,
    }
    validation = validate_allowlist(paths)
    blockers = []
    if len(revision) != 40 or any(ch not in "0123456789abcdef" for ch in revision):
        blockers.append("revision_not_fixed")
    if not validation["ok"]:
        blockers.append("forbidden_path_requested")
    if output_dir.exists():
        blockers.append("output_dir_already_exists")
    if blockers:
        return {
            "schema": "agent_bridge.voice_small_file_audit_receipt.v1",
            "status": "blocked",
            "repository": repository,
            "revision": revision,
            "output_dir": str(output_dir),
            "files": [],
            "completed_files": 0,
            "blockers": blockers,
            "runtime_effects": runtime_effects,
        }

    temp_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent)
    )
    rows = []
    total = 0
    failure = None
    try:
        for value in paths:
            encoded_path = urllib.parse.quote(value, safe="/")
            url = (
                f"https://huggingface.co/{repository}/resolve/"
                f"{revision}/{encoded_path}"
            )
            try:
                payload = fetch(url, max_file_bytes)
            except ValueError as error:
                failure = str(error)
                break
            except (OSError, urllib.error.URLError, TimeoutError):
                failure = "transport_or_fetch_failed"
                break
            if len(payload) > max_file_bytes:
                failure = "file_size_limit_exceeded"
                break
            total += len(payload)
            if total > max_total_bytes:
                failure = "total_size_limit_exceeded"
                break
            destination = temp_dir / value
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            rows.append(
                {
                    "path": value,
                    "size": len(payload),
                    "sha256": sha256_bytes(payload),
                    "source_url": url,
                }
            )
        if failure is not None:
            shutil.rmtree(temp_dir)
            return {
                "schema": "agent_bridge.voice_small_file_audit_receipt.v1",
                "status": "blocked",
                "repository": repository,
                "revision": revision,
                "output_dir": str(output_dir),
                "files": rows,
                "completed_files": len(rows),
                "blockers": [failure],
                "runtime_effects": runtime_effects,
            }
        temp_dir.rename(output_dir)
    except BaseException:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise

    return {
        "schema": "agent_bridge.voice_small_file_audit_receipt.v1",
        "status": "small_files_acquired",
        "repository": repository,
        "revision": revision,
        "output_dir": str(output_dir),
        "files": rows,
        "completed_files": len(rows),
        "blockers": [],
        "runtime_effects": runtime_effects,
    }


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute) and isinstance(
        node.func.value, ast.Name
    ):
        return f"{node.func.value.id}.{node.func.attr}"
    return None


def audit_python_source(path: Path) -> dict[str, Any]:
    findings = set()
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except (OSError, SyntaxError) as error:
        return {
            "path": str(path),
            "parsed": False,
            "executed": False,
            "findings": [f"parse_failed:{type(error).__name__}"],
        }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name.split(".", 1)[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [(node.module or "").split(".", 1)[0]]
        else:
            modules = []
        for module in modules:
            if module in NETWORK_IMPORTS:
                findings.add(f"network_import:{module}")
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in DYNAMIC_CALLS:
                findings.add(f"dynamic_execution:{name}")
            if name and name.split(".", 1)[0] in PROCESS_MODULES:
                findings.add(f"process_execution:{name}")
            if name in {"os.system", "os.popen"}:
                findings.add(f"process_execution:{name}")
    return {
        "path": str(path),
        "parsed": True,
        "executed": False,
        "findings": sorted(findings),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Acquire fixed-revision small files without executing them"
    )
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    receipt = acquire_small_files(
        repository=args.repository,
        revision=args.revision,
        paths=DEFAULT_PATHS,
        output_dir=args.output_dir,
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["status"] == "small_files_acquired" else 2


if __name__ == "__main__":
    raise SystemExit(main())
