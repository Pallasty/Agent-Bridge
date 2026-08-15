from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs/design/voice-scene"
MODULE_PATH = ROOT / "scripts/story_render_one_shot_worker_protocol_contract.py"
RESULT_PATH = (
    VOICE_SCENE / "s620_story_render_one_shot_worker_protocol_contract.json"
)
SCHEMA_PATH = (
    VOICE_SCENE / "story_render_one_shot_worker_protocol_contract.schema.json"
)
S619_PATH = VOICE_SCENE / "s619_story_render_runtime_admission_review.json"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_render_one_shot_worker_protocol_contract", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(**overrides):
    return load_module().build_protocol_contract(
        ROOT,
        s619_path=overrides.pop("s619_path", S619_PATH),
        **overrides,
    )


def test_s620_defines_fixed_fixture_one_request_one_response_protocol() -> None:
    result = build()

    assert result["status"] == "story_render_one_shot_worker_protocol_reviewable"
    protocol = result["protocol"]
    assert protocol == {
        "name": "agent_bridge.story-render-worker.v1",
        "encoding": "strict_utf8_json_object",
        "framing": "one_document_then_eof",
        "cardinality": "one_request_one_response",
        "stdin_max_bytes": 65_536,
        "stdout_max_bytes": 65_536,
        "stderr_max_bytes": 16_384,
        "duplicate_object_keys_allowed": False,
        "nonfinite_numbers_allowed": False,
        "trailing_data_allowed": False,
    }
    request = result["request"]
    assert request["exact_fields"] == [
        "protocol",
        "request_id",
        "fixture",
        "authorization",
    ]
    assert request["caller_supplied_text_allowed"] is False
    assert request["caller_supplied_paths_allowed"] is False
    assert request["fixture"] == {
        "preflight": "fixed_s602_fixture_only",
        "chapter": 2,
        "preflight_sha256": (
            "6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb"
        ),
        "execution_contract_sha256": (
            "24edc82e885c7f8e5a934019e78530f0d70a482e15ec04c52824395fef1e0fe8"
        ),
    }


def test_s620_keeps_owner_authority_inside_closed_worker_request() -> None:
    authority = build()["request"]["authorization"]

    assert authority["shape"] == "s608_closed_hmac_sha256_envelope"
    assert authority["exact_fields"] == [
        "authorization_id",
        "contract_sha256",
        "preflight_sha256",
        "output_directory",
        "action",
        "issued_at",
        "expires_at",
        "single_use_nonce",
        "issuer",
        "subject",
        "key_id",
        "mac_sha256",
    ]
    assert authority["action"] == "render"
    assert authority["maximum_ttl_seconds"] == 300
    assert authority["contract_sha256_binding"] == "s620_protocol_contract_sha256"
    assert authority["preflight_sha256_binding"] == "fixed_s602_preflight_sha256"
    assert authority["output_directory_policy"] == (
        "one_private_root_child_named_by_supervisor_render_id"
    )
    assert authority["installed_key_read_by"] == "one_shot_worker_only"
    assert authority["key_material_enters_mcp_process"] is False
    assert authority["nonce_consumed_before_output_creation"] is True
    assert authority["persisted_or_logged_by_supervisor"] is False


def test_s620_requires_host_wide_reject_busy_and_owned_reaping() -> None:
    result = build()
    admission = result["host_admission"]
    supervisor = result["supervisor"]

    assert admission == {
        "scope": "host_wide_across_mcp_processes",
        "mechanism": "nonblocking_exclusive_flock",
        "lock_path": (
            "/home/pallasting/.agent-bridge-secure/story-render/"
            "render-worker.lock"
        ),
        "lock_mode": "0600",
        "max_active": 1,
        "when_busy": "reject_without_queue_or_spawn",
        "held_until": "worker_reaped_and_response_projected",
    }
    assert supervisor["spawn"] == {
        "shell": False,
        "absolute_executable_and_script": True,
        "new_process_group": True,
        "worker_subprocess_spawn_allowed": False,
        "stdin": "pipe_write_once_then_close",
        "stdout": "bounded_pipe",
        "stderr": "bounded_redacted_pipe",
    }
    assert supervisor["termination"] == {
        "deadline_seconds": 300,
        "on_mcp_cancel": "terminate_process_group_then_reap",
        "on_protocol_limit": "terminate_process_group_then_reap",
        "on_parent_death": "worker_receives_sigkill",
        "grace_seconds": 2,
        "escalation": "sigterm_then_sigkill",
        "wait_required_on_every_spawned_path": True,
    }


