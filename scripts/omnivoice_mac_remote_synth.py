#!/usr/bin/env python3
"""Dispatch the default-off OmniVoice adapter to an explicitly configured Mac."""

import argparse
import fcntl
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

JOB_ID = re.compile(r"[0-9a-f]{32}")
SSH_DESTINATION = re.compile(r"(?:[A-Za-z0-9_.+%-]+@)?[A-Za-z0-9_.:%-]+")
REMOTE_OUTPUT = re.compile(r"/[A-Za-z0-9_./-]+")


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False))


def timeout_seconds():
    try:
        value = float(os.environ.get("AB_OMNIVOICE_MAC_REMOTE_TIMEOUT_SECS", "270"))
    except ValueError:
        value = 270.0
    return max(30.0, min(value, 840.0))


def job_root():
    return Path(os.environ.get(
        "AB_OMNIVOICE_MAC_REMOTE_JOB_DIR", "/tmp/agent-bridge-omnivoice"
    ))


def checked_job_dir(job_id):
    if not JOB_ID.fullmatch(job_id):
        raise ValueError("invalid remote job id")
    return job_root() / job_id


def worker(request):
    job_id = request.get("job_id", "")
    text = request.get("text")
    manifest = request.get("manifest")
    if not isinstance(text, str) or not text:
        raise ValueError("remote request text is empty")
    if not isinstance(manifest, str) or not manifest:
        raise ValueError("remote manifest is required")
    manifest_path = Path(manifest)
    if not manifest_path.is_file():
        raise ValueError(f"remote manifest not found: {manifest_path}")
    directory = checked_job_dir(job_id)
    directory.mkdir(parents=True, exist_ok=False)
    output = directory / "speech.wav"
    adapter = Path(__file__).with_name("omnivoice_tts_synth.py")
    command = [sys.executable, str(adapter), "--text", text, "--output", str(output),
               "--manifest", str(manifest_path)]
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    try:
        receipt = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        receipt = {"ok": False,
                   "detail": f"remote OmniVoice produced no JSON receipt: {(proc.stderr or '')[-400:]}"}
    if proc.returncode != 0 or not receipt.get("ok") or not output.is_file():
        raise RuntimeError(receipt.get("detail", f"remote OmniVoice rc={proc.returncode}"))
    receipt.update({"remote_output": str(output), "remote_job_id": job_id})
    return receipt


def cleanup(job_id):
    directory = checked_job_dir(job_id)
    if directory.is_dir():
        shutil.rmtree(directory)


def remote_command(python, adapter, *arguments):
    return " ".join(shlex.quote(part) for part in (python, adapter, *arguments))


def dispatch(args):
    host = os.environ.get("AB_OMNIVOICE_MAC_REMOTE_HOST", "").strip()
    remote_python = os.environ.get("AB_OMNIVOICE_MAC_REMOTE_PYTHON", "").strip()
    remote_adapter = os.environ.get("AB_OMNIVOICE_MAC_REMOTE_ADAPTER", "").strip()
    if not host or not remote_python or not remote_adapter:
        raise ValueError("set AB_OMNIVOICE_MAC_REMOTE_HOST, _PYTHON, and _ADAPTER")
    if host.startswith("-") or not SSH_DESTINATION.fullmatch(host):
        raise ValueError("AB_OMNIVOICE_MAC_REMOTE_HOST is not a safe SSH destination")
    if not args.manifest:
        raise ValueError("a remote OmniVoice manifest is required")
    timeout = timeout_seconds()
    job_id = uuid.uuid4().hex
    request = json.dumps({"job_id": job_id, "text": args.text,
                          "manifest": str(args.manifest)}, ensure_ascii=False)
    lock_path = Path(os.environ.get(
        "AB_OMNIVOICE_MAC_REMOTE_LOCK", "/tmp/agent-bridge-omnivoice-mac.lock"
    ))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("remote OmniVoice Mac is busy") from exc
        worker_cmd = remote_command(remote_python, remote_adapter, "--worker")
        try:
            ssh = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, worker_cmd],
                input=request, capture_output=True, text=True, timeout=timeout, check=False,
            )
            try:
                receipt = json.loads((ssh.stdout or "").strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError) as exc:
                detail = (ssh.stderr or "")[-400:]
                raise RuntimeError(f"remote worker produced no JSON receipt: {detail}") from exc
            if ssh.returncode != 0 or not receipt.get("ok"):
                raise RuntimeError(receipt.get("detail", f"remote worker rc={ssh.returncode}"))
            remote_output = receipt.get("remote_output", "")
            if not isinstance(remote_output, str):
                remote_output = ""
            remote_path = Path(remote_output)
            if (not REMOTE_OUTPUT.fullmatch(remote_output) or
                    ".." in remote_path.parts or
                    not remote_path.is_absolute() or remote_path.name != "speech.wav" or
                    remote_path.parent.name != job_id):
                raise RuntimeError("remote worker returned an unexpected output path")
            copied = subprocess.run(
                ["scp", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                 f"{host}:{remote_output}", str(args.output)],
                capture_output=True, text=True, timeout=timeout, check=False,
            )
            if copied.returncode != 0 or not args.output.is_file():
                raise RuntimeError(f"remote WAV copy failed: {(copied.stderr or '')[-400:]}")
        finally:
            cleanup_cmd = remote_command(remote_python, remote_adapter, "--cleanup", job_id)
            subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, cleanup_cmd],
                capture_output=True, text=True, timeout=30, check=False,
            )
    receipt.pop("remote_output", None)
    receipt.update({"execution_host": host, "execution_transport": "ssh",
                    "remote_cleanup_attempted": True})
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--cleanup")
    args = parser.parse_args()
    try:
        if args.cleanup:
            cleanup(args.cleanup)
            return 0
        if args.worker:
            emit({**worker(json.load(sys.stdin)), "ok": True})
            return 0
        if not args.text or args.output is None:
            parser.error("--text and --output are required for dispatch")
        emit({**dispatch(args), "ok": True})
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        if args.output and args.output.exists():
            args.output.unlink()
        emit({"ok": False, "backend": "omnivoice", "detail": str(exc)[:600]})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
