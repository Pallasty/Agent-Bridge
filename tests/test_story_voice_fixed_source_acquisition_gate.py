from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "scripts" / "story_voice_fixed_source_acquisition_gate.py"
)
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_fixed_source_acquisition_gate.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_fixed_source_acquisition_gate", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safetensors_fixture(path: Path, tensors: list[str]) -> None:
    header = {
        name: {
            "dtype": "F32",
            "shape": [1],
            "data_offsets": [index * 4, (index + 1) * 4],
        }
        for index, name in enumerate(tensors)
    }
    encoded = json.dumps(header, separators=(",", ":")).encode()
    padding = b" " * ((8 - len(encoded) % 8) % 8)
    body = encoded + padding
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        struct.pack("<Q", len(body)) + body + b"\0" * (4 * len(tensors))
    )


def make_snapshot(root: Path) -> tuple[Path, dict]:
    snapshot = root / "source"
    safetensors_fixture(snapshot / "model.safetensors", ["talker.weight"])
    safetensors_fixture(
        snapshot / "speech_tokenizer" / "model.safetensors",
        ["encoder.weight", "decoder.weight"],
    )
    (snapshot / "config.json").write_text("{}")
    (snapshot / "configuration.json").write_text("{}")
    (snapshot / "README.md").write_text("ModelScope packaging")
    contract = {}
    for rel in (
        "model.safetensors",
        "speech_tokenizer/model.safetensors",
    ):
        path = snapshot / rel
        contract[rel] = {
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return snapshot, contract


def test_matching_weight_payload_is_fixed_revision_equivalent(
    tmp_path: Path,
) -> None:
    gate = load_module()
    snapshot, contract = make_snapshot(tmp_path)

    receipt = gate.verify_acquisition(
        snapshot,
        current_onnx_snapshot=tmp_path / "current-onnx",
        expected_weights=contract,
    )

    assert receipt["status"] == (
        "weight_payload_fixed_revision_verified_packaging_divergent"
    )
    assert receipt["weight_payload_fixed_revision_equivalent"] is True
    assert receipt["packaging_exact_fixed_revision"] is False
    assert receipt["source"]["declared_revision"] == "master"
    assert receipt["source"]["declared_revision_immutable"] is False


def test_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    gate = load_module()
    snapshot, contract = make_snapshot(tmp_path)
    contract["model.safetensors"]["sha256"] = "0" * 64

    receipt = gate.verify_acquisition(
        snapshot,
        current_onnx_snapshot=tmp_path / "current-onnx",
        expected_weights=contract,
    )

    assert receipt["status"] == "blocked"
    assert receipt["weight_payload_fixed_revision_equivalent"] is False
    assert "weight_payload_hash_or_size_mismatch" in receipt["blockers"]


def test_missing_weight_fails_closed(tmp_path: Path) -> None:
    gate = load_module()
    snapshot, contract = make_snapshot(tmp_path)
    (snapshot / "speech_tokenizer" / "model.safetensors").unlink()

    receipt = gate.verify_acquisition(
        snapshot,
        current_onnx_snapshot=tmp_path / "current-onnx",
        expected_weights=contract,
    )

    assert receipt["status"] == "blocked"
    assert receipt["missing_files"] == [
        "speech_tokenizer/model.safetensors"
    ]


def test_source_must_not_overlap_current_onnx(tmp_path: Path) -> None:
    gate = load_module()
    snapshot, contract = make_snapshot(tmp_path)

    receipt = gate.verify_acquisition(
        snapshot,
        current_onnx_snapshot=snapshot,
        expected_weights=contract,
    )

    assert receipt["status"] == "blocked"
    assert "source_overlaps_current_onnx_snapshot" in receipt["blockers"]


def test_gate_does_not_execute_models_or_mutate_files(tmp_path: Path) -> None:
    gate = load_module()
    snapshot, contract = make_snapshot(tmp_path)
    receipt = gate.verify_acquisition(
        snapshot,
        current_onnx_snapshot=tmp_path / "current-onnx",
        expected_weights=contract,
    )

    assert receipt["runtime_effects"] == {
        "hashed_weight_files": 2,
        "parsed_safetensors_headers": 2,
        "downloaded_files": False,
        "created_model_files": False,
        "executed_converter": False,
        "executed_model": False,
        "replaced_current_snapshot": False,
        "used_gpu": False,
        "played_audio": False,
    }
    assert receipt["conversion_ready"] is False


def test_repository_receipt_validates_against_schema(tmp_path: Path) -> None:
    jsonschema = __import__("jsonschema")
    gate = load_module()
    snapshot, contract = make_snapshot(tmp_path)
    receipt = gate.verify_acquisition(
        snapshot,
        current_onnx_snapshot=tmp_path / "current-onnx",
        expected_weights=contract,
    )

    jsonschema.validate(receipt, json.loads(SCHEMA_PATH.read_text()))
