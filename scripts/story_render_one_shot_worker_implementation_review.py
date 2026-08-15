#!/usr/bin/env python3
"""Build the non-actuating S621 one-shot worker implementation review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


VOICE_SCENE = Path("docs/design/voice-scene")
S620_SCHEMA = VOICE_SCENE / "story_render_one_shot_worker_protocol_contract.schema.json"
SOURCE_PATHS = {
    "s620_builder": Path(
        "scripts/story_render_one_shot_worker_protocol_contract.py"
    ),
    "story_preflight_mcp": Path("crates/bridge/src/mcp_tools/story.rs"),
    "mcp_registry": Path("crates/bridge/src/mcp_tools.rs"),
    "bridge_lib": Path("crates/bridge/src/lib.rs"),
    "mcp_server": Path("crates/mcp/src/server.rs"),
    "orphan_reaper": Path("crates/bridge/src/orphan_reaper.rs"),
    "bridge_cargo": Path("crates/bridge/Cargo.toml"),
}
TARGET_PATHS = {
    "worker": Path("scripts/story_render_one_shot_worker.py"),
    "protocol_codec": Path("scripts/story_render_worker_protocol.py"),
    "supervisor": Path("crates/bridge/src/story_render_supervisor.rs"),
    "mcp_render": Path("crates/bridge/src/mcp_tools/story_render.rs"),
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required:{path}")
    return value


def _validate_s620(value: dict[str, Any], schema: dict[str, Any]) -> None:
    bound_names = (
        "evidence",
        "activation",
        "protocol",
        "request",
        "host_admission",
        "supervisor",
        "environment",
        "output_custody",
        "response",
        "lifecycle",
        "failure_policy",
        "implementation_authorized",
        "execution_authorized",
        "deployment_authorized",
        "runtime_effects",
    )
    try:
        bound = {name: value[name] for name in bound_names}
    except KeyError as error:
        raise ValueError("S620 worker protocol authority invalid") from error
    if (
        value.get("status")
        != "story_render_one_shot_worker_protocol_reviewable"
        or value.get("decision")
        != "static_protocol_complete_implementation_and_runtime_blocked"
        or value.get("protocol", {}).get("name")
        != "agent_bridge.story-render-worker.v1"
        or value.get("host_admission", {}).get("scope")
        != "host_wide_across_mcp_processes"
        or value.get("supervisor", {}).get("termination", {}).get(
            "wait_required_on_every_spawned_path"
        )
        is not True
        or value.get("request", {}).get("caller_supplied_text_allowed") is not False
        or value.get("request", {}).get("caller_supplied_paths_allowed") is not False
        or value.get("implementation_authorized") is not False
        or value.get("execution_authorized") is not False
        or value.get("deployment_authorized") is not False
        or any(value.get("runtime_effects", {}).values())
        or value.get("next_gate")
        != "story_render_one_shot_worker_protocol_implementation_review"
        or _digest(bound) != value.get("contract_sha256")
        or list(Draft202012Validator(schema).iter_errors(value))
    ):
        raise ValueError("S620 worker protocol authority invalid")


def _fault(
    code: str,
    stage: str,
    effects_forbidden: list[str],
    required_cleanup: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "stage": stage,
        "disposition": "fail_closed",
        "effects_forbidden": effects_forbidden,
        "required_cleanup": required_cleanup or [],
    }


def _fault_matrix() -> list[dict[str, Any]]:
    no_runtime = [
        "issue_grant",
        "spawn_worker",
        "read_key",
        "consume_nonce",
        "load_model",
        "render_audio",
    ]
    before_spawn = [
        "spawn_worker",
        "read_key",
        "consume_nonce",
        "load_model",
        "render_audio",
    ]
    reap = ["terminate_process_group", "wait_worker", "release_host_lock"]
    rows = [
        _fault("input_oversize", "pure_protocol_codec", no_runtime),
        _fault("invalid_utf8", "pure_protocol_codec", no_runtime),
        _fault("invalid_json_root", "pure_protocol_codec", no_runtime),
        _fault("duplicate_json_key", "pure_protocol_codec", no_runtime),
        _fault("nonfinite_number", "pure_protocol_codec", no_runtime),
        _fault("trailing_json_data", "pure_protocol_codec", no_runtime),
        _fault("unknown_request_field", "pure_protocol_codec", no_runtime),
        _fault("fixture_binding_mismatch", "pure_protocol_codec", no_runtime),
        _fault("authorization_shape_invalid", "pure_protocol_codec", no_runtime),
        _fault(
            "forbidden_response_field",
            "pure_protocol_codec",
            ["project_mcp_response", "register_mcp_tool"],
        ),
        _fault(
            "redaction_violation",
            "pure_protocol_codec",
            ["project_mcp_response", "register_mcp_tool"],
        ),
        _fault(
            "host_lock_busy",
            "synthetic_rust_supervisor",
            ["issue_grant", "spawn_worker", "consume_nonce"],
        ),
        _fault(
            "spawn_failure",
            "synthetic_rust_supervisor",
            before_spawn,
            ["discard_grant_reference", "release_host_lock"],
        ),
        _fault(
            "stdout_overflow",
            "synthetic_rust_supervisor",
            ["accept_worker_response", "project_mcp_response"],
            reap,
        ),
        _fault(
            "stderr_overflow",
            "synthetic_rust_supervisor",
            ["forward_stderr", "project_mcp_response"],
            reap,
        ),
        _fault(
            "malformed_worker_response",
            "synthetic_rust_supervisor",
            ["project_mcp_response"],
            reap,
        ),
        _fault(
            "worker_timeout",
            "synthetic_rust_supervisor",
            ["project_success", "reuse_grant"],
            reap,
        ),
        _fault(
            "mcp_cancelled",
            "synthetic_rust_supervisor",
            ["leave_worker_running", "reuse_grant"],
            reap,
        ),
        _fault(
            "term_ignoring_descendant",
            "synthetic_rust_supervisor",
            ["release_host_lock_before_reap"],
            reap,
        ),
        _fault(
            "worker_exit_without_response",
            "synthetic_rust_supervisor",
            ["project_success"],
            ["wait_worker", "release_host_lock"],
        ),
        _fault(
            "inline_owner_signing_attempt",
            "owner_confirmation_broker",
            ["read_key", "issue_grant", "spawn_worker"],
        ),
        _fault(
            "caller_envelope_without_owner_confirmation",
            "owner_confirmation_broker",
            ["spawn_worker", "consume_nonce", "load_model"],
        ),
        _fault(
            "premature_mcp_registration",
            "mcp_registration_and_deployment_review",
            ["register_mcp_tool", "modify_toolset", "deploy_binary"],
        ),
    ]
    return rows


def _source_findings(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source_files = {
        name: {"path": str(relative), "sha256": _sha256_file(root / relative)}
        for name, relative in SOURCE_PATHS.items()
    }
    registry = (root / SOURCE_PATHS["mcp_registry"]).read_text(encoding="utf-8")
    story = (root / SOURCE_PATHS["story_preflight_mcp"]).read_text(
        encoding="utf-8"
    )
    server = (root / SOURCE_PATHS["mcp_server"]).read_text(encoding="utf-8")
    reaper = (root / SOURCE_PATHS["orphan_reaper"]).read_text(encoding="utf-8")
    cargo = (root / SOURCE_PATHS["bridge_cargo"]).read_text(encoding="utf-8")
    dependency_markers = {
        "libc": 'libc = "0.2"',
        "serde": "serde.workspace = true",
        "serde_json": "serde_json.workspace = true",
        "tokio": "tokio.workspace = true",
        "uuid": "uuid.workspace = true",
    }
    dependencies = sorted(
        name for name, marker in dependency_markers.items() if marker in cargo
    )
    findings = {
        "worker_target_absent": not (root / TARGET_PATHS["worker"]).exists(),
        "protocol_codec_target_absent": not (
            root / TARGET_PATHS["protocol_codec"]
        ).exists(),
        "supervisor_target_absent": not (
            root / TARGET_PATHS["supervisor"]
        ).exists(),
        "mcp_render_target_absent": not (
            root / TARGET_PATHS["mcp_render"]
        ).exists(),
        "story_command_render_registry_absent": '"story_command_render"'
        not in registry,
        "existing_story_preflight_registered": all(
            marker in registry
            for marker in (
                "use story::{StoryCommandPreflightTool, StoryMcpConfig};",
                "Arc::new(StoryCommandPreflightTool::new(config))",
            )
        )
        and '"story_command_preflight"' in story,
        "existing_mcp_cancellation_aborts_tool_future": all(
            marker in server
            for marker in (
                "notifications/cancelled",
                "h.abort();",
                "Err(e) if e.is_cancelled() => None",
            )
        ),
        "existing_owned_process_group_reaper_present": all(
            marker in reaper
            for marker in (
                "pub async fn reap_group(",
                "libc::SIGTERM",
                "libc::SIGKILL",
                "libc::setsid()",
            )
        ),
        "required_rust_dependencies_already_present": dependencies,
    }
    if dependencies != ["libc", "serde", "serde_json", "tokio", "uuid"]:
        raise ValueError("required Rust dependency baseline changed")
    if not all(
        findings[name]
        for name in (
            "worker_target_absent",
            "protocol_codec_target_absent",
            "supervisor_target_absent",
            "mcp_render_target_absent",
            "story_command_render_registry_absent",
            "existing_story_preflight_registered",
            "existing_mcp_cancellation_aborts_tool_future",
            "existing_owned_process_group_reaper_present",
        )
    ):
        raise ValueError("current Story runtime source boundary changed")
    return findings, source_files


def build_implementation_review(
    repo_root: Path,
    *,
    s620_path: Path,
) -> dict[str, Any]:
    """Review a staged implementation without creating any target surface."""

    root = Path(repo_root).resolve()
    s620_path = Path(s620_path)
    s620 = _read_json(s620_path)
    _validate_s620(s620, _read_json(root / S620_SCHEMA))
    findings, source_files = _source_findings(root)

    evidence = {
        "s620_contract": {
            "path": str(s620_path.relative_to(root)),
            "sha256": _sha256_file(s620_path),
            "contract_sha256": s620["contract_sha256"],
        },
        "s620_schema": {
            "path": str(S620_SCHEMA),
            "sha256": _sha256_file(root / S620_SCHEMA),
        },
        "source_files": source_files,
    }
    implementation_ladder = [
        {
            "id": "pure_protocol_codec",
            "objective": "strict request_response_validation_and_mcp_redaction",
            "process_spawn": False,
            "filesystem_write": False,
            "real_key_read": False,
            "real_model_load": False,
            "mcp_registration": False,
        },
        {
            "id": "synthetic_rust_supervisor",
            "objective": "host_lock_bounded_io_cancel_kill_and_reap_with_fake_workers",
            "process_spawn": True,
            "filesystem_write": "temporary_test_roots_only",
            "real_key_read": False,
            "real_model_load": False,
            "mcp_registration": False,
        },
        {
            "id": "private_fixture_worker",
            "objective": "compose_fixed_fixture_with_injected_fake_authority_and_runner",
            "process_spawn": "synthetic_integration_only",
            "filesystem_write": "temporary_test_roots_only",
            "real_key_read": False,
            "real_model_load": False,
            "mcp_registration": False,
        },
        {
            "id": "owner_confirmation_broker",
            "objective": "independent_owner_confirmation_and_short_lived_grant_issuance",
            "process_spawn": False,
            "filesystem_write": "separate_contract_required",
            "real_key_read": True,
            "real_model_load": False,
            "mcp_registration": False,
        },
        {
            "id": "mcp_registration_and_deployment_review",
            "objective": "default_off_niche_registration_and_current_client_adoption",
            "process_spawn": False,
            "filesystem_write": False,
            "real_key_read": False,
            "real_model_load": False,
            "mcp_registration": "review_only_until_owner_authorized",
        },
    ]
    selected_next_patch = {
        "stage": "pure_protocol_codec",
        "allowed_files": [
            "scripts/story_render_worker_protocol.py",
            "tests/test_story_render_worker_protocol.py",
            "docs/design/voice-scene/story_render_worker_request.schema.json",
            "docs/design/voice-scene/story_render_worker_response.schema.json",
        ],
        "modified_existing_files": [],
        "forbidden_files": [
            "crates/bridge/src/mcp_tools.rs",
            "crates/bridge/src/mcp_tools/story.rs",
            "crates/bridge/src/main.rs",
            "crates/bridge/src/mcp_tools/audio.rs",
            "crates/store",
            "/home/pallasting/.agent-bridge-secure",
        ],
        "imports_forbidden": [
            "subprocess",
            "sqlite3",
            "onnxruntime",
            "torch",
            "sounddevice",
        ],
        "filesystem_writes_allowed": False,
        "network_allowed": False,
        "environment_reads_allowed": False,
        "clock_reads_allowed": False,
        "randomness_allowed": False,
    }
    pure_protocol_codec = {
        "entrypoints": [
            "decode_request",
            "validate_worker_response",
            "encode_error_response",
            "project_mcp_response",
        ],
        "input_type": "bytes_and_s620_contract",
        "output_type": "validated_plain_data_or_typed_protocol_error",
        "authorization_work": "shape_and_binding_validation_only",
        "mac_verification": False,
        "nonce_consumption": False,
        "model_or_executor_import": False,
        "strict_json": {
            "duplicate_keys": "reject",
            "nonfinite_numbers": "reject",
            "trailing_data": "reject",
            "unknown_fields": "reject",
            "utf8_errors": "reject",
        },
        "size_limits_from_s620_only": True,
        "error_messages": "fixed_codes_no_input_echo",
    }
    synthetic_supervisor_plan = {
        "target": "crates/bridge/src/story_render_supervisor.rs",
        "ownership": "detached_cleanup_task_owns_child_and_lock",
        "cancel_path": (
            "drop_guard_signals_cleanup_task_which_terminates_group_and_waits"
        ),
        "kill_on_drop_alone_sufficient": False,
        "host_lock": "nonblocking_flock_held_by_cleanup_task",
        "process_identity": "setsid_leader_pid_equals_pgid_and_parent_death_sigkill",
        "termination": "sigterm_two_second_grace_sigkill_then_wait",
        "io": "concurrent_bounded_stdout_stderr_drain",
        "dependencies": ["libc", "serde", "serde_json", "tokio", "uuid"],
        "new_cargo_dependency_allowed": False,
        "test_workers": [
            "success",
            "malformed_output",
            "stdout_overflow",
            "stderr_overflow",
            "hang",
            "term_ignoring_descendant",
        ],
        "test_roots": "temporary_directories_only",
        "real_worker_allowed": False,
        "mcp_registration_in_stage": False,
    }
    owner_authority_boundary = {
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
    mcp_registration_boundary = {
        "tool_name": "story_command_render",
        "annotation_if_later_registered": "conservative_not_read_only",
        "default_exposed": False,
        "toolset": "codex-voice",
        "tier": "Niche",
        "enable_env": "AB_STORY_COMMAND_RENDER_ENABLE",
        "register_in_s621": False,
        "add_to_codex_voice_extras_in_s621": False,
        "registration_requires": [
            "pure_codec_verified",
            "synthetic_supervisor_verified",
            "private_fixture_worker_verified",
            "independent_owner_confirmation_broker_verified",
            "redacted_projection_verified",
            "deployment_review_owner_authorized",
        ],
    }
    runtime_effects = {
        "created_protocol_codec": False,
        "created_runtime_worker": False,
        "created_supervisor": False,
        "created_lock_file": False,
        "created_output_root": False,
        "modified_rust_registry": False,
        "registered_mcp_tool": False,
        "issued_owner_grant": False,
        "read_authority_key": False,
        "consumed_nonce": False,
        "spawned_worker": False,
        "loaded_model": False,
        "executed_onnx": False,
        "rendered_audio": False,
        "played_audio": False,
        "recorded_audio": False,
        "wrote_cache": False,
        "wrote_memory": False,
        "modified_configuration": False,
        "deployed_binary": False,
    }
    blockers = [
        "pure_protocol_codec_absent",
        "runtime_request_response_schemas_absent",
        "synthetic_rust_supervisor_absent",
        "private_fixture_worker_absent",
        "independent_owner_confirmation_broker_undecided",
        "story_command_render_mcp_surface_absent",
    ]
    bound = {
        "evidence": evidence,
        "current_source_findings": findings,
        "implementation_ladder": implementation_ladder,
        "selected_next_patch": selected_next_patch,
        "pure_protocol_codec": pure_protocol_codec,
        "synthetic_supervisor_plan": synthetic_supervisor_plan,
        "owner_authority_boundary": owner_authority_boundary,
        "mcp_registration_boundary": mcp_registration_boundary,
        "fault_matrix": _fault_matrix(),
        "blockers": blockers,
        "implementation_authorized": False,
        "execution_authorized": False,
        "deployment_authorized": False,
        "runtime_effects": runtime_effects,
    }
    return {
        "schema": "agent_bridge.story_render_one_shot_worker_implementation_review.v1",
        "status": "story_render_one_shot_worker_implementation_reviewable",
        "decision": "pure_protocol_then_synthetic_supervisor_real_authority_deferred",
        **bound,
        "review_sha256": _digest(bound),
        "claims": {
            "s620_contract_hash_bound": True,
            "current_runtime_targets_absent": True,
            "staged_implementation_selected": True,
            "pure_codec_patch_reviewed": True,
            "real_owner_authority_deferred": True,
            "worker_implemented": False,
            "supervisor_implemented": False,
            "mcp_tool_registered": False,
            "runtime_enabled": False,
        },
        "next_gate": "story_render_worker_protocol_codec_implementation",
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = build_implementation_review(
        root,
        s620_path=root
        / "docs/design/voice-scene/s620_story_render_one_shot_worker_protocol_contract.json",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
