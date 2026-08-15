from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "scripts" / "story_voice_cpu_int4_residual_embed_probe.py"
)
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_cpu_int4_residual_embed_probe.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_cpu_int4_residual_embed_probe", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_snapshot(root: Path) -> Path:
    model = root / "cpu_int4" / "residual_embed.onnx"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"fixture")
    return model


def successful_probe() -> dict:
    return {
        "status": "residual_embed_probe_passed",
        "input": {
            "name": "codec_ids",
            "shape": [1, 16],
            "dtype": "int64",
            "fixture": list(range(16)),
        },
        "output": {
            "name": "step_embed",
            "shape": [1, 2048],
            "dtype": "float32",
            "all_finite": True,
            "nonzero": True,
            "minimum": -1.0,
            "maximum": 1.0,
            "mean": 0.0,
        },
        "sha256_run_1": "e" * 64,
        "sha256_run_2": "e" * 64,
        "deterministic": True,
    }


def test_owner_authorization_blocks_execution(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    calls = []

    receipt = probe.run_residual_embed_gate(
        snapshot,
        owner_authorized=False,
        runner=lambda path, timeout: calls.append((path, timeout)),
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["owner_authorization_required"]
    assert calls == []


def test_fixed_codec_frame_numeric_probe_passes(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    model = make_snapshot(snapshot)
    calls = []

    receipt = probe.run_residual_embed_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda path, timeout: (
            calls.append((path, timeout)) or successful_probe()
        ),
        timeout_seconds=37,
    )

    assert calls == [(model, 37)]
    assert receipt["status"] == "residual_embed_probe_passed_no_forwarding"
    assert receipt["blockers"] == []
    assert receipt["runtime_effects"] == {
        "created_inference_session": True,
        "executed_graphs": True,
        "execution_count": 2,
        "forwarded_step_embedding": False,
        "generated_codec_frame": False,
        "decoded_waveform": False,
        "played_audio": False,
        "used_gpu": False,
        "imported_community_python": False,
    }


def test_nonfinite_or_zero_output_fails_closed(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    result = successful_probe()
    result["output"]["all_finite"] = False
    result["output"]["nonzero"] = False

    receipt = probe.run_residual_embed_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: result,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == [
        "nonfinite_output",
        "degenerate_zero_output",
    ]


def test_wrong_shape_or_nondeterminism_fails_closed(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    result = successful_probe()
    result["output"]["shape"] = [1, 1024]
    result["deterministic"] = False

    receipt = probe.run_residual_embed_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: result,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == [
        "output_contract_mismatch",
        "nondeterministic_output",
    ]


def test_child_failure_is_recorded_without_forwarding(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)

    receipt = probe.run_residual_embed_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: {
            "status": "residual_embed_probe_failed",
            "error_type": "InvalidArgument",
            "error": "codec IDs rejected",
        },
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["residual_embed_probe_failed"]
    assert receipt["runtime_effects"]["forwarded_step_embedding"] is False


def test_receipt_validates_against_schema(tmp_path: Path) -> None:
    jsonschema = __import__("jsonschema")
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    receipt = probe.run_residual_embed_gate(
        snapshot,
        owner_authorized=False,
        runner=lambda _path, _timeout: successful_probe(),
    )

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(receipt, schema)
