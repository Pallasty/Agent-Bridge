from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "scripts" / "story_voice_fixed_source_acquisition_plan.py"
)
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_fixed_source_acquisition_plan.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_fixed_source_acquisition_plan", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_small_file_command_is_revision_pinned_and_weight_excluding(
    tmp_path: Path,
) -> None:
    planner = load_module()
    destination = tmp_path / "fixed"
    receipt = planner.build_plan(
        destination,
        current_snapshot=tmp_path / "current-onnx",
        available_bytes=planner.MINIMUM_WORKSPACE_RESERVE_BYTES * 2,
        destination_exists=False,
    )

    command = receipt["commands"]["small_files_only_argv"]
    assert command[:4] == [
        "hf",
        "download",
        "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "--revision",
    ]
    assert command[4] == (
        "6c3e96b6a2c593ce3e546ee699a5d944de81850e"
    )
    assert command.count("--include") == 11
    assert all("safetensors" not in item for item in command)
    assert receipt["weights"]["authorized"] is False
    assert receipt["weights"]["download_command_emitted"] is False


def test_manifest_partitions_all_files_without_overlap(tmp_path: Path) -> None:
    planner = load_module()
    receipt = planner.build_plan(
        tmp_path / "fixed",
        current_snapshot=tmp_path / "current-onnx",
        available_bytes=planner.MINIMUM_WORKSPACE_RESERVE_BYTES * 2,
        destination_exists=False,
    )

    small = {item["path"] for item in receipt["small_files"]}
    weights = {item["path"] for item in receipt["weights"]["files"]}
    assert len(small) == 11
    assert weights == {
        "model.safetensors",
        "speech_tokenizer/model.safetensors",
    }
    assert small.isdisjoint(weights)
    assert receipt["weights"]["total_bytes"] == 4_515_695_644


def test_existing_destination_fails_closed(tmp_path: Path) -> None:
    planner = load_module()
    receipt = planner.build_plan(
        tmp_path / "fixed",
        current_snapshot=tmp_path / "current-onnx",
        available_bytes=planner.MINIMUM_WORKSPACE_RESERVE_BYTES * 2,
        destination_exists=True,
    )

    assert receipt["status"] == "blocked"
    assert "isolated_destination_already_exists" in receipt["blockers"]


def test_insufficient_workspace_reserve_fails_closed(
    tmp_path: Path,
) -> None:
    planner = load_module()
    receipt = planner.build_plan(
        tmp_path / "fixed",
        current_snapshot=tmp_path / "current-onnx",
        available_bytes=planner.MINIMUM_WORKSPACE_RESERVE_BYTES - 1,
        destination_exists=False,
    )

    assert receipt["status"] == "blocked"
    assert "insufficient_workspace_reserve" in receipt["blockers"]


def test_current_snapshot_cannot_be_destination_parent(tmp_path: Path) -> None:
    planner = load_module()
    current = tmp_path / "current-onnx"
    receipt = planner.build_plan(
        current / "fixed",
        current_snapshot=current,
        available_bytes=planner.MINIMUM_WORKSPACE_RESERVE_BYTES * 2,
        destination_exists=False,
    )

    assert receipt["status"] == "blocked"
    assert "destination_overlaps_current_snapshot" in receipt["blockers"]


def test_plan_records_no_external_or_model_effects(tmp_path: Path) -> None:
    planner = load_module()
    receipt = planner.build_plan(
        tmp_path / "fixed",
        current_snapshot=tmp_path / "current-onnx",
        available_bytes=planner.MINIMUM_WORKSPACE_RESERVE_BYTES * 2,
        destination_exists=False,
    )

    assert receipt["runtime_effects"] == {
        "network_requests": False,
        "created_destination": False,
        "downloaded_small_files": False,
        "downloaded_weights": False,
        "executed_converter": False,
        "executed_onnx_graphs": False,
        "replaced_current_snapshot": False,
        "used_gpu": False,
        "played_audio": False,
    }


def test_repository_receipt_validates_against_schema() -> None:
    jsonschema = __import__("jsonschema")
    planner = load_module()
    receipt = planner.build_plan(
        Path(
            "/4TNVMe2/aiot_weights/qwen3_tts/original/"
            "Qwen3-TTS-12Hz-1.7B-CustomVoice/"
            "6c3e96b6a2c593ce3e546ee699a5d944de81850e"
        ),
        current_snapshot=Path(
            "/4TNVMe2/aiot_weights/modelscope/models/"
            "onnx-community--Qwen3-TTS-12Hz-1.7B-CustomVoice/"
            "snapshots/master"
        ),
        available_bytes=1_677_395_083_264,
        destination_exists=False,
    )
    schema = json.loads(SCHEMA_PATH.read_text())

    jsonschema.validate(receipt, schema)
