#!/usr/bin/env python3
"""Repository-owned synthetic Worker modes for S623 Supervisor tests only."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def publish(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def main() -> int:
    mode = sys.argv[1]
    _request = sys.stdin.buffer.read()
    if mode == "success":
        sys.stdout.buffer.write(b'{"status":"synthetic-success"}')
        sys.stderr.buffer.write(b"synthetic diagnostic\n")
        return 0
    if mode == "mark_success":
        publish(sys.argv[2], "spawned")
        sys.stdout.buffer.write(b'{"status":"synthetic-success"}')
        return 0
    if mode == "no_response":
        return 0
    if mode == "malformed_output":
        sys.stdout.buffer.write(b"{")
        return 0
    if mode == "stdout_overflow":
        sys.stdout.buffer.write(b"x" * 65_537)
        sys.stdout.buffer.flush()
        time.sleep(300)
    if mode == "stderr_overflow":
        sys.stderr.buffer.write(b"x" * 16_385)
        sys.stderr.buffer.flush()
        time.sleep(300)
    if mode == "hang":
        publish(sys.argv[2], str(os.getpid()))
        time.sleep(300)
    if mode == "term_ignoring_descendant":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(300)",
            ],
            close_fds=True,
        )
        publish(sys.argv[2], f"{os.getpid()} {child.pid}")
        time.sleep(300)
    if mode == "exit_with_descendant":
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(300)",
            ],
            close_fds=True,
        )
        publish(sys.argv[2], f"{os.getpid()} {child.pid}")
        sys.stdout.buffer.write(b'{"status":"must-not-be-accepted"}')
        return 0
    if mode == "kill_guardian":
        os.kill(os.getppid(), signal.SIGKILL)
        time.sleep(300)
    if mode == "fd_audit":
        leaked = []
        for fd in range(190, 198):
            try:
                os.fstat(fd)
            except OSError:
                continue
            leaked.append(fd)
        if leaked:
            sys.stderr.write(f"custody descriptors leaked: {leaked}\n")
            return 71
        sys.stdout.buffer.write(b'{"status":"synthetic-success"}')
        return 0
    return 70


if __name__ == "__main__":
    raise SystemExit(main())
