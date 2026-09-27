#!/usr/bin/env python3
"""Read an existing local artifact; this is not a capture service or an ACL.

Offsets and body budgets count UTF-8 bytes, not characters or tokens. JSON
metadata and escaping are additional wire bytes. Search matches do not overlap.
Each CLI call validates the complete artifact against a caller-pinned SHA256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, NoReturn


MAX_ARTIFACT_BYTES = 8 * 1024 * 1024


def load_artifact(path: Path, expected_sha256: str) -> bytes:
    """Read a regular, nonsymlink UTF-8 file matching the supplied digest.

    Raises:
        ValueError: Digest, file type, size, content hash or encoding is invalid.
        OSError: The file is missing or cannot be read.
    """
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("expected SHA256 must contain exactly 64 hex characters")
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("artifact must be a regular file, not a symlink or special file")
    # NOFOLLOW closes the final-component symlink race; NONBLOCK avoids hanging
    # if the path is replaced by a FIFO between lstat and open.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("artifact must be a regular file")
        if info.st_size > MAX_ARTIFACT_BYTES:
            raise ValueError("artifact exceeds 8 MiB limit")
        data = stream.read(MAX_ARTIFACT_BYTES + 1)
    if len(data) > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact exceeds 8 MiB limit")
    if hashlib.sha256(data).hexdigest() != expected_sha256.lower():
        raise ValueError("artifact SHA256 mismatch")
    data.decode("utf-8", errors="strict")
    return data


def _validate(data: bytes, start: int, budget: int) -> None:
    if not isinstance(data, bytes):
        raise ValueError("artifact data must be bytes")
    if len(data) > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact exceeds 8 MiB limit")
    data.decode("utf-8", errors="strict")
    if type(budget) is not int or not 4 <= budget <= 16000:
        raise ValueError("body budget must be an integer from 4 through 16000 bytes")
    if type(start) is not int or not 0 <= start <= len(data):
        raise ValueError("start must be an integer between zero and total_bytes")
    if start < len(data) and data[start] & 0xC0 == 0x80:
        raise ValueError("start must be a UTF-8 byte boundary")


def read_page(data: bytes, start: int = 0, budget: int = 4096) -> dict[str, Any]:
    """Return one bounded page; next_start resumes without dropping bytes.

    Raises:
        ValueError: Data, offset or budget violates the UTF-8 byte contract.
    """
    _validate(data, start, budget)
    end = min(start + budget, len(data))
    while end < len(data) and data[end] & 0xC0 == 0x80:
        end -= 1
    truncated = end < len(data)
    return {
        "text": data[start:end].decode("utf-8"),
        "start": start,
        "next_start": end if truncated else None,
        "total_bytes": len(data),
        "truncated": truncated,
    }


def preview(data: bytes, budget: int = 1024) -> dict[str, Any]:
    """Return the first page with the same byte-budget contract as read_page."""
    return read_page(data, 0, budget)


def search(
    data: bytes,
    query: str,
    start: int = 0,
    budget: int = 4096,
    max_matches: int = 5,
) -> dict[str, Any]:
    """Find literal, nonoverlapping matches, with a resumable byte cursor.

    A count or budget limit may return search_complete=False even when no
    later match exists. Resume at next_start to finish scanning.

    Raises:
        ValueError: Data, offset, query, budget or match limit is invalid.
    """
    _validate(data, start, budget)
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    needle = query.encode("utf-8", errors="strict")
    if not 1 <= len(needle) <= 256:
        raise ValueError("query must contain 1 through 256 UTF-8 bytes")
    if len(needle) > budget:
        raise ValueError("body budget must fit at least one complete query match")
    if type(max_matches) is not int or not 1 <= max_matches <= 100:
        raise ValueError("max_matches must be an integer from 1 through 100")
    matches: list[dict[str, Any]] = []
    cursor = start
    remaining = budget
    while cursor < len(data) and len(matches) < max_matches and remaining >= len(needle):
        found = data.find(needle, cursor)
        if found < 0:
            cursor = len(data)
            break
        cursor = found + len(needle)
        matches.append({"start": found, "end": cursor, "text": query})
        remaining -= len(needle)
    complete = cursor == len(data)
    return {
        "matches": matches,
        "next_start": None if complete else cursor,
        "search_complete": complete,
    }


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def main(argv: list[str] | None = None) -> int:
    """Read one file and print compact JSON; invalid requests exit with code 2."""
    parser = _JsonArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("preview", "read", "search"):
        command = commands.add_parser(name)
        command.add_argument("--budget", type=int, default=1024 if name == "preview" else 4096)
        if name != "preview":
            command.add_argument("--start", type=int, default=0)
        if name == "search":
            command.add_argument("--query", required=True)
            command.add_argument("--max-matches", type=int, default=5)
    try:
        args = parser.parse_args(argv)
        data = load_artifact(args.file, args.sha256)
        if args.operation == "preview":
            result = preview(data, args.budget)
        elif args.operation == "read":
            result = read_page(data, args.start, args.budget)
        else:
            result = search(data, args.query, args.start, args.budget, args.max_matches)
        response = {"source_sha256": args.sha256.lower(), "operation": args.operation, **result}
    except (ValueError, OSError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, separators=(",", ":")))
        return 2
    print(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
