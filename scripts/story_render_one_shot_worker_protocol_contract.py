#!/usr/bin/env python3
"""Build the non-actuating S620 one-shot Story render worker protocol."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


VOICE_SCENE = Path("docs/design/voice-scene")
S619_SCHEMA = VOICE_SCENE / "story_render_runtime_admission_review.schema.json"
S602_PATH = VOICE_SCENE / "s602_story_fixture_mcp_preflight_receipt.json"
S604_PATH = VOICE_SCENE / "s604_story_bounded_render_execution_contract.json"
S608_PATH = VOICE_SCENE / "s608_story_executor_authority_model_nonce_contract.json"
S614_PATH = (
    VOICE_SCENE / "s614_story_render_secure_configuration_installation_result.json"
)


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


def _validate_s619(value: dict[str, Any], schema: dict[str, Any]) -> None:
    selected = value.get("selected_architecture", {})
    decision = value.get("decision", {})
    if (
        value.get("status") != "story_render_runtime_admission_review_complete"
        or decision.get("runtime_admitted") is not False
        or decision.get("deployment_admitted") is not False
        or selected.get("pattern") != "one_shot_supervised_python_worker"
        or selected.get("default_exposed") is not False
        or selected.get("enable_env") != "AB_STORY_COMMAND_RENDER_ENABLE"
        or selected.get("concurrency")
        != {"max_active": 1, "when_busy": "reject_without_queue"}
        or selected.get("cancellation", {}).get("hard_deadline_seconds") != 300
        or selected.get("authorization", {}).get("key_material_enters_mcp_process")
        is not False
        or selected.get("pilot_scope", {}).get("accepted_preflight")
        != "fixed_s602_fixture_only"
        or selected.get("pilot_scope", {}).get("arbitrary_novel_paths") is not False
        or selected.get("pilot_scope", {}).get("playback") is not False
        or selected.get("pilot_scope", {}).get("recording") is not False
        or selected.get("pilot_scope", {}).get("memory_write") is not False
        or value.get("execution_authorized") is not False
        or value.get("deployment_authorized") is not False
        or value.get("next_gate")
        != "story_render_one_shot_worker_protocol_contract"
        or list(Draft202012Validator(schema).iter_errors(value))
    ):
        raise ValueError("S619 runtime admission authority invalid")


def _validate_fixture(
    preflight: dict[str, Any], execution_contract: dict[str, Any]
) -> None:
    if (
        preflight.get("status") != "story_fixture_mcp_preflight_verified"
        or preflight.get("request", {}).get("start")
        != {"kind": "chapter", "chapter": 2}
        or preflight.get("request", {}).get("dry_run") is not True
        or preflight.get("result", {}).get("execution_authorized") is not False
        or preflight.get("selection", {}).get("selected_segments") != 3
        or any(
            preflight.get("runtime_effects", {}).get(name) is not False
            for name in (
                "loaded_model",
                "executed_onnx",
                "rendered_audio",
                "played_audio",
                "wrote_memory",
                "wrote_cache",
            )
        )
    ):
        raise ValueError("S602 fixed fixture authority invalid")
    if (
        execution_contract.get("status")
        != "story_bounded_render_execution_contract_reviewable"
        or execution_contract.get("execution_authorized") is not False
        or any(execution_contract.get("runtime_effects", {}).values())
        or execution_contract.get("evidence", {}).get("preflight_sha256")
        != preflight.get("result", {}).get("preflight_sha256")
        or execution_contract.get("evidence", {}).get("chapter") != 2
        or execution_contract.get("bounds", {}).get("network_allowed") is not False
        or execution_contract.get("bounds", {}).get("gpu_allowed") is not False
    ):
        raise ValueError("S604 fixture execution contract invalid")


def _validate_authority_contract(value: dict[str, Any]) -> None:
    proof = value.get("authority_proof", {})
    if (
        value.get("status")
        != "story_executor_authority_model_nonce_contract_reviewable"
        or proof.get("algorithm") != "hmac-sha256"
        or proof.get("canonicalization") != "utf8-jcs-rfc8785"
        or proof.get("proof_field") != "mac_sha256"
        or proof.get("secret_material_in_envelope") is not False
        or proof.get("constant_time_comparison_required") is not True
        or value.get("execution_authorized") is not False
    ):
        raise ValueError("S608 authority contract invalid")


def _validate_installation(value: dict[str, Any]) -> None:
    installation = value.get("installation", {})
    if (
        value.get("status") != "story_render_secure_configuration_installed"
        or value.get("decision")
        != "configuration_installed_executor_invocation_blocked"
        or installation.get("runtime_directory")
        != "/home/pallasting/.agent-bridge-secure/story-render"
        or installation.get("key_bundle")
        != (
            "/home/pallasting/.agent-bridge-secure/story-render/"
            "authority-keys.v1.json"
        )
        or installation.get("active_key_id") != "story-render-owner-v1"
        or installation.get("runtime_directory_mode") != "0700"
        or installation.get("key_bundle_mode") != "0600"
        or installation.get("key_material_disclosed") is not False
        or value.get("execution_authorized") is not False
    ):
        raise ValueError("S614 installed custody authority invalid")


def build_protocol_contract(
    repo_root: Path,
    *,
    s619_path: Path,
) -> dict[str, Any]:
    """Bind a strict worker protocol without spawning or changing runtime."""

    root = Path(repo_root).resolve()
    s619_path = Path(s619_path)
    s619 = _read_json(s619_path)
    _validate_s619(s619, _read_json(root / S619_SCHEMA))

    s602_path = root / S602_PATH
    s604_path = root / S604_PATH
    s608_path = root / S608_PATH
    s614_path = root / S614_PATH
    s602 = _read_json(s602_path)
    s604 = _read_json(s604_path)
    s608 = _read_json(s608_path)
    s614 = _read_json(s614_path)
    _validate_fixture(s602, s604)
    _validate_authority_contract(s608)
    _validate_installation(s614)

    fixture = {
        "preflight": "fixed_s602_fixture_only",
        "chapter": 2,
        "preflight_sha256": s602["result"]["preflight_sha256"],
        "execution_contract_sha256": s604["contract_sha256"],
    }
    evidence = {
        "s619_runtime_admission": {
            "path": str(s619_path.relative_to(root)),
            "sha256": _sha256_file(s619_path),
            "selected_pattern": s619["selected_architecture"]["pattern"],
        },
        "s602_fixed_preflight": {
            "path": str(S602_PATH),
            "sha256": _sha256_file(s602_path),
            "source_sha256": s602["request"]["source_sha256"],
            "preflight_sha256": s602["result"]["preflight_sha256"],
        },
        "s604_fixture_execution_contract": {
            "path": str(S604_PATH),
            "sha256": _sha256_file(s604_path),
            "contract_sha256": s604["contract_sha256"],
            "usage": "fixture_and_model_provenance_only",
            "legacy_fuse_output_root_admitted": False,
        },
        "s608_authority_contract": {
            "path": str(S608_PATH),
            "sha256": _sha256_file(s608_path),
            "contract_sha256": s608["contract_sha256"],
            "domain_separator": s608["authority_proof"]["domain_separator"],
        },
        "s614_installed_custody": {
            "path": str(S614_PATH),
            "sha256": _sha256_file(s614_path),
            "status": s614["status"],
            "active_key_id": s614["installation"]["active_key_id"],
            "key_material_disclosed": False,
        },
    }
    activation = {
        "tool_name": "story_command_render",
        "tier": "Niche",
        "toolset": "codex-voice",
        "default_exposed": False,
        "enable_env": "AB_STORY_COMMAND_RENDER_ENABLE",
        "enable_required_value": "1",
        "enabled_now": False,
    }
    protocol = {
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
    request = {
        "exact_fields": [
            "protocol",
            "request_id",
            "fixture",
            "authorization",
        ],
        "protocol": "agent_bridge.story-render-worker.v1",
        "request_id": "supervisor_generated_32_lowercase_hex",
        "fixture": fixture,
        "authorization": {
            "shape": "s608_closed_hmac_sha256_envelope",
            "exact_fields": [
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
            ],
            "action": "render",
            "maximum_ttl_seconds": 300,
            "contract_sha256_binding": "s620_protocol_contract_sha256",
            "preflight_sha256_binding": "fixed_s602_preflight_sha256",
            "output_directory_policy": (
                "one_private_root_child_named_by_supervisor_render_id"
            ),
            "installed_key_read_by": "one_shot_worker_only",
            "key_material_enters_mcp_process": False,
            "nonce_consumed_before_output_creation": True,
            "persisted_or_logged_by_supervisor": False,
        },
        "caller_supplied_text_allowed": False,
        "caller_supplied_paths_allowed": False,
    }
    host_admission = {
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
    supervisor = {
        "spawn": {
            "shell": False,
            "absolute_executable_and_script": True,
            "new_process_group": True,
            "worker_subprocess_spawn_allowed": False,
            "stdin": "pipe_write_once_then_close",
            "stdout": "bounded_pipe",
            "stderr": "bounded_redacted_pipe",
        },
        "io_collection": "drain_stdout_and_stderr_concurrently",
        "termination": {
            "deadline_seconds": 300,
            "on_mcp_cancel": "terminate_process_group_then_reap",
            "on_protocol_limit": "terminate_process_group_then_reap",
            "on_parent_death": "worker_receives_sigkill",
            "grace_seconds": 2,
            "escalation": "sigterm_then_sigkill",
            "wait_required_on_every_spawned_path": True,
        },
    }
    environment = {
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
    output_custody = {
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
    response = {
        "success_exact_fields": [
            "protocol",
            "request_id",
            "status",
            "render_id",
            "segment_count",
            "assembly",
            "playback_authorized",
            "memory_authorized",
        ],
        "assembly_exact_fields": [
            "sha256",
            "sample_rate_hz",
            "channels",
            "frames",
            "duration_seconds",
        ],
        "error_exact_fields": [
            "protocol",
            "request_id",
            "status",
            "code",
            "retryable",
        ],
        "error_codes": [
            "invalid_request",
            "authority_rejected",
            "nonce_reused",
            "custody_rejected",
            "model_rejected",
            "render_failed",
            "internal_failure",
        ],
        "forbidden_fields": [
            "authorization_id",
            "mac_sha256",
            "single_use_nonce",
            "key_material",
            "output_directory",
            "absolute_path",
            "exception",
            "traceback",
        ],
        "mcp_projection_allowlist": [
            "status",
            "render_id",
            "segment_count",
            "assembly",
            "playback_authorized",
            "memory_authorized",
        ],
        "playback_authorized": False,
        "memory_authorized": False,
    }
    lifecycle = [
        "activation_gate_checked",
        "fixed_fixture_call_validated",
        "host_lock_try_acquired",
        "render_identity_generated",
        "explicit_owner_grant_issued",
        "worker_request_validated",
        "one_shot_worker_spawned",
        "request_written_and_stdin_closed",
        "bounded_streams_drained",
        "worker_reaped",
        "response_schema_validated",
        "redacted_mcp_projection_emitted",
        "host_lock_released",
    ]
    failure_policy = {
        "disabled": "reject_without_grant_lock_or_spawn",
        "busy": "reject_without_queue_spawn_or_nonce_consumption",
        "malformed_request": "reject_before_spawn",
        "owner_grant_declined": "release_lock_without_spawn",
        "spawn_failure": "discard_grant_reference_release_lock_and_require_new_grant",
        "worker_authority_rejection": "reap_and_return_redacted_error",
        "cancel_or_deadline": "terminate_group_reap_and_never_reuse_grant",
        "output_or_protocol_overflow": "terminate_group_reap_and_redact",
        "post_nonce_failure": "new_owner_grant_required_for_retry",
    }
    runtime_effects = {
        "created_lock_file": False,
        "created_output_root": False,
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
    bound = {
        "evidence": evidence,
        "activation": activation,
        "protocol": protocol,
        "request": request,
        "host_admission": host_admission,
        "supervisor": supervisor,
        "environment": environment,
        "output_custody": output_custody,
        "response": response,
        "lifecycle": lifecycle,
        "failure_policy": failure_policy,
        "implementation_authorized": False,
        "execution_authorized": False,
        "deployment_authorized": False,
        "runtime_effects": runtime_effects,
    }
    return {
        "schema": "agent_bridge.story_render_one_shot_worker_protocol.v1",
        "status": "story_render_one_shot_worker_protocol_reviewable",
        "decision": "static_protocol_complete_implementation_and_runtime_blocked",
        **bound,
        "contract_sha256": _digest(bound),
        "claims": {
            "s619_architecture_hash_bound": True,
            "fixed_fixture_only": True,
            "host_wide_single_job_admission_defined": True,
            "owned_worker_reaping_defined": True,
            "private_output_custody_defined": True,
            "redacted_projection_defined": True,
            "worker_implemented": False,
            "supervisor_implemented": False,
            "owner_grant_broker_implemented": False,
            "mcp_tool_registered": False,
            "runtime_enabled": False,
        },
        "implementation_blockers": [
            "owner_grant_broker_absent",
            "host_lock_and_supervisor_absent",
            "one_shot_worker_absent",
            "private_output_contract_not_implemented",
            "redacted_mcp_projection_absent",
            "story_command_render_not_registered",
        ],
        "next_gate": "story_render_one_shot_worker_protocol_implementation_review",
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = build_protocol_contract(
        root,
        s619_path=root
        / "docs/design/voice-scene/s619_story_render_runtime_admission_review.json",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
