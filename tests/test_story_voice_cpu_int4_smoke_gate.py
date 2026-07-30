from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_voice_cpu_int4_smoke_gate.py"
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_cpu_int4_smoke_receipt.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_cpu_int4_smoke_gate", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_snapshot(root: Path) -> list[str]:
    variant = root / "cpu_int4"
    variant.mkdir(parents=True)
    names = ["codec_embed.onnx", "talker_cache.onnx"]
    (variant / "manifest.json").write_text(
        json.dumps(
            {
                "device": "cpu",
                "precision": "int4",
                "execution_provider": "CPUExecutionProvider",
                "sub_models": {
                    "codec_embed": {"filename": names[0]},
                    "talker_cache": {"filename": names[1]},
                },
            }
        )
    )
    for name in names:
        (variant / name).write_bytes(b"fixture")
    return names


def test_authorization_is_required_before_any_session_probe(
    tmp_path: Path,
) -> None:
    gate = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    calls = []

    receipt = gate.run_smoke_gate(
        snapshot,
        owner_authorized=False,
        available_providers=["CPUExecutionProvider"],
        probe=lambda path, timeout: calls.append((path, timeout)),
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["owner_authorization_required"]
    assert calls == []


def test_only_manifest_referenced_cpu_int4_graphs_are_probed(
    tmp_path: Path,
) -> None:
    gate = load_module()
    snapshot = tmp_path / "snapshot"
    names = make_snapshot(snapshot)
    (snapshot / "cpu_fp32").mkdir()
    (snapshot / "cpu_fp32" / "ignored.onnx").write_bytes(b"ignored")
    calls = []

    def probe(path: Path, timeout: int):
        calls.append((path.name, timeout))
        return {
            "status": "session_created",
            "providers": ["CPUExecutionProvider"],
            "inputs": 2,
            "outputs": 1,
        }

    receipt = gate.run_smoke_gate(
        snapshot,
        owner_authorized=True,
        available_providers=["CPUExecutionProvider"],
        probe=probe,
        timeout_seconds=17,
    )

    assert calls == [(name, 17) for name in names]
    assert receipt["status"] == "session_creation_passed_no_inference"
    assert receipt["probed_models"] == [
        {
            "path": f"cpu_int4/{name}",
            "status": "session_created",
            "providers": ["CPUExecutionProvider"],
            "inputs": 2,
            "outputs": 1,
        }
        for name in names
    ]
    assert receipt["runtime_effects"]["created_inference_sessions"] is True
    assert receipt["runtime_effects"]["executed_graphs"] is False


def test_missing_cpu_provider_blocks_without_probe(tmp_path: Path) -> None:
    gate = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    calls = []

    receipt = gate.run_smoke_gate(
        snapshot,
        owner_authorized=True,
        available_providers=["CUDAExecutionProvider"],
        probe=lambda path, timeout: calls.append((path, timeout)),
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["cpu_execution_provider_unavailable"]
    assert calls == []


def test_probe_failure_is_recorded_and_fail_closed(tmp_path: Path) -> None:
    gate = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)

    def probe(path: Path, _timeout: int):
        if path.name == "talker_cache.onnx":
            return {
                "status": "session_failed",
                "error_type": "InvalidGraph",
                "error": "unsupported operator",
            }
        return {
            "status": "session_created",
            "providers": ["CPUExecutionProvider"],
            "inputs": 1,
            "outputs": 1,
        }

    receipt = gate.run_smoke_gate(
        snapshot,
        owner_authorized=True,
        available_providers=["CPUExecutionProvider"],
        probe=probe,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["session_creation_failed"]
    assert receipt["probed_models"][1]["error_type"] == "InvalidGraph"
    assert receipt["runtime_effects"]["executed_graphs"] is False


def test_smoke_receipt_validates_against_schema(tmp_path: Path) -> None:
    jsonschema = __import__("jsonschema")
    gate = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    receipt = gate.run_smoke_gate(
        snapshot,
        owner_authorized=False,
        available_providers=["CPUExecutionProvider"],
        probe=lambda _path, _timeout: None,
    )

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(receipt, schema)


def test_receipt_binds_runtime_provenance(tmp_path: Path) -> None:
    gate = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)

    receipt = gate.run_smoke_gate(
        snapshot,
        owner_authorized=True,
        available_providers=["CPUExecutionProvider"],
        probe=lambda _path, _timeout: {
            "status": "session_created",
            "providers": ["CPUExecutionProvider"],
            "inputs": 1,
            "outputs": 1,
        },
        runtime_version="1.2.3",
        runtime_executable="/isolated/bin/python",
    )

    assert receipt["runtime"] == {
        "name": "onnxruntime",
        "version": "1.2.3",
        "executable": "/isolated/bin/python",
        "available_providers": ["CPUExecutionProvider"],
    }
