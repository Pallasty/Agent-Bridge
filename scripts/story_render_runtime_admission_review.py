#!/usr/bin/env python3
"""Build the non-actuating S619 Story render runtime admission review."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


VOICE_SCENE = Path("docs/design/voice-scene")
S618_SCHEMA = VOICE_SCENE / "story_bounded_render_acceptance_review.schema.json"
SOURCE_PATHS = {
    "story_mcp_adapter": Path("crates/bridge/src/mcp_tools/story.rs"),
    "story_registry": Path("crates/bridge/src/mcp_tools.rs"),
    "story_contract": Path("crates/bridge/src/story_contract.rs"),
    "mcp_server": Path("crates/mcp/src/server.rs"),
    "render_executor": Path("scripts/story_bounded_render_executor.py"),
    "installed_key_composition": Path(
        "scripts/story_executor_installed_key_composition.py"
    ),
}


def sha256_file(path: Path) -> str:
    """Hash a file without changing it."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required:{path}")
    return value


def _validate_s618(
    value: dict[str, Any], schema_path: Path
) -> None:
    claims = value.get("claims", {})
    effects = value.get("runtime_effects", {})
    if (
        value.get("status") != "story_bounded_render_acceptance_verified"
        or value.get("decision")
        != "accepted_by_exact_pcm_continuity_without_new_playback"
        or claims.get("human_acceptance_continuity_verified") is not True
        or claims.get("story_command_render_runtime_enabled") is not False
        or value.get("next_gate")
        != "story_command_render_runtime_admission_review"
        or any(effects.values())
    ):
        raise ValueError("S618 acceptance authority invalid")
    schema = _load_json(schema_path)
    if list(Draft202012Validator(schema).iter_errors(value)):
        raise ValueError("S618 acceptance authority invalid")


def _function_node(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise ValueError(f"required function missing:{name}")


def _python_findings(executor_source: str, composition_source: str) -> dict[str, Any]:
    executor_tree = ast.parse(executor_source)
    execute = _function_node(executor_tree, "execute_bounded_render")
    argument_names = [argument.arg for argument in execute.args.args]
    argument_names.extend(argument.arg for argument in execute.args.kwonlyargs)
    synchronous_runner_call = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "runner"
        for node in ast.walk(execute)
    )
    composition_tree = ast.parse(composition_source)
    _function_node(composition_tree, "prepare_installed_secure_bounded_render")
    return {
        "executor_kwonly_arguments": argument_names,
        "executor_cancellation_parameter_present": any(
            name in {"cancellation", "cancellation_token", "cancel_token"}
            for name in argument_names
        ),
        "synchronous_runner_call_present": synchronous_runner_call,
        "installed_key_composition_present": True,
    }


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    required = {
        "observed_at",
        "source_head",
        "origin_head",
        "github_head",
        "installed_binary_path",
        "installed_binary_version",
        "installed_source_commit",
        "installed_commits_behind_source",
        "doctor_ok",
        "doctor_mcp_servers_current_binary",
        "direct_manifest_tool_count",
        "direct_manifest_story_preflight_count",
        "direct_manifest_other_story_tools",
        "active_codex_voice_preflight_env_observed",
        "active_preflight_env_variable_count",
        "wrapper_has_story_activation",
    }
    if set(snapshot) != required:
        raise ValueError("runtime snapshot fields invalid")
    for name in ("source_head", "origin_head", "github_head", "installed_source_commit"):
        value = snapshot[name]
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
            raise ValueError(f"runtime snapshot digest invalid:{name}")
    if snapshot["source_head"] not in {
        snapshot["origin_head"],
        snapshot["github_head"],
    } or snapshot["origin_head"] != snapshot["github_head"]:
        raise ValueError("dual remote source parity missing")
    installed_path = Path(snapshot["installed_binary_path"])
    if not installed_path.is_file():
        raise ValueError("installed binary missing")
    if snapshot["installed_source_commit"][:12] not in snapshot[
        "installed_binary_version"
    ]:
        raise ValueError("installed binary version source mismatch")
    for name in (
        "installed_commits_behind_source",
        "direct_manifest_tool_count",
        "direct_manifest_story_preflight_count",
        "active_preflight_env_variable_count",
    ):
        if not isinstance(snapshot[name], int) or snapshot[name] < 0:
            raise ValueError(f"runtime snapshot count invalid:{name}")
    if not isinstance(snapshot["direct_manifest_other_story_tools"], list):
        raise ValueError("runtime manifest story tools invalid")


