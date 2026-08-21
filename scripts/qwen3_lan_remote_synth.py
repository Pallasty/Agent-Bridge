#!/usr/bin/env python3
"""Default-off Qwen3-TTS LAN dispatcher using an existing remote Unix worker."""

import argparse
import base64
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
import uuid
from pathlib import Path

SSH_DESTINATION = re.compile(r"(?:[A-Za-z0-9_.+%-]+@)?[A-Za-z0-9_.:%-]+")
REMOTE_OUTPUT = re.compile(r"/tmp/ab-qwen3-lan-[0-9a-f]{32}\.wav")

REMOTE_SCRIPT = r'''
import json, socket, sys
request = json.load(sys.stdin)
socket_path = request.pop("_socket")
timeout = float(request.pop("_timeout"))
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.settimeout(timeout)
try:
    client.connect(socket_path)
    client.sendall((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
    raw = bytearray()
    while len(raw) < 65536:
        chunk = client.recv(4096)
        if not chunk:
            break
        raw.extend(chunk)
        if b"\n" in chunk:
            break
    if not raw:
        raise RuntimeError("Qwen3 worker returned no receipt")
    print(raw.split(b"\n", 1)[0].decode("utf-8"), flush=True)
finally:
    client.close()
'''


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False))


def timeout_seconds():
    try:
        value = float(os.environ.get("AB_QWEN3_LAN_TIMEOUT_SECS", "180"))
    except ValueError:
        value = 180.0
    return max(30.0, min(value, 600.0))


def remote_script_arg():
    return base64.b64encode(REMOTE_SCRIPT.encode("utf-8")).decode("ascii")


def remote_command(remote_python):
    encoded = remote_script_arg()
    # Keep the payload in one shell-quoted argument.  OpenSSH reconstructs the
    # remote command from argv, so passing ``-c`` and code as separate argv
    # entries would let the remote shell split the Python program at semicolons.
    code = f'import base64;exec(base64.b64decode("{encoded}"))'
    return f'{shlex.quote(remote_python)} -c {shlex.quote(code)}'


def ssh_options():
    options = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
               "-o", "StrictHostKeyChecking=yes"]
    alias = os.environ.get("AB_QWEN3_LAN_HOST_KEY_ALIAS", "").strip()
    if alias:
        options.extend(["-o", f"HostKeyAlias={alias}"])
    port = os.environ.get("AB_QWEN3_LAN_SSH_PORT", "22").strip()
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError("AB_QWEN3_LAN_SSH_PORT must be 1..65535")
    if port != "22":
        options.extend(["-p", port])
    return options


def parse_receipt(stdout, stderr):
    try:
        return json.loads((stdout or "").strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"remote worker produced no JSON receipt: {(stderr or '')[-400:]}") from exc


