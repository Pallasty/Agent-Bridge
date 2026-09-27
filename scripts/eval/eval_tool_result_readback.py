#!/usr/bin/env python3
"""Compare fixed text exposure policies; no models, MCP or production writes.

Queries are supplied exact anchors. This measures byte accessibility, not agent
reasoning. Capture uses temporary files; inputs come from a pinned Git object.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from typing import Any


_SPEC = importlib.util.spec_from_file_location(
    "tool_result_readback", Path(__file__).with_name("tool_result_readback.py")
)
assert _SPEC is not None and _SPEC.loader is not None
readback = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(readback)
MAX_BYTES = 8 * 1024 * 1024


def wire_bytes(operation: str, digest: str, response: dict[str, Any]) -> int:
    """Count the complete CLI-compatible JSON response, including newline."""
    envelope = {"source_sha256": digest, "operation": operation, **response}
    return len((json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n").encode())


def evaluate_case(data: bytes, anchors: list[str]) -> dict[str, Any]:
    """Measure one explicitly selected file with two unique literal anchors."""
    text = data.decode("utf-8")
    if len(anchors) != 2 or len(set(anchors)) != 2 or any(not anchor or text.count(anchor) != 1 for anchor in anchors):
        raise ValueError("exactly two unique, present anchors are required")
    digest = hashlib.sha256(data).hexdigest()
    inline = {"text": text, "total_bytes": len(data), "truncated": False}
    head_tail_text = text if len(data) <= 8192 else (
        data[:4096].decode("utf-8", errors="ignore")
        + "\n[omitted middle]\n"
        + data[-4096:].decode("utf-8", errors="ignore")
    )
    head_tail = {"text": head_tail_text, "total_bytes": len(data), "truncated": len(data) > 8192}
    first = readback.preview(data, budget=1024)
    responses = [("preview", first)]
    recovered = 0
    for anchor in anchors:
        found = readback.search(data, anchor, budget=4096)
        responses.append(("search", found))
        if not found["matches"]:
            continue
        start = max(0, found["matches"][0]["start"] - 96)
        while start and data[start] & 0xC0 == 0x80:
            start -= 1
        page = readback.read_page(data, start=start, budget=512)
        responses.append(("read", page))
        recovered += int(anchor in page["text"])

    rebuilt = bytearray()
    roundtrip_calls = 0
    roundtrip_wire = 0
    start = 0
    while True:
        page = readback.read_page(data, start=start, budget=4096)
        rebuilt.extend(page["text"].encode("utf-8"))
        roundtrip_calls += 1
        roundtrip_wire += wire_bytes("read", digest, page)
        next_start = page["next_start"]
        if next_start is None:
            break
        if next_start <= start:
            raise ValueError("pagination did not advance")
        start = next_start

    candidate_wire = sum(wire_bytes(operation, digest, response) for operation, response in responses)
    candidate_content = sum(
        len(response["text"].encode("utf-8")) if "text" in response else
        sum(len(match["text"].encode("utf-8")) for match in response["matches"])
        for _, response in responses
    )
    inline_wire = wire_bytes("inline", digest, inline)
    return {
        "sha256": digest,
        "input_bytes": len(data),
        "inline": {"anchors_visible": 2, "response_count": 1, "wire_bytes": inline_wire},
        "head_tail": {
            "anchors_visible": sum(anchor in head_tail_text for anchor in anchors),
            "response_count": 1,
            "wire_bytes": wire_bytes("head_tail", digest, head_tail),
        },
        "selective": {
            "preview_anchors_visible": sum(anchor in first["text"] for anchor in anchors),
            "anchors_recovered": recovered,
            "response_count": len(responses),
            "content_bytes": candidate_content,
            "wire_bytes": candidate_wire,
        },
        "roundtrip": {
            "sha256_matches": hashlib.sha256(rebuilt).hexdigest() == digest and rebuilt == data,
            "response_count": roundtrip_calls,
            "wire_bytes": roundtrip_wire,
        },
        "response_byte_reduction_vs_inline": round(1 - candidate_wire / inline_wire, 6),
        "task_value_proven": False,
    }


def git_blob(repo: Path, revision: str, path: str) -> bytes:
    """Read a size-bounded pinned Git blob without replacing objects or fetching."""
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("a fixed 40-hex source revision is required")
    if not path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
        raise ValueError("a repository-relative path is required")
    command = ["git", "--no-replace-objects", "--literal-pathspecs", "-C", str(repo)]
    obj = f"{revision}:{path}"
    size = int(subprocess.check_output([*command, "cat-file", "-s", obj]))
    if size > MAX_BYTES:
        raise ValueError("source exceeds the 8 MiB input limit")
    data = subprocess.check_output([*command, "cat-file", "blob", obj])
    if len(data) != size:
        raise ValueError("Git blob size mismatch")
    return data


def main() -> int:
    """Run the fixed comparison and print JSON; return nonzero on a failed check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--manifest", type=Path, default=Path(__file__).parent / "fixtures/agno_readback_cases.json")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        cases = []
        with tempfile.TemporaryDirectory(prefix="ab-agno-readback-") as directory:
            for index, case in enumerate(manifest["cases"]):
                data = git_blob(args.repo, manifest["source_revision"], case["path"])
                if len(data) != case["size_bytes"]:
                    raise ValueError(f"input size changed: {case['path']}")
                artifact = Path(directory) / f"{index}.txt"
                artifact.write_bytes(data)
                checked = readback.load_artifact(artifact, case["sha256"])
                result = evaluate_case(checked, case["anchors"])
                cases.append({"path": case["path"], "kind": case["kind"], **result})
        passed = bool(cases) and all(
            case["roundtrip"]["sha256_matches"] and case["selective"]["anchors_recovered"] == 2
            for case in cases
        )
        report = {
            "source_revision": manifest["source_revision"],
            "selection": manifest["selection"],
            "mechanics_passed": passed,
            "cases": cases,
            "model_calls": 0,
            "tokens_measured": False,
            "end_to_end_task_latency_measured": False,
            "task_value_proven": False,
            "runtime_promotion_authorized": False,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if passed else 1
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"error": str(exc), "mechanics_passed": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
