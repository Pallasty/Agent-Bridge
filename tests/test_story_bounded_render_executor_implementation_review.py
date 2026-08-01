from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_bounded_render_executor_implementation_review.py"
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
SCHEMA_PATH = VOICE_SCENE / "story_bounded_render_executor_implementation_review.schema.json"
RECEIPT_PATH = VOICE_SCENE / "s605_story_bounded_render_executor_implementation_review.json"
EXECUTOR_TARGET = ROOT / "scripts" / "story_bounded_render_executor.py"


def load_module():
    assert MODULE_PATH.exists(), "S605 implementation-review module is missing"
    spec = importlib.util.spec_from_file_location(
        "story_bounded_render_executor_implementation_review", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(**overrides):
    module = load_module()
    kwargs = {
        "execution_contract_path": VOICE_SCENE
        / "s604_story_bounded_render_execution_contract.json",
        "contract_builder_path": ROOT
        / "scripts"
        / "story_bounded_render_execution_contract.py",
        "trusted_runner_path": ROOT
        / "scripts"
        / "story_voice_existing_onnx_trusted_runner.py",
        "preflight_adapter_path": ROOT
        / "scripts"
        / "story_command_integration_preflight.py",
        "executor_target_path": EXECUTOR_TARGET,
    }
    return module.build_implementation_review(**{**kwargs, **overrides})


def write_json(tmp_path: Path, name: str, value: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def test_review_selects_one_isolated_non_mcp_executor() -> None:
    result = build()

    assert result["status"] == (
        "story_bounded_render_executor_implementation_reviewable"
    )
    assert result["decision"] == (
        "isolated_python_executor_source_only_not_authorized"
    )
    assert result["surface"] == {
        "kind": "isolated_python_module",
        "target": str(EXECUTOR_TARGET.resolve()),
        "mcp_tool_registered": False,
        "rust_registry_modified": False,
        "subprocess_or_shell_allowed": False,
        "direct_runner_call_only": True,
    }
    assert result["implementation_authorized"] is False
    assert result["execution_authorized"] is False
    assert all(value is False for value in result["runtime_effects"].values())


def test_review_freezes_authorization_and_custody_boundaries() -> None:
    result = build()

    assert result["authorization_envelope"]["required_fields"] == [
        "authorization_id",
        "contract_sha256",
        "preflight_sha256",
        "output_directory",
        "action",
        "issued_at",
        "expires_at",
        "single_use_nonce",
    ]
    assert result["authorization_envelope"]["action"] == "render"
    assert result["authorization_envelope"]["single_use"] is True
    assert result["output_custody"] == {
        "root_from_contract_only": True,
        "dedicated_new_directory_required": True,
        "existing_target_rejected": True,
        "temporary_files_scoped_to_new_directory": True,
        "atomic_finalization_required": True,
        "cleanup_only_executor_created_files": True,
    }
    assert result["playback_boundary"]["executor_may_play"] is False
    assert result["memory_boundary"]["executor_may_write_memory"] is False


def test_review_fault_matrix_fails_closed_before_later_effects() -> None:
    result = build()
    faults = result["fault_matrix"]

    assert len(faults) >= 12
    assert len({row["code"] for row in faults}) == len(faults)
    assert all(row["disposition"] == "fail_closed" for row in faults)
    by_code = {row["code"]: row for row in faults}
    assert by_code["missing_render_grant"]["effects_forbidden"] == [
        "create_output_directory",
        "load_model",
        "render_audio",
    ]
    assert "play_audio" in by_code["machine_audio_gate_failed"][
        "effects_forbidden"
    ]
    assert by_code["memory_write_requested"]["phase"] == "request_validation"
    assert by_code["recording_requested"]["phase"] == "request_validation"


def test_review_rejects_contract_or_source_drift(tmp_path: Path) -> None:
    contract = json.loads(
        (VOICE_SCENE / "s604_story_bounded_render_execution_contract.json").read_text(
            encoding="utf-8"
        )
    )
    authorized = copy.deepcopy(contract)
    authorized["execution_authorized"] = True
    with pytest.raises(ValueError, match="S604 execution boundary invalid"):
        build(
            execution_contract_path=write_json(
                tmp_path, "authorized.json", authorized
            )
        )

    runner = tmp_path / "runner.py"
    runner.write_text(
        (ROOT / "scripts" / "story_voice_existing_onnx_trusted_runner.py")
        .read_text(encoding="utf-8")
        + "\n# drift\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="trusted runner SHA-256 mismatch"):
        build(trusted_runner_path=runner)


def test_review_refuses_to_overwrite_an_existing_executor(tmp_path: Path) -> None:
    target = tmp_path / "story_bounded_render_executor.py"
    target.write_text("# existing\n", encoding="utf-8")

    with pytest.raises(ValueError, match="executor target already exists"):
        build(executor_target_path=target)


def test_review_is_deterministic_and_validates_recorded_receipt() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    generated = build()

    assert generated == build()
    assert len(generated["review_sha256"]) == 64
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(generated)) == []
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
    assert receipt == generated