def dispatch(args):
    host = os.environ.get("AB_QWEN3_LAN_REMOTE_HOST", "").strip()
    remote_python = os.environ.get("AB_QWEN3_LAN_REMOTE_PYTHON", "").strip()
    worker_socket = os.environ.get("AB_QWEN3_LAN_WORKER_SOCKET", "").strip()
    if not host or not remote_python or not worker_socket:
        raise ValueError("set AB_QWEN3_LAN_REMOTE_HOST, _PYTHON, and _WORKER_SOCKET")
    if host.startswith("-") or not SSH_DESTINATION.fullmatch(host):
        raise ValueError("AB_QWEN3_LAN_REMOTE_HOST is not a safe SSH destination")
    if not remote_python.startswith("/") or not worker_socket.startswith("/"):
        raise ValueError("remote Python and worker socket must be absolute paths")
    timeout = timeout_seconds()
    remote_output = f"/tmp/ab-qwen3-lan-{uuid.uuid4().hex}.wav"
    request = {"op": "synthesize", "text": args.text, "output": remote_output,
               "speaker": args.speaker, "instruct": args.instruct or "",
               "_socket": worker_socket, "_timeout": timeout}
    lock_path = Path(os.environ.get("AB_QWEN3_LAN_LOCK", "/tmp/agent-bridge-qwen3-lan.lock"))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("remote Qwen3 Mac is busy") from exc
        ssh_args = ["ssh", *ssh_options(), host, remote_command(remote_python)]
        try:
            ssh = subprocess.run(ssh_args, input=json.dumps(request, ensure_ascii=False),
                                 capture_output=True, text=True, timeout=timeout, check=False)
            receipt = parse_receipt(ssh.stdout, ssh.stderr)
            if ssh.returncode != 0 or not receipt.get("ok"):
                raise RuntimeError(receipt.get("detail", f"remote worker rc={ssh.returncode}"))
            returned = receipt.get("output") or receipt.get("remote_output") or remote_output
            if returned != remote_output or not REMOTE_OUTPUT.fullmatch(returned):
                raise RuntimeError("remote worker returned an unexpected output path")
            copied = subprocess.run(
                ["scp", "-q", *ssh_options(), f"{host}:{remote_output}", str(args.output)],
                capture_output=True, text=True, timeout=timeout, check=False)
            if copied.returncode != 0 or not args.output.is_file():
                raise RuntimeError(f"remote WAV copy failed: {(copied.stderr or '')[-400:]}")
        finally:
            cleanup = {"path": remote_output}
            cleanup_script = "import json,os,sys; p=json.load(sys.stdin)['path']; os.unlink(p) if os.path.isfile(p) else None"
            cleanup_code = "import base64;exec(base64.b64decode(%r))" % base64.b64encode(cleanup_script.encode()).decode()
            subprocess.run(["ssh", *ssh_options(), host, remote_python, "-c", cleanup_code],
                           input=json.dumps(cleanup), capture_output=True, text=True,
                           timeout=30, check=False)
    receipt.pop("output", None)
    receipt.pop("remote_output", None)
    receipt.update({"backend": "qwen3-lan", "execution_host": host,
                    "execution_transport": "ssh", "remote_cleanup_attempted": True})
    return receipt


def health(args):
    host = os.environ.get("AB_QWEN3_LAN_REMOTE_HOST", "").strip()
    remote_python = os.environ.get("AB_QWEN3_LAN_REMOTE_PYTHON", "").strip()
    worker_socket = os.environ.get("AB_QWEN3_LAN_WORKER_SOCKET", "").strip()
    if not host or not remote_python or not worker_socket:
        raise ValueError("set AB_QWEN3_LAN_REMOTE_HOST, _PYTHON, and _WORKER_SOCKET")
    if host.startswith("-") or not SSH_DESTINATION.fullmatch(host):
        raise ValueError("AB_QWEN3_LAN_REMOTE_HOST is not a safe SSH destination")
    request = {"op": "health", "_socket": worker_socket, "_timeout": timeout_seconds()}
    proc = subprocess.run(["ssh", *ssh_options(), host, remote_command(remote_python)],
                          input=json.dumps(request), capture_output=True, text=True,
                          timeout=timeout_seconds(), check=False)
    receipt = parse_receipt(proc.stdout, proc.stderr)
    if proc.returncode != 0 or not receipt.get("ok"):
        raise RuntimeError(receipt.get("detail", f"remote health rc={proc.returncode}"))
    receipt.update({"backend": "qwen3-lan", "execution_host": host,
                    "execution_transport": "ssh"})
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--speaker", default="serena")
    parser.add_argument("--instruct")
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args()
    try:
        if args.health:
            emit({**health(args), "ok": True})
            return 0
        if not args.text or args.output is None:
            parser.error("--text and --output are required")
        emit({**dispatch(args), "ok": True})
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        if args.output and args.output.exists():
            args.output.unlink()
        emit({"ok": False, "backend": "qwen3-lan", "detail": str(exc)[:600]})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
