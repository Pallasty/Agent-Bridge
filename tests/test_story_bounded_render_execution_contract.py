from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_bounded_render_execution_contract.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
SCHEMA_PATH = VOICE_SCENE / "story_bounded_render_execution_contract.schema.json"
RECEIPT_PATH = VOICE_SCENE / "s604_story_bounded_render_execution_contract.json"
OUTPUT_ROOT = Path(
    "/Data/Models/agent-bridge/evidence/voice-scene/story-command-runtime"
)


def load_module():
    assert MODULE_PATH.exists(), "S604 execution-contract module is missing"
    spec = importlib.util.spec_from_file_location(
        "story_bounded_render_execution_contract", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(**overrides):
    module = load_module()
    kwargs = {
        "preflight_receipt_path": VOICE_SCENE
        / "s602_story_fixture_mcp_preflight_receipt.json",
        "accepted_render_receipt_path": VOICE_SCENE
        / "s603_story_fixture_bounded_render_receipt.json",
        "trusted_runner_path": ROOT
        / "scripts"
        / "story_voice_existing_onnx_trusted_runner.py",
        "output_root": OUTPUT_ROOT,
    }
    return module.build_execution_contract(**{**kwargs, **overrides})


def write_variant(tmp_path: Path, name: str, value: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def test_contract_separates_each_runtime_authority() -> None:
    result = build()

    assert result["status"] == "story_bounded_render_execution_contract_reviewable"
    assert result["execution_authorized"] is False
    assert result["authority"]["render"] == {
        "grant_required": True,
        "grant_present": False,
        "single_use": True,
        "bound_fields": [
            "contract_sha256",
            "preflight_sha256",
            "output_directory",
        ],
    }
    assert result["authority"]["playback"]["grant_present"] is False
    assert result["authority"]["playback"]["requires_machine_gate"] is True
    assert result["authority"]["record"] == {
        "supported": False,
        "grant_present": False,
    }
    assert result["authority"]["memory_write"] == {
        "supported": False,
        "grant_present": False,
    }
    assert all(value is False for value in result["runtime_effects"].values())


def test_contract_freezes_narrow_fixture_bounds_and_safe_output_root() -> None:
    result = build()

    assert result["bounds"] == {
        "max_segments_per_grant": 3,
        "max_codec_frames_per_segment": 100,
        "max_assembled_duration_seconds": 30.0,
        "sample_rate_hz": 24000,
        "channels": 1,
        "allowed_speakers": ["Serena", "Vivian"],
        "output_root": str(OUTPUT_ROOT),
        "existing_output_overwrite_allowed": False,
        "network_allowed": False,
        "gpu_allowed": False,
    }
    assert result["evidence"]["selected_segments"] == 3
    assert result["evidence"]["model_inference_sha256"] == (
        "70d3911f6923000d776cd16d575bf6518f6a638ee0adf8c1b60d0e1d34fdeb75"
    )


def test_contract_rejects_unaccepted_or_drifted_evidence(tmp_path: Path) -> None:
    render = json.loads(
        (VOICE_SCENE / "s603_story_fixture_bounded_render_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    unaccepted = copy.deepcopy(render)
    unaccepted["owner_feedback"]["accepted"] = False
    with pytest.raises(ValueError, match="bounded render acceptance invalid"):
        build(
            accepted_render_receipt_path=write_variant(
                tmp_path, "unaccepted.json", unaccepted
            )
        )

    drifted = copy.deepcopy(render)
    drifted["preflight"]["preflight_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="preflight provenance mismatch"):
        build(
            accepted_render_receipt_path=write_variant(
                tmp_path, "drifted.json", drifted
            )
        )


def test_contract_rejects_accepted_receipt_outside_execution_bounds(
    tmp_path: Path,
) -> None:
    render = json.loads(
        (VOICE_SCENE / "s603_story_fixture_bounded_render_receipt.json").read_text(
            encoding="utf-8"
        )
    )

    frame_capped = copy.deepcopy(render)
    frame_capped["segments"][0]["generated_codec_frames"] = 100
    with pytest.raises(ValueError, match="accepted render exceeds execution bounds"):
        build(
            accepted_render_receipt_path=write_variant(
                tmp_path, "frame-capped.json", frame_capped
            )
        )

    unknown_speaker = copy.deepcopy(render)
    unknown_speaker["segments"][0]["speaker"] = "Dylan"
    with pytest.raises(ValueError, match="accepted render exceeds execution bounds"):
        build(
            accepted_render_receipt_path=write_variant(
                tmp_path, "unknown-speaker.json", unknown_speaker
            )
        )

    overlong = copy.deepcopy(render)
    overlong["assembly"]["duration_seconds"] = 30.01
    with pytest.raises(ValueError, match="accepted render exceeds execution bounds"):
        build(
            accepted_render_receipt_path=write_variant(
                tmp_path, "overlong.json", overlong
            )
        )


def test_contract_rejects_unsafe_output_roots(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="output root outside voice evidence root"):
        build(output_root=tmp_path / "story-runtime")
    with pytest.raises(ValueError, match="dedicated output root required"):
        build(output_root=Path("/Data/Models/agent-bridge/evidence/voice-scene"))


def test_contract_is_deterministic_and_hash_binds_the_runner(tmp_path: Path) -> None:
    original = build()
    assert original == build()
    assert len(original["contract_sha256"]) == 64
    assert original["evidence"]["contract_builder_path"] == str(
        MODULE_PATH.resolve()
    )
    assert len(original["evidence"]["contract_builder_sha256"]) == 64

    runner = tmp_path / "runner.py"
    runner.write_text(
        (ROOT / "scripts" / "story_voice_existing_onnx_trusted_runner.py")
        .read_text(encoding="utf-8")
        + "\n# drift\n",
        encoding="utf-8",
    )
    drifted = build(trusted_runner_path=runner)
    assert drifted["evidence"]["trusted_runner_sha256"] != original["evidence"][
        "trusted_runner_sha256"
    ]
    assert drifted["contract_sha256"] != original["contract_sha256"]


def test_real_contract_and_receipt_validate_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(build())) == []
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
    assert receipt == build()
