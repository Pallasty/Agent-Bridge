from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs/design/voice-scene"
MODULE_PATH = ROOT / "scripts/story_render_one_shot_worker_implementation_review.py"
RESULT_PATH = (
    VOICE_SCENE / "s621_story_render_one_shot_worker_implementation_review.json"
)
SCHEMA_PATH = (
    VOICE_SCENE / "story_render_one_shot_worker_implementation_review.schema.json"
)
S620_PATH = (
    VOICE_SCENE / "s620_story_render_one_shot_worker_protocol_contract.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_render_one_shot_worker_implementation_review", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(**overrides):
    return load_module().build_implementation_review(
        ROOT,
        s620_path=overrides.pop("s620_path", S620_PATH),
        **overrides,
    )


def test_s621_selects_staged_synthetic_first_implementation() -> None:
    result = build()

    assert result["status"] == (
        "story_render_one_shot_worker_implementation_reviewable"
    )
    assert result["decision"] == (
        "pure_protocol_then_synthetic_supervisor_real_authority_deferred"
    )
    assert [stage["id"] for stage in result["implementation_ladder"]] == [
        "pure_protocol_codec",
        "synthetic_rust_supervisor",
        "private_fixture_worker",
        "owner_confirmation_broker",
        "mcp_registration_and_deployment_review",
    ]
    assert all(
        stage["real_key_read"] is False
        for stage in result["implementation_ladder"][:3]
    )
    assert all(
        stage["real_model_load"] is False
        for stage in result["implementation_ladder"][:2]
    )
    assert result["next_gate"] == "story_render_worker_protocol_codec_implementation"


def test_s621_current_source_facts_keep_runtime_absent() -> None:
    facts = build()["current_source_findings"]

    assert facts["worker_target_absent"] is True
    assert facts["protocol_codec_target_absent"] is True
    assert facts["supervisor_target_absent"] is True
    assert facts["mcp_render_target_absent"] is True
    assert facts["story_command_render_registry_absent"] is True
    assert facts["existing_story_preflight_registered"] is True
    assert facts["existing_mcp_cancellation_aborts_tool_future"] is True
    assert facts["existing_owned_process_group_reaper_present"] is True
    assert facts["required_rust_dependencies_already_present"] == [
        "libc",
        "serde",
        "serde_json",
        "tokio",
        "uuid",
    ]


def test_s621_next_patch_is_pure_protocol_only() -> None:
    patch = build()["selected_next_patch"]

    assert patch["stage"] == "pure_protocol_codec"
    assert patch["allowed_files"] == [
        "scripts/story_render_worker_protocol.py",
        "tests/test_story_render_worker_protocol.py",
        "docs/design/voice-scene/story_render_worker_request.schema.json",
        "docs/design/voice-scene/story_render_worker_response.schema.json",
    ]
    assert patch["modified_existing_files"] == []
    assert patch["forbidden_files"] == [
        "crates/bridge/src/mcp_tools.rs",
        "crates/bridge/src/mcp_tools/story.rs",
        "crates/bridge/src/main.rs",
        "crates/bridge/src/mcp_tools/audio.rs",
        "crates/store",
        "/home/pallasting/.agent-bridge-secure",
    ]
    assert patch["imports_forbidden"] == [
        "subprocess",
        "sqlite3",
        "onnxruntime",
        "torch",
        "sounddevice",
    ]
    assert patch["filesystem_writes_allowed"] is False


def test_s621_freezes_codec_and_supervisor_ownership_boundaries() -> None:
    result = build()
    codec = result["pure_protocol_codec"]
    supervisor = result["synthetic_supervisor_plan"]

    assert codec["entrypoints"] == [
        "decode_request",
        "validate_worker_response",
        "encode_error_response",
        "project_mcp_response",
    ]
    assert codec["authorization_work"] == "shape_and_binding_validation_only"
    assert codec["mac_verification"] is False
    assert codec["nonce_consumption"] is False
    assert codec["model_or_executor_import"] is False
    assert supervisor["ownership"] == "detached_cleanup_task_owns_child_and_lock"
    assert supervisor["cancel_path"] == (
        "drop_guard_signals_cleanup_task_which_terminates_group_and_waits"
    )
    assert supervisor["kill_on_drop_alone_sufficient"] is False
    assert supervisor["host_lock"] == "nonblocking_flock_held_by_cleanup_task"
    assert supervisor["test_workers"] == [
        "success",
        "malformed_output",
        "stdout_overflow",
        "stderr_overflow",
        "hang",
        "term_ignoring_descendant",
    ]
    assert supervisor["mcp_registration_in_stage"] is False


def test_s621_does_not_let_mcp_self_issue_owner_authority() -> None:
    boundary = build()["owner_authority_boundary"]

    assert boundary == {
        "mcp_call_is_owner_grant": False,
        "inline_mcp_signer_allowed": False,
        "worker_self_signing_allowed": False,
        "caller_supplied_envelope_is_sufficient": False,
        "independent_owner_confirmation_required": True,
        "real_broker_design_deferred_until": (
            "pure_codec_and_synthetic_supervisor_verified"
        ),
        "real_key_read_in_s621": False,
        "real_grant_issued_in_s621": False,
    }


def test_s621_fault_matrix_covers_protocol_process_and_authority_failures() -> None:
    faults = build()["fault_matrix"]
    by_code = {fault["code"]: fault for fault in faults}

    assert len(faults) >= 18
    assert len(by_code) == len(faults)
    assert all(fault["disposition"] == "fail_closed" for fault in faults)
    assert by_code["duplicate_json_key"]["stage"] == "pure_protocol_codec"
    assert by_code["host_lock_busy"]["effects_forbidden"] == [
        "issue_grant",
        "spawn_worker",
        "consume_nonce",
    ]
    assert by_code["mcp_cancelled"]["required_cleanup"] == [
        "terminate_process_group",
        "wait_worker",
        "release_host_lock",
    ]
    assert by_code["inline_owner_signing_attempt"]["stage"] == (
        "owner_confirmation_broker"
    )
    assert "register_mcp_tool" in by_code["redaction_violation"][
        "effects_forbidden"
    ]


def test_s621_rejects_mutated_s620_authority(tmp_path: Path) -> None:
    changed = json.loads(S620_PATH.read_text(encoding="utf-8"))
    changed["implementation_authorized"] = True
    path = tmp_path / "s620.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(ValueError, match="S620 worker protocol authority invalid"):
        build(s620_path=path)


def test_s621_checked_result_is_exact_schema_valid_builder_output() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    expected = build()
    actual = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(actual)) == []
    assert actual == expected


def test_s621_review_builder_has_no_execution_or_mutation_surface() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "import subprocess",
        "from subprocess",
        "execute_bounded_render(",
        "prepare_installed_secure_bounded_render(",
        "load_installed_authority_key(",
        "import sqlite3",
        "import onnxruntime",
        "pw-play",
        "write_text(",
        "write_bytes(",
        "os.kill",
    ):
        assert forbidden not in source
