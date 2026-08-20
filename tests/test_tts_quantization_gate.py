from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/eval/tts_quantization_gate.py"
POLICY = ROOT / "scripts/eval/fixtures/tts_quantization_gate_policy_v1.json"
SPEC = importlib.util.spec_from_file_location("tts_quantization_gate", SCRIPT)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


CASES = ["zh-short", "zh-long", "mixed", "english"]


def write_json(path: Path, value: dict) -> str:
    raw = (json.dumps(value, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def evidence(tmp_path: Path, kind: str, status: str = "PASS", cases: list[str] | None = None,
             metrics: dict | None = None) -> dict:
    path = tmp_path / f"{kind}.json"
    digest = write_json(path, {"producer_schema": f"example.{kind}.v1", "status": status})
    return {
        "kind": kind,
        "path": path.name,
        "sha256": digest,
        "status": status,
        "case_ids": CASES if cases is None else cases,
        "metrics": metrics or {},
    }


def manifest(tmp_path: Path, *, boundaries: list[str] | None = None,
             omit: set[str] | None = None, failed: set[str] | None = None,
             runtime_metrics: dict | None = None) -> Path:
    boundaries = boundaries or ["autoregressive", "codec", "feedforward"]
    omit = omit or set()
    failed = failed or set()
    required = {
        "static_shadow",
        "autoregressive_trajectory",
        "waveform_numeric",
        "tensor_numeric",
        "blind_listening",
        "runtime_benchmark",
    }
    rows = []
    for kind in sorted(required - omit):
        metrics = None
        if kind == "runtime_benchmark":
            metrics = runtime_metrics or {
                "max_latency_ratio": 1.01,
                "runtime_memory_delta_bytes": -4096,
            }
        rows.append(evidence(tmp_path, kind, "FAIL" if kind in failed else "PASS", metrics=metrics))
    corpus_path = tmp_path / "corpus.json"
    corpus_sha256 = write_json(corpus_path, {"schema": "example.corpus.v1", "case_ids": CASES})
    value = {
        "schema": gate.MANIFEST_SCHEMA,
        "candidate": {
            "id": "candidate-q8",
            "model": "example-tts",
            "quantization": "int8",
            "artifact": {"baseline_bytes": 1000, "candidate_bytes": 700},
        },
        "corpus": {
            "id": "frozen-four",
            "path": corpus_path.name,
            "sha256": corpus_sha256,
            "case_ids": CASES,
        },
        "components": [
            {"name": f"component-{index}", "boundary": boundary}
            for index, boundary in enumerate(boundaries)
        ],
        "evidence": rows,
    }
    path = tmp_path / "manifest.json"
    write_json(path, value)
    return path


def test_all_boundaries_pass_and_entropy_remains_shadow(tmp_path: Path) -> None:
    receipt = gate.build_receipt(manifest(tmp_path), POLICY)
    assert receipt["decision"] == "pass"
    assert receipt["missing_evidence"] == []
    assert receipt["rejection_reasons"] == []
    assert receipt["shadow_evidence_observed"] is True
    assert receipt["required_evidence_kinds"] == [
        "autoregressive_trajectory",
        "blind_listening",
        "runtime_benchmark",
        "tensor_numeric",
        "waveform_numeric",
    ]
    assert all(value is False for value in receipt["authorization"].values())


def test_missing_boundary_evidence_is_insufficient_not_pass(tmp_path: Path) -> None:
    receipt = gate.build_receipt(manifest(tmp_path, omit={"waveform_numeric"}), POLICY)
    assert receipt["decision"] == "insufficient_evidence"
    assert receipt["missing_evidence"] == ["evidence_missing:waveform_numeric"]


@pytest.mark.parametrize(
    ("failed", "runtime_metrics", "reason"),
    [
        ({"autoregressive_trajectory"}, None, "evidence_failed:autoregressive_trajectory"),
        (set(), {"max_latency_ratio": 1.051, "runtime_memory_delta_bytes": -1},
         "resource_limit:max_latency_ratio"),
        (set(), {"max_latency_ratio": 1.0, "runtime_memory_delta_bytes": 1},
         "resource_limit:runtime_memory_increased"),
    ],
)
def test_failed_evidence_or_resource_regression_rejects(
    tmp_path: Path, failed: set[str], runtime_metrics: dict | None, reason: str
) -> None:
    receipt = gate.build_receipt(
        manifest(tmp_path, failed=failed, runtime_metrics=runtime_metrics), POLICY
    )
    assert receipt["decision"] == "reject"
    assert reason in receipt["rejection_reasons"]


def test_shadow_entropy_cannot_satisfy_autoregressive_gate(tmp_path: Path) -> None:
    receipt = gate.build_receipt(
        manifest(tmp_path, boundaries=["autoregressive"], omit={"autoregressive_trajectory"}),
        POLICY,
    )
    assert receipt["shadow_evidence_observed"] is True
    assert receipt["decision"] == "insufficient_evidence"


def test_evidence_hash_drift_fails_closed(tmp_path: Path) -> None:
    path = manifest(tmp_path)
    value = json.loads(path.read_text())
    evidence_path = tmp_path / value["evidence"][0]["path"]
    evidence_path.write_text("{}\n")
    with pytest.raises(gate.ContractError, match="sha256_mismatch"):
        gate.build_receipt(path, POLICY)


def test_corpus_hash_drift_fails_closed(tmp_path: Path) -> None:
    path = manifest(tmp_path)
    value = json.loads(path.read_text())
    (tmp_path / value["corpus"]["path"]).write_text("{}\n")
    with pytest.raises(gate.ContractError, match="manifest.corpus:sha256_mismatch"):
        gate.build_receipt(path, POLICY)


def test_policy_cannot_grant_operational_authority(tmp_path: Path) -> None:
    changed = json.loads(POLICY.read_text())
    changed["authorization"]["allows_deployment"] = True
    policy = tmp_path / "policy.json"
    write_json(policy, changed)
    with pytest.raises(gate.ContractError, match="operational_authority"):
        gate.build_receipt(manifest(tmp_path), policy)


def test_manifest_is_closed_world(tmp_path: Path) -> None:
    path = manifest(tmp_path)
    value = json.loads(path.read_text())
    value["allows_weight_writing"] = True
    write_json(path, value)
    with pytest.raises(gate.ContractError, match="manifest:keys"):
        gate.build_receipt(path, POLICY)


def test_cli_writes_exclusive_private_receipt_and_refuses_overwrite(tmp_path: Path) -> None:
    candidate = manifest(tmp_path)
    output = tmp_path / "receipt.json"
    command = [
        sys.executable,
        str(SCRIPT),
        "--manifest",
        str(candidate),
        "--policy",
        str(POLICY),
        "--output",
        str(output),
    ]
    first = subprocess.run(command, text=True, capture_output=True, check=False)
    assert first.returncode == 0, first.stderr
    assert json.loads(output.read_text())["decision"] == "pass"
    assert stat.S_IMODE(os.stat(output).st_mode) == 0o600
    original = output.read_bytes()
    second = subprocess.run(command, text=True, capture_output=True, check=False)
    assert second.returncode != 0
    assert output.read_bytes() == original


def test_cli_returns_two_for_a_valid_rejection_receipt(tmp_path: Path) -> None:
    candidate = manifest(tmp_path, failed={"waveform_numeric"})
    output = tmp_path / "receipt.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(candidate), "--policy", str(POLICY),
         "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(output.read_text())["decision"] == "reject"
