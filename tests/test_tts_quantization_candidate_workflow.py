from __future__ import annotations

import json
import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/eval/tts_quantization_candidate_workflow.py"
POLICY = ROOT / "scripts/eval/fixtures/tts_quantization_gate_policy_v1.json"
FROZEN = ROOT / "tests/fixtures/tts_quantization"
REAL_QWEN_PACK = (
    ROOT / "docs/reports/qwen3-tts-quantization/2026-08-20-codec-scope3-audit-pack-v1"
)


def invoke(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_qwen_workflow_writes_private_rejected_audit_pack(tmp_path: Path) -> None:
    output = tmp_path / "qwen-pack"
    result = invoke(
        "qwen-codec-scope3",
        "--waveform", str(FROZEN / "qwen_waveform.json"),
        "--listening", str(FROZEN / "qwen_listening.json"),
        "--runtime", str(FROZEN / "qwen_runtime_rejected.json"),
        "--corpus", str(FROZEN / "qwen_corpus.json"),
        "--policy", str(POLICY),
        "--output-dir", str(output),
    )
    assert result.returncode == 2, result.stderr
    summary = json.loads(result.stdout)
    receipt = json.loads((output / "candidate.receipt.json").read_text())
    assert summary["decision"] == receipt["decision"] == "reject"
    assert "resource_limit:runtime_memory_increased" in receipt["rejection_reasons"]
    assert all(value is False for value in summary["authorization"].values())
    assert summary["self_contained"] is True
    assert stat.S_IMODE(os.stat(output).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(output / "candidate.manifest.json").st_mode) == 0o600
    assert stat.S_IMODE(os.stat(output / "candidate.receipt.json").st_mode) == 0o600
    manifest = json.loads((output / "candidate.manifest.json").read_text())
    assert manifest["corpus"]["path"] == "inputs/corpus.json"
    assert all(item["path"].startswith("inputs/") for item in manifest["evidence"])
    for item in manifest["evidence"]:
        copied = output / item["path"]
        assert hashlib.sha256(copied.read_bytes()).hexdigest() == item["sha256"]
        assert stat.S_IMODE(os.stat(copied).st_mode) == 0o600
    assert (output / "gate.policy.json").read_bytes() == POLICY.read_bytes()


def test_omnivoice_workflow_keeps_missing_runtime_visible(tmp_path: Path) -> None:
    output = tmp_path / "omni-pack"
    result = invoke(
        "omnivoice-static-int8",
        "--summary", str(FROZEN / "omnivoice_static_rejected.json"),
        "--trajectory", str(FROZEN / "omnivoice_trajectory_rejected.json"),
        "--policy", str(POLICY),
        "--output-dir", str(output),
    )
    assert result.returncode == 2, result.stderr
    receipt = json.loads((output / "candidate.receipt.json").read_text())
    assert "evidence_failed:autoregressive_trajectory" in receipt["rejection_reasons"]
    assert "evidence_missing:runtime_benchmark" in receipt["missing_evidence"]


def test_workflow_refuses_to_reuse_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "owner-data"
    marker.write_text("preserve\n")
    result = invoke(
        "omnivoice-static-int8",
        "--summary", str(FROZEN / "omnivoice_static_rejected.json"),
        "--policy", str(POLICY),
        "--output-dir", str(output),
    )
    assert result.returncode != 0
    assert "output_directory_exists" in result.stderr
    assert marker.read_text() == "preserve\n"


def test_invalid_policy_is_rejected_before_output_creation(tmp_path: Path) -> None:
    changed = json.loads(POLICY.read_text())
    changed["authorization"]["allows_deployment"] = True
    policy = tmp_path / "unsafe-policy.json"
    policy.write_text(json.dumps(changed) + "\n")
    output = tmp_path / "must-not-exist"
    result = invoke(
        "omnivoice-static-int8",
        "--summary", str(FROZEN / "omnivoice_static_rejected.json"),
        "--policy", str(policy),
        "--output-dir", str(output),
    )
    assert result.returncode != 0
    assert "contains_operational_authority" in result.stderr
    assert not output.exists()


def test_real_qwen_audit_pack_is_self_contained_and_reproducible(tmp_path: Path) -> None:
    manifest = REAL_QWEN_PACK / "candidate.manifest.json"
    policy = REAL_QWEN_PACK / "gate.policy.json"
    frozen_receipt = json.loads((REAL_QWEN_PACK / "candidate.receipt.json").read_text())
    output = tmp_path / "reproduced-receipt.json"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/eval/tts_quantization_gate.py"),
         "--manifest", str(manifest), "--policy", str(policy), "--output", str(output)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2, result.stderr
    reproduced = json.loads(output.read_text())
    assert reproduced == frozen_receipt
    normalized = json.loads(manifest.read_text())
    assert all(not Path(item["path"]).is_absolute() for item in normalized["evidence"])
    assert not Path(normalized["corpus"]["path"]).is_absolute()
