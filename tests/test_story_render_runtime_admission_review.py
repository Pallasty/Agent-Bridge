from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs/design/voice-scene"
MODULE_PATH = ROOT / "scripts/story_render_runtime_admission_review.py"
RESULT_PATH = VOICE_SCENE / "s619_story_render_runtime_admission_review.json"
SCHEMA_PATH = VOICE_SCENE / "story_render_runtime_admission_review.schema.json"
S618_PATH = VOICE_SCENE / "s618_story_bounded_render_acceptance_review.json"
INSTALLED_BINARY = Path("/home/pallasting/.local/bin/agent-bridge.real")


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_render_runtime_admission_review", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runtime_snapshot(**overrides):
    value = {
        "observed_at": "2026-08-02T07:02:39+00:00",
        "source_head": "a5744e82b12301abc589353123a1887c01558bab",
        "origin_head": "a5744e82b12301abc589353123a1887c01558bab",
        "github_head": "a5744e82b12301abc589353123a1887c01558bab",
        "installed_binary_path": INSTALLED_BINARY,
        "installed_binary_version": (
            "agent-bridge 0.14.0 "
            "(v0.14.0-1281-g82fc5f16; 82fc5f169438)"
        ),
        "installed_source_commit": "82fc5f1694385eb58bf1b31a98074be9a03de58b",
        "installed_commits_behind_source": 25,
        "doctor_ok": True,
        "doctor_mcp_servers_current_binary": True,
        "direct_manifest_tool_count": 103,
        "direct_manifest_story_preflight_count": 1,
        "direct_manifest_other_story_tools": [],
        "active_codex_voice_preflight_env_observed": True,
        "active_preflight_env_variable_count": 12,
        "wrapper_has_story_activation": False,
    }
    value.update(overrides)
    return value


def build(**overrides):
    snapshot = runtime_snapshot(**overrides.pop("snapshot", {}))
    return load_module().build_runtime_admission_review(
        ROOT,
        s618_path=overrides.pop("s618_path", S618_PATH),
        snapshot=snapshot,
        **overrides,
    )


def test_s619_detects_preflight_only_surface_and_non_cancellable_executor() -> None:
    result = build()
    findings = result["source_findings"]

    assert findings["preflight_registered"] is True
    assert findings["preflight_read_only"] is True
    assert findings["preflight_dry_run_only"] is True
    assert findings["preflight_cancel_on_drop"] is True
    assert findings["mcp_server_aborts_tool_future"] is True
    assert findings["render_mcp_surface_present"] is False
    assert findings["python_executor_present"] is True
    assert findings["installed_key_composition_present"] is True
    assert findings["executor_cancellation_parameter_present"] is False
    assert findings["synchronous_runner_call_present"] is True
    assert findings["render_authorization_broker_present"] is False
    assert findings["render_concurrency_gate_present"] is False
    assert findings["render_receipt_redaction_adapter_present"] is False


def test_s619_blocks_current_wiring_and_selects_one_shot_supervised_worker() -> None:
    result = build()

    assert result["status"] == "story_render_runtime_admission_review_complete"
    assert result["decision"] == {
        "selected": "block_current_wiring_define_one_shot_worker_contract",
        "runtime_admitted": False,
        "deployment_admitted": False,
    }
    assert result["blockers"] == [
        "render_mcp_surface_absent",
        "owner_authorization_broker_absent",
        "cooperative_render_cancellation_absent",
        "render_concurrency_admission_absent",
        "private_output_custody_absent",
        "redacted_render_result_projection_absent",
        "installed_binary_not_current_source",
    ]
    selected = result["selected_architecture"]
    assert selected["pattern"] == "one_shot_supervised_python_worker"
    assert selected["enable_env"] == "AB_STORY_COMMAND_RENDER_ENABLE"
    assert selected["concurrency"] == {
        "max_active": 1,
        "when_busy": "reject_without_queue",
    }
    assert selected["cancellation"] == {
        "mcp_abort": "drop_guard_signals_owned_supervisor",
        "supervisor": "kill_and_reap_worker_process_group",
        "hard_deadline_seconds": 300,
    }
    assert selected["pilot_scope"]["arbitrary_novel_paths"] is False
    assert selected["pilot_scope"]["playback"] is False
    assert selected["pilot_scope"]["memory_write"] is False
    assert result["next_gate"] == "story_render_one_shot_worker_protocol_contract"


def test_s619_rejects_mutated_s618_authority(tmp_path: Path) -> None:
    s618 = json.loads(S618_PATH.read_text(encoding="utf-8"))
    s618["claims"]["story_command_render_runtime_enabled"] = True
    changed = tmp_path / "s618.json"
    changed.write_text(json.dumps(s618), encoding="utf-8")

    with pytest.raises(ValueError, match="S618 acceptance authority invalid"):
        build(s618_path=changed)


def test_s619_rejects_manifest_claim_inconsistent_with_source() -> None:
    with pytest.raises(ValueError, match="manifest render surface contradicts source"):
        build(snapshot={"direct_manifest_other_story_tools": ["story_command_render"]})


def test_s619_checked_in_result_is_exact_schema_valid_builder_output() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    expected = build()
    actual = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(actual)) == []
    assert actual == expected


def test_s619_review_builder_has_no_execution_or_mutation_surface() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "subprocess",
        "tokio",
        "execute_bounded_render(",
        "prepare_installed_secure_bounded_render(",
        "sqlite3",
        "onnxruntime",
        "pw-play",
        "write_text(",
        "write_bytes(",
    ):
        assert forbidden not in source