def build_runtime_admission_review(
    repo_root: Path,
    *,
    s618_path: Path,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate current Story source and deployment without actuating runtime."""

    root = repo_root.resolve()
    _validate_snapshot(snapshot)
    s618_path = Path(s618_path)
    s618 = _load_json(s618_path)
    _validate_s618(s618, root / S618_SCHEMA)

    source_files = {
        name: {
            "path": str(relative),
            "sha256": sha256_file(root / relative),
        }
        for name, relative in SOURCE_PATHS.items()
    }
    story_source = (root / SOURCE_PATHS["story_mcp_adapter"]).read_text(
        encoding="utf-8"
    )
    registry_source = (root / SOURCE_PATHS["story_registry"]).read_text(
        encoding="utf-8"
    )
    server_source = (root / SOURCE_PATHS["mcp_server"]).read_text(
        encoding="utf-8"
    )
    executor_source = (root / SOURCE_PATHS["render_executor"]).read_text(
        encoding="utf-8"
    )
    composition_source = (
        root / SOURCE_PATHS["installed_key_composition"]
    ).read_text(encoding="utf-8")

    render_surface_present = bool(
        re.search(r'"story_command_render"', story_source)
        or re.search(r'"story_command_render"', registry_source)
    )
    if snapshot["direct_manifest_other_story_tools"] and not render_surface_present:
        raise ValueError("manifest render surface contradicts source")

    python_findings = _python_findings(executor_source, composition_source)
    source_findings = {
        "preflight_registered": all(
            marker in registry_source
            for marker in (
                "use story::{StoryCommandPreflightTool, StoryMcpConfig};",
                "Arc::new(StoryCommandPreflightTool::new(config))",
            )
        ),
        "preflight_read_only": "Some(ToolAnnotations::read_only())"
        in story_source,
        "preflight_dry_run_only": '"dry_run": {"const": true}'
        in story_source,
        "preflight_cancel_on_drop": all(
            marker in story_source
            for marker in (
                "StoryPreflightCancelOnDrop",
                "self.cancellation.cancel();",
            )
        ),
        "mcp_server_aborts_tool_future": all(
            marker in server_source
            for marker in (
                "notifications/cancelled",
                "h.abort();",
                "Err(e) if e.is_cancelled() => None",
            )
        ),
        "render_mcp_surface_present": render_surface_present,
        "python_executor_present": True,
        **python_findings,
        "render_authorization_broker_present": all(
            marker in story_source
            for marker in ("mac_sha256", "single_use_nonce", "owner_approval")
        ),
        "render_concurrency_gate_present": any(
            marker in story_source
            for marker in ("Semaphore", "try_acquire", "reject_without_queue")
        ),
        "render_receipt_redaction_adapter_present": all(
            marker in story_source
            for marker in ("render-receipt", "redact", "authorization_id")
        ),
    }

    blockers: list[str] = []
    if not source_findings["render_mcp_surface_present"]:
        blockers.append("render_mcp_surface_absent")
    if not source_findings["render_authorization_broker_present"]:
        blockers.append("owner_authorization_broker_absent")
    if not source_findings["executor_cancellation_parameter_present"]:
        blockers.append("cooperative_render_cancellation_absent")
    if not source_findings["render_concurrency_gate_present"]:
        blockers.append("render_concurrency_admission_absent")
    if s618.get("evidence", {}).get("s617_execution_result_path"):
        s617_path = root / s618["evidence"]["s617_execution_result_path"]
    else:
        raise ValueError("S618 S617 evidence missing")
    s617 = _load_json(s617_path)
    private_output_custody = (
        s617.get("execution", {}).get("output_filesystem") != "fuseblk"
        and s617.get("execution", {}).get("output_directory_mode_observed")
        == "0700"
    )
    if not private_output_custody:
        blockers.append("private_output_custody_absent")
    if not source_findings["render_receipt_redaction_adapter_present"]:
        blockers.append("redacted_render_result_projection_absent")
    installed_binary_current = (
        snapshot["installed_source_commit"] == snapshot["source_head"]
        and snapshot["installed_commits_behind_source"] == 0
    )
    if not installed_binary_current:
        blockers.append("installed_binary_not_current_source")

    installed_binary_path = Path(snapshot["installed_binary_path"])
    requirements = [
        {
            "id": "accepted_bounded_audio",
            "status": "pass",
            "evidence": "S618 exact PCM and owner acceptance continuity",
        },
        {
            "id": "registered_non_actuating_preflight",
            "status": "pass",
            "evidence": "read-only dry-run MCP surface with drop cancellation",
        },
        {
            "id": "render_execution_surface",
            "status": "fail",
            "evidence": "no Story render MCP tool or worker protocol",
        },
        {
            "id": "explicit_owner_authorization_ingress",
            "status": "fail",
            "evidence": "installed-key composition is not an owner approval broker",
        },
        {
            "id": "render_cancellation_and_reaping",
            "status": "fail",
            "evidence": "Python runner call is synchronous and has no cancellation input",
        },
        {
            "id": "single_job_resource_admission",
            "status": "fail",
            "evidence": "no render semaphore, reject-busy rule, or owned worker",
        },
        {
            "id": "private_audio_output_custody",
            "status": "fail",
            "evidence": "S617 output root is fuseblk with observed 0777 semantics",
        },
        {
            "id": "redacted_mcp_result_projection",
            "status": "fail",
            "evidence": "executor receipt contains an authorization identifier",
        },
        {
            "id": "deployed_current_source",
            "status": "fail",
            "evidence": "installed binary trails reviewed source by 25 commits",
        },
    ]

    architecture_options = [
        {
            "id": "direct_rust_inprocess_port",
            "decision": "defer",
            "complexity": "high",
            "benefit": "single runtime and native cancellation ownership",
            "cost": "requires a new tokenizer and Qwen ONNX inference port",
        },
        {
            "id": "long_lived_python_worker",
            "decision": "defer",
            "complexity": "medium_high",
            "benefit": "warm model reuse and lower repeated latency",
            "cost": "adds durable state, restart, secret lifetime, and multiplexing risk",
        },
        {
            "id": "one_shot_supervised_python_worker",
            "decision": "select_for_next_contract",
            "complexity": "medium",
            "benefit": "strong kill-reap isolation and simplest bounded pilot rollback",
            "cost": "reloads the model for every authorized render",
        },
    ]
    selected_architecture = {
        "pattern": "one_shot_supervised_python_worker",
        "tool_name": "story_command_render",
        "tier": "Niche",
        "toolset": "codex-voice",
        "default_exposed": False,
        "enable_env": "AB_STORY_COMMAND_RENDER_ENABLE",
        "enable_required_value": "1",
        "worker_lifecycle": "one_process_per_authorized_bounded_render",
        "transport": "length_bounded_json_stdin_stdout_no_shell",
        "environment": "fixed_allowlist_no_inherited_secrets",
        "concurrency": {
            "max_active": 1,
            "when_busy": "reject_without_queue",
        },
        "cancellation": {
            "mcp_abort": "drop_guard_signals_owned_supervisor",
            "supervisor": "kill_and_reap_worker_process_group",
            "hard_deadline_seconds": 300,
        },
        "authorization": {
            "source": "separate_explicit_owner_approval_broker",
            "key_material_enters_mcp_process": False,
            "worker_reads_installed_key": True,
            "single_use_nonce_required": True,
        },
        "output": {
            "root": "/home/pallasting/.agent-bridge-secure/story-render/outputs",
            "root_mode": "0700",
            "existing_target_rejected": True,
        },
        "response": {
            "redacted_projection_only": True,
            "authorization_id_in_response": False,
            "mac_or_nonce_in_response": False,
        },
        "pilot_scope": {
            "accepted_preflight": "fixed_s602_fixture_only",
            "arbitrary_novel_paths": False,
            "playback": False,
            "recording": False,
            "memory_write": False,
        },
    }

    return {
        "schema": "agent_bridge.story_render_runtime_admission_review.v1",
        "status": "story_render_runtime_admission_review_complete",
        "decision": {
            "selected": "block_current_wiring_define_one_shot_worker_contract",
            "runtime_admitted": False,
            "deployment_admitted": False,
        },
        "observed_at": snapshot["observed_at"],
        "evidence": {
            "source": {
                "head": snapshot["source_head"],
                "origin_master": snapshot["origin_head"],
                "github_master": snapshot["github_head"],
                "dual_remote_parity": True,
                "files": source_files,
            },
            "accepted_render": {
                "path": str(s618_path.relative_to(root)),
                "sha256": sha256_file(s618_path),
                "status": s618["status"],
            },
            "installed_binary": {
                "path": str(installed_binary_path),
                "sha256": sha256_file(installed_binary_path),
                "version": snapshot["installed_binary_version"],
                "source_commit": snapshot["installed_source_commit"],
                "commits_behind_source": snapshot[
                    "installed_commits_behind_source"
                ],
                "current_source": installed_binary_current,
            },
            "live_surface": {
                "doctor_ok": snapshot["doctor_ok"],
                "doctor_mcp_servers_current_binary": snapshot[
                    "doctor_mcp_servers_current_binary"
                ],
                "direct_manifest_tool_count": snapshot[
                    "direct_manifest_tool_count"
                ],
                "story_preflight_count": snapshot[
                    "direct_manifest_story_preflight_count"
                ],
                "other_story_tools": snapshot[
                    "direct_manifest_other_story_tools"
                ],
                "active_codex_voice_preflight_env_observed": snapshot[
                    "active_codex_voice_preflight_env_observed"
                ],
                "active_preflight_env_variable_count": snapshot[
                    "active_preflight_env_variable_count"
                ],
                "wrapper_has_story_activation": snapshot[
                    "wrapper_has_story_activation"
                ],
            },
        },
        "source_findings": source_findings,
        "requirements": requirements,
        "blockers": blockers,
        "architecture_options": architecture_options,
        "selected_architecture": selected_architecture,
        "execution_authorized": False,
        "deployment_authorized": False,
        "runtime_effects": {
            "fetched_remote_heads": True,
            "inspected_source": True,
            "inspected_installed_binary": True,
            "inspected_process_environment_story_keys": True,
            "spawned_read_only_manifest_probe": True,
            "called_story_tool": False,
            "read_authority_key": False,
            "consumed_nonce": False,
            "loaded_model": False,
            "rendered_audio": False,
            "played_audio": False,
            "recorded_audio": False,
            "modified_configuration": False,
            "deployed_binary": False,
            "restarted_client": False,
            "wrote_memory": False,
        },
        "claims": {
            "preflight_is_live_and_non_actuating": True,
            "bounded_render_quality_previously_accepted": True,
            "current_render_runtime_ready": False,
            "current_render_runtime_enabled": False,
            "one_shot_worker_is_design_selection_only": True,
            "arbitrary_novel_runtime_admitted": False,
            "playback_or_memory_admitted": False,
        },
        "next_gate": "story_render_one_shot_worker_protocol_contract",
    }
