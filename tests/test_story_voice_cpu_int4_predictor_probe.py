from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_voice_cpu_int4_predictor_probe.py"
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_cpu_int4_predictor_probe.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_cpu_int4_predictor_probe", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_snapshot(root: Path) -> Path:
    model = root / "cpu_int4" / "code_predictor.onnx"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"fixture")
    return model


def successful_probe() -> dict:
    return {
        "status": "predictor_probe_passed",
        "inputs": [
            {
                "name": "talker_hidden",
                "dtype": "tensor(float)",
                "shape": [1, 2048],
                "fixture": "zeros",
            },
            {
                "name": "codec_ids",
                "dtype": "tensor(int64)",
                "shape": [1, 16],
                "fixture": "zeros",
            },
        ],
        "output": {
            "name": "group_logits",
            "dtype": "float32",
            "shape": [1, 15, 2048],
            "all_finite": True,
            "minimum": -2.0,
            "maximum": 2.0,
            "mean": 0.0,
            "sha256_run_1": "b" * 64,
            "sha256_run_2": "b" * 64,
            "deterministic": True,
        },
    }


def test_authorization_blocks_predictor_execution(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    calls = []

    receipt = probe.run_predictor_gate(
        snapshot,
        owner_authorized=False,
        runner=lambda path, timeout: calls.append((path, timeout)),
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["owner_authorization_required"]
    assert calls == []
    assert receipt["runtime_effects"]["executed_graphs"] is False


def test_finite_deterministic_predictor_output_passes(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    model = make_snapshot(snapshot)
    calls = []

    receipt = probe.run_predictor_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda path, timeout: (
            calls.append((path, timeout)) or successful_probe()
        ),
        timeout_seconds=23,
    )

    assert calls == [(model, 23)]
    assert receipt["status"] == "predictor_probe_passed_no_generation"
    assert receipt["blockers"] == []
    assert receipt["runtime_effects"] == {
        "created_inference_session": True,
        "executed_graphs": True,
        "execution_count": 2,
        "sampled_codec_ids": False,
        "generated_tokens": False,
        "rendered_audio": False,
        "played_audio": False,
        "used_gpu": False,
        "imported_community_python": False,
    }


def test_nonfinite_or_nondeterministic_logits_fail_closed(
    tmp_path: Path,
) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    result = successful_probe()
    result["output"]["all_finite"] = False
    result["output"]["deterministic"] = False

    receipt = probe.run_predictor_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: result,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == [
        "nonfinite_output",
        "nondeterministic_output",
    ]


def test_child_contract_failure_is_recorded(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)

    receipt = probe.run_predictor_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: {
            "status": "predictor_probe_failed",
            "error_type": "ValueError",
            "error": "unexpected input contract",
        },
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["predictor_probe_failed"]
    assert receipt["probe"]["error_type"] == "ValueError"


def test_predictor_receipt_validates_against_schema(tmp_path: Path) -> None:
    jsonschema = __import__("jsonschema")
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    receipt = probe.run_predictor_gate(
        snapshot,
        owner_authorized=False,
        runner=lambda _path, _timeout: successful_probe(),
    )

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(receipt, schema)
