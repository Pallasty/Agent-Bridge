#!/usr/bin/env python3
"""Review a minimal bounded Story executor without implementing or running it."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


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


def _validate_contract(
    contract: dict[str, Any],
    *,
    contract_builder_path: Path,
    trusted_runner_path: Path,
) -> None:
    if (
        contract.get("schema")
        != "agent_bridge.story_bounded_render_execution_contract.v1"
        or contract.get("status")
        != "story_bounded_render_execution_contract_reviewable"
        or contract.get("execution_authorized") is not False
        or contract.get("claims", {}).get("executor_implemented") is not False
        or contract.get("claims", {}).get("runtime_execution_admitted") is not False
        or contract.get("next_gate")
        != "story_bounded_render_executor_implementation_review"
        or any(contract.get("runtime_effects", {}).values())
    ):
        raise ValueError("S604 execution boundary invalid")
    bound = {
        key: contract[key]
        for key in (
            "evidence",
            "bounds",
            "authority",
            "state_machine",
            "execution_authorized",
            "runtime_effects",
        )
    }
    if _digest(bound) != contract.get("contract_sha256"):
        raise ValueError("S604 contract SHA-256 invalid")
    evidence = contract["evidence"]
    if _sha256_file(contract_builder_path) != evidence.get(
        "contract_builder_sha256"
    ):
        raise ValueError("contract builder SHA-256 mismatch")
    if _sha256_file(trusted_runner_path) != evidence.get("trusted_runner_sha256"):
        raise ValueError("trusted runner SHA-256 mismatch")


def _fault(
    code: str, phase: str, effects_forbidden: list[str]
) -> dict[str, Any]:
    return {
        "code": code,
        "phase": phase,
        "disposition": "fail_closed",
        "effects_forbidden": effects_forbidden,
    }


def _fault_matrix() -> list[dict[str, Any]]:
    no_runtime = ["create_output_directory", "load_model", "render_audio"]
    return [
        _fault("missing_render_grant", "authorization", no_runtime),
        _fault("expired_render_grant", "authorization", no_runtime),
        _fault("reused_single_use_nonce", "authorization", no_runtime),
        _fault("contract_sha256_mismatch", "authorization", no_runtime),
        _fault("preflight_sha256_mismatch", "authorization", no_runtime),
        _fault("output_directory_mismatch", "authorization", no_runtime),
        _fault("output_target_exists", "output_custody", no_runtime),
        _fault("trusted_runner_hash_mismatch", "source_admission", no_runtime),
        _fault("model_inference_hash_mismatch", "model_admission", no_runtime),
        _fault(
            "segment_limit_exceeded",
            "request_validation",
            ["load_model", "render_audio"],
        ),
        _fault(
            "recording_requested",
            "request_validation",
            ["record_audio", "load_model", "render_audio"],
        ),
        _fault(
            "memory_write_requested",
            "request_validation",
            ["write_memory", "load_model", "render_audio"],
        ),
        _fault(
            "segment_render_failed",
            "render",
            ["finalize_assembly", "play_audio", "write_memory"],
        ),
        _fault(
            "natural_eos_not_reached",
            "render",
            ["finalize_assembly", "play_audio", "write_memory"],
        ),
        _fault(
            "machine_audio_gate_failed",
            "machine_gate",
            ["finalize_assembly", "play_audio", "write_memory"],
        ),
        _fault(
            "playback_grant_missing",
            "post_render",
            ["play_audio", "write_memory"],
        ),
    ]


def build_implementation_review(
    *,
    execution_contract_path: Path,
    contract_builder_path: Path,
    trusted_runner_path: Path,
    preflight_adapter_path: Path,
    executor_target_path: Path,
) -> dict[str, Any]:
    """Produce a deterministic source-only implementation review."""

    contract = _read_json(execution_contract_path)
    for path, label in (
        (contract_builder_path, "contract builder"),
        (trusted_runner_path, "trusted runner"),
        (preflight_adapter_path, "preflight adapter"),
    ):
        if not path.is_file():
            raise ValueError(f"{label} missing")
    _validate_contract(
        contract,
        contract_builder_path=contract_builder_path,
        trusted_runner_path=trusted_runner_path,
    )
    if executor_target_path.exists():
        raise ValueError("executor target already exists")

    review_builder_path = Path(__file__).resolve()
    evidence = {
        "review_builder_path": str(review_builder_path),
        "review_builder_sha256": _sha256_file(review_builder_path),
        "execution_contract_path": str(execution_contract_path.resolve()),
        "execution_contract_file_sha256": _sha256_file(execution_contract_path),
        "execution_contract_sha256": contract["contract_sha256"],
        "contract_builder_path": str(contract_builder_path.resolve()),
        "contract_builder_sha256": _sha256_file(contract_builder_path),
        "trusted_runner_path": str(trusted_runner_path.resolve()),
        "trusted_runner_sha256": _sha256_file(trusted_runner_path),
        "preflight_adapter_path": str(preflight_adapter_path.resolve()),
        "preflight_adapter_sha256": _sha256_file(preflight_adapter_path),
        "executor_target_absent": True,
    }
    surface = {
        "kind": "isolated_python_module",
        "target": str(executor_target_path.resolve()),
        "mcp_tool_registered": False,
        "rust_registry_modified": False,
        "subprocess_or_shell_allowed": False,
        "direct_runner_call_only": True,
    }
    proposed_patch = {
        "allowed_files": [
            str(executor_target_path.resolve()),
            str(
                executor_target_path.resolve().parents[1]
                / "tests"
                / "test_story_bounded_render_executor.py"
            ),
        ],
        "modified_existing_files": [],
        "forbidden_files": [
            "crates/bridge/src/mcp_tools.rs",
            "crates/bridge/src/mcp_tools/audio.rs",
            "crates/bridge/src/main.rs",
        ],
    }
    authorization_envelope = {
        "required_fields": [
            "authorization_id",
            "contract_sha256",
            "preflight_sha256",
            "output_directory",
            "action",
            "issued_at",
            "expires_at",
            "single_use_nonce",
        ],
        "action": "render",
        "single_use": True,
        "validate_before_output_directory": True,
        "persistent_nonce_store_required_before_runtime": True,
    }
    output_custody = {
        "root_from_contract_only": True,
        "dedicated_new_directory_required": True,
        "existing_target_rejected": True,
        "temporary_files_scoped_to_new_directory": True,
        "atomic_finalization_required": True,
        "cleanup_only_executor_created_files": True,
    }
    playback_boundary = {
        "executor_may_play": False,
        "separate_playback_component_required": True,
        "machine_gate_receipt_required": True,
        "separate_single_use_grant_required": True,
    }
    memory_boundary = {
        "executor_may_write_memory": False,
        "interaction_log_component_present": False,
        "future_memory_authority_separate": True,
    }
    blockers = [
        "render_authorization_envelope_verifier_not_implemented",
        "persistent_single_use_nonce_store_not_implemented",
        "atomic_output_custody_not_implemented",
        "machine_audio_gate_receipt_compiler_not_implemented",
        "executor_source_not_implemented",
    ]
    runtime_effects = {
        "created_executor_source": False,
        "modified_rust_registry": False,
        "registered_mcp_tool": False,
        "created_output_directory": False,
        "loaded_model": False,
        "executed_onnx": False,
        "rendered_audio": False,
        "played_audio": False,
        "recorded_audio": False,
        "wrote_cache": False,
        "wrote_memory": False,
    }
    bound = {
        "evidence": evidence,
        "surface": surface,
        "proposed_patch": proposed_patch,
        "authorization_envelope": authorization_envelope,
        "output_custody": output_custody,
        "playback_boundary": playback_boundary,
        "memory_boundary": memory_boundary,
        "fault_matrix": _fault_matrix(),
        "blockers": blockers,
        "implementation_authorized": False,
        "execution_authorized": False,
        "runtime_effects": runtime_effects,
    }
    return {
        "schema": (
            "agent_bridge.story_bounded_render_executor_implementation_review.v1"
        ),
        "status": "story_bounded_render_executor_implementation_reviewable",
        "decision": "isolated_python_executor_source_only_not_authorized",
        **bound,
        "review_sha256": _digest(bound),
        "claims": {
            "minimal_source_surface_selected": True,
            "fault_matrix_complete_for_pilot": True,
            "runtime_authorities_separated": True,
            "executor_implemented": False,
            "runtime_execution_admitted": False,
        },
        "next_gate": (
            "owner_authorized_isolated_bounded_render_executor_implementation"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-contract", type=Path, required=True)
    parser.add_argument("--contract-builder", type=Path, required=True)
    parser.add_argument("--trusted-runner", type=Path, required=True)
    parser.add_argument("--preflight-adapter", type=Path, required=True)
    parser.add_argument("--executor-target", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = build_implementation_review(
        execution_contract_path=args.execution_contract,
        contract_builder_path=args.contract_builder,
        trusted_runner_path=args.trusted_runner,
        preflight_adapter_path=args.preflight_adapter,
        executor_target_path=args.executor_target,
    )
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
