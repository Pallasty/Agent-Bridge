from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_voice_small_file_audit.py"
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_small_file_audit_receipt.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_small_file_audit", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_forbidden_model_and_audio_paths_are_rejected() -> None:
    audit = load_module()

    result = audit.validate_allowlist(
        [
            "README.md",
            "qwen3-tts_onnx/model.onnx",
            "audio_ref/speaker.wav",
            "logs/run.txt",
        ]
    )

    assert result["ok"] is False
    assert result["forbidden"] == [
        "qwen3-tts_onnx/model.onnx",
        "audio_ref/speaker.wav",
        "logs/run.txt",
    ]


def test_failed_fetch_leaves_no_partial_evidence_tree(tmp_path: Path) -> None:
    audit = load_module()
    output = tmp_path / "evidence"
    calls = 0

    def fetch(_url: str, _max_bytes: int) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            return b"first"
        raise OSError("transport reset")

    receipt = audit.acquire_small_files(
        repository="owner/repo",
        revision="1" * 40,
        paths=["README.md", "requirements.txt"],
        output_dir=output,
        fetch=fetch,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["transport_or_fetch_failed"]
    assert receipt["completed_files"] == 1
    assert not output.exists()


def test_successful_fetch_is_hash_bound_and_atomic(tmp_path: Path) -> None:
    audit = load_module()
    output = tmp_path / "evidence"
    payloads = {
        "README.md": b"license: Apache-2.0\n",
        "src/inference.py": b"import numpy as np\n",
    }

    def fetch(url: str, _max_bytes: int) -> bytes:
        name = next(path for path in payloads if url.endswith("/" + path))
        return payloads[name]

    receipt = audit.acquire_small_files(
        repository="owner/repo",
        revision="2" * 40,
        paths=list(payloads),
        output_dir=output,
        fetch=fetch,
    )

    assert receipt["status"] == "small_files_acquired"
    assert receipt["runtime_effects"]["executed_community_code"] is False
    assert [row["path"] for row in receipt["files"]] == list(payloads)
    assert receipt["files"][0]["sha256"] == hashlib.sha256(
        payloads["README.md"]
    ).hexdigest()
    assert (output / "README.md").read_bytes() == payloads["README.md"]


def test_size_limit_blocks_oversized_response(tmp_path: Path) -> None:
    audit = load_module()

    receipt = audit.acquire_small_files(
        repository="owner/repo",
        revision="3" * 40,
        paths=["README.md"],
        output_dir=tmp_path / "evidence",
        max_file_bytes=8,
        fetch=lambda _url, _limit: b"x" * 9,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["file_size_limit_exceeded"]
    assert not (tmp_path / "evidence").exists()


def test_transport_timeout_is_converted_to_bounded_fetch_failure() -> None:
    audit = load_module()

    def runner(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["curl"], timeout=1)

    with pytest.raises(OSError, match="transport_timeout"):
        audit.fetch_bounded(
            "https://example.invalid/file",
            1024,
            timeout_seconds=1,
            runner=runner,
        )


def test_static_python_audit_flags_execution_and_network_primitives(
    tmp_path: Path,
) -> None:
    audit = load_module()
    source = tmp_path / "candidate.py"
    source.write_text(
        """
import requests
import subprocess

eval("1 + 1")
subprocess.run(["echo", "unsafe"])
requests.get("https://example.invalid")
""".strip()
    )

    result = audit.audit_python_source(source)

    assert result["parsed"] is True
    assert result["executed"] is False
    assert result["findings"] == [
        "dynamic_execution:eval",
        "network_import:requests",
        "process_execution:subprocess.run",
    ]


def test_static_python_audit_accepts_data_only_imports(tmp_path: Path) -> None:
    audit = load_module()
    source = tmp_path / "candidate.py"
    source.write_text("import json\nimport numpy as np\n")

    result = audit.audit_python_source(source)

    assert result["parsed"] is True
    assert result["findings"] == []


def test_blocked_receipt_validates_against_schema(tmp_path: Path) -> None:
    jsonschema = __import__("jsonschema")
    audit = load_module()
    receipt = audit.acquire_small_files(
        repository="owner/repo",
        revision="4" * 40,
        paths=["README.md"],
        output_dir=tmp_path / "evidence",
        fetch=lambda _url, _limit: (_ for _ in ()).throw(
            OSError("transport reset")
        ),
    )

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(receipt, schema)