def test_s620_defines_private_output_and_redacted_projection() -> None:
    result = build()

    assert result["output_custody"] == {
        "root": "/home/pallasting/.agent-bridge-secure/story-render/outputs",
        "root_mode": "0700",
        "job_directory_mode": "0700",
        "artifact_mode": "0600",
        "job_name_source": "supervisor_generated_render_id",
        "render_id_relation": "render_id_equals_request_id",
        "authorization_id_in_job_name": False,
        "existing_target_rejected": True,
        "symlinks_rejected": True,
        "absolute_paths_in_mcp_response": False,
    }
    response = result["response"]
    assert response["success_exact_fields"] == [
        "protocol",
        "request_id",
        "status",
        "render_id",
        "segment_count",
        "assembly",
        "playback_authorized",
        "memory_authorized",
    ]
    assert response["forbidden_fields"] == [
        "authorization_id",
        "mac_sha256",
        "single_use_nonce",
        "key_material",
        "output_directory",
        "absolute_path",
        "exception",
        "traceback",
    ]
    assert response["mcp_projection_allowlist"] == [
        "status",
        "render_id",
        "segment_count",
        "assembly",
        "playback_authorized",
        "memory_authorized",
    ]
    assert response["playback_authorized"] is False
    assert response["memory_authorized"] is False


def test_s620_acquires_host_lock_before_grant_and_discards_failed_grants() -> None:
    result = build()

    assert result["lifecycle"][:6] == [
        "activation_gate_checked",
        "fixed_fixture_call_validated",
        "host_lock_try_acquired",
        "render_identity_generated",
        "explicit_owner_grant_issued",
        "worker_request_validated",
    ]
    assert result["failure_policy"]["owner_grant_declined"] == (
        "release_lock_without_spawn"
    )
    assert result["failure_policy"]["spawn_failure"] == (
        "discard_grant_reference_release_lock_and_require_new_grant"
    )


def test_s620_keeps_environment_and_runtime_default_off() -> None:
    result = build()

    assert result["environment"] == {
        "inherit_parent_environment": False,
        "allowlist": {
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TZ": "UTC",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "CUDA_VISIBLE_DEVICES": "",
            "HIP_VISIBLE_DEVICES": "",
            "ROCR_VISIBLE_DEVICES": "",
        },
        "network_allowed": False,
        "cache_writes_allowed": False,
        "gpu_allowed": False,
    }
    assert result["activation"] == {
        "tool_name": "story_command_render",
        "tier": "Niche",
        "toolset": "codex-voice",
        "default_exposed": False,
        "enable_env": "AB_STORY_COMMAND_RENDER_ENABLE",
        "enable_required_value": "1",
        "enabled_now": False,
    }
    assert result["implementation_authorized"] is False
    assert result["execution_authorized"] is False
    assert result["deployment_authorized"] is False


def test_s620_rejects_mutated_s619_authority(tmp_path: Path) -> None:
    changed = json.loads(S619_PATH.read_text(encoding="utf-8"))
    changed["selected_architecture"]["concurrency"]["max_active"] = 2
    path = tmp_path / "s619.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(ValueError, match="S619 runtime admission authority invalid"):
        build(s619_path=path)


def test_s620_checked_in_result_is_exact_schema_valid_builder_output() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    expected = build()
    actual = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(actual)) == []
    assert actual == expected


def test_s620_builder_has_no_execution_or_mutation_surface() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "import subprocess",
        "from subprocess",
        "execute_bounded_render(",
        "prepare_installed_secure_bounded_render(",
        "load_installed_authority_key(",
        "sqlite3",
        "onnxruntime",
        "pw-play",
        "write_text(",
        "write_bytes(",
        "os.kill",
    ):
        assert forbidden not in source
