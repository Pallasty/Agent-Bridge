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
    return 70


if __name__ == "__main__":
    raise SystemExit(main())
