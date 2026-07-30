from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_voice_cpu_int4_numeric_probe.py"
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_cpu_int4_numeric_probe.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_cpu_int4_numeric_probe", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_snapshot(root: Path) -> Path:
    model = root / "cpu_int4" / "codec_embed.onnx"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"fixture")
    return model


def successful_probe() -> dict:
    return {
        "status": "numeric_probe_passed",
        "input": {
            "name": "codec_ids",
            "dtype": "tensor(int64)",
            "shape": [1, 4],
            "values": [0, 1, 2, 3],
        },
        "output": {
            "name": "codec_embeds_Q4",
            "dtype": "float32",
            "shape": [1, 4, 2048],
            "all_finite": True,
            "minimum": -1.0,
            "maximum": 1.0,
            "mean": 0.0,
            "sha256_run_1": "a" * 64,
            "sha256_run_2": "a" * 64,
            "deterministic": True,
        },
    }


def test_owner_authorization_is_required_before_graph_execution(
    tmp_path: Path,
) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    calls = []

    receipt = probe.run_numeric_gate(
        snapshot,
        owner_authorized=False,
        runner=lambda path, timeout: calls.append((path, timeout)),
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["owner_authorization_required"]
    assert calls == []
    assert receipt["runtime_effects"]["executed_graphs"] is False


def test_success_requires_finite_deterministic_bounded_output(
    tmp_path: Path,
) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    model = make_snapshot(snapshot)
    calls = []

    receipt = probe.run_numeric_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda path, timeout: (
            calls.append((path, timeout)) or successful_probe()
        ),
        timeout_seconds=19,
    )

    assert calls == [(model, 19)]
    assert receipt["status"] == "numeric_probe_passed_no_audio"
    assert receipt["blockers"] == []
    assert receipt["probe"]["output"]["all_finite"] is True
    assert receipt["probe"]["output"]["deterministic"] is True
    assert receipt["runtime_effects"] == {
        "created_inference_session": True,
        "executed_graphs": True,
        "execution_count": 2,
        "generated_tokens": False,
        "rendered_audio": False,
        "played_audio": False,
        "used_gpu": False,
        "imported_community_python": False,
    }


def test_nonfinite_or_nondeterministic_output_fails_closed(
    tmp_path: Path,
) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    result = successful_probe()
    result["output"]["all_finite"] = False
    result["output"]["deterministic"] = False

    receipt = probe.run_numeric_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: result,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == [
        "nonfinite_output",
        "nondeterministic_output",
    ]


def test_child_failure_is_sanitized_and_blocks(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)

    receipt = probe.run_numeric_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: {
            "status": "numeric_probe_failed",
            "error_type": "InvalidArgument",
            "error": "input contract mismatch",
        },
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["numeric_probe_failed"]
    assert receipt["probe"]["error_type"] == "InvalidArgument"


def test_numeric_probe_receipt_validates_against_schema(
    tmp_path: Path,
) -> None:
    jsonschema = __import__("jsonschema")
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    receipt = probe.run_numeric_gate(
        snapshot,
        owner_authorized=False,
        runner=lambda _path, _timeout: successful_probe(),
    )

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(receipt, schema)
