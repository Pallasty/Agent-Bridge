#!/usr/bin/env python3
"""Statically review the isolated Story renderer without importing or running it."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_EXECUTOR_ARGUMENTS = [
    "contract",
    "authorization",
    "request",
    "now",
    "authority_verifier",
    "model_verifier",
    "nonce_store_path",
]


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


def _validate_prior_review(review: dict[str, Any], executor_path: Path) -> None:
    if (
        review.get("schema")
        != "agent_bridge.story_bounded_render_executor_implementation_review.v1"
        or review.get("status")
        != "story_bounded_render_executor_implementation_reviewable"
        or review.get("decision")
        != "isolated_python_executor_source_only_not_authorized"
        or review.get("implementation_authorized") is not False
        or review.get("execution_authorized") is not False
        or any(review.get("runtime_effects", {}).values())
        or review.get("next_gate")
        != "owner_authorized_isolated_bounded_render_executor_implementation"
    ):
        raise ValueError("S605 authority boundary invalid")
    bound = {
        key: review[key]
        for key in (
            "evidence",
            "surface",
            "proposed_patch",
            "authorization_envelope",
            "output_custody",
            "playback_boundary",
            "memory_boundary",
            "fault_matrix",
            "blockers",
            "implementation_authorized",
            "execution_authorized",
            "runtime_effects",
        )
    }
    if _digest(bound) != review.get("review_sha256"):
        raise ValueError("S605 review SHA-256 invalid")
    if review.get("surface", {}).get("target") != str(executor_path.resolve()):
        raise ValueError("S605 executor target mismatch")
    if str(executor_path.resolve()) not in review.get("proposed_patch", {}).get(
        "allowed_files", []
    ):
        raise ValueError("S605 executor file not allowed")


def _validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("schema")
        != "agent_bridge.story_bounded_render_execution_contract.v1"
        or contract.get("execution_authorized") is not False
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


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise ValueError(f"required executor function missing:{name}")
    return matches[0]


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _execution_call_order(function: ast.FunctionDef) -> list[str]:
    wanted = {
        "_validate_contract": "validate_contract",
        "_validate_request": "validate_request",
        "_validate_authorization": "validate_authorization",
        "model_verifier": "model_verifier",
        "_consume_nonce": "consume_nonce",
        "mkdir": "create_output_directory",
        "_load_runner": "load_runner",
    }
    found = []
    for node in sorted(
        (item for item in ast.walk(function) if isinstance(item, ast.Call)),
        key=lambda item: (item.lineno, item.col_offset),
    ):
        name = _call_name(node)
        if name in wanted and wanted[name] not in found:
            found.append(wanted[name])
    return found


def _import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def _source_analysis(source: str, tree: ast.Module) -> tuple[dict[str, Any], dict[str, Any]]:
    execute = _function(tree, "execute_bounded_render")
    arguments = [arg.arg for arg in execute.args.kwonlyargs]
    if "runner_override" in source:
        raise ValueError("runner override forbidden")
    if arguments != EXPECTED_EXECUTOR_ARGUMENTS:
        raise ValueError("executor signature boundary invalid")
    order = _execution_call_order(execute)
    expected_order = [
        "validate_contract",
        "validate_request",
        "validate_authorization",
        "model_verifier",
        "consume_nonce",
        "create_output_directory",
        "load_runner",
    ]
    if order != expected_order:
        raise ValueError("executor call order invalid")
    imports = _import_roots(tree)
    forbidden_imports = {
        "subprocess",
        "socket",
        "requests",
        "urllib",
        "sounddevice",
        "pyaudio",
    }
    if imports & forbidden_imports:
        raise ValueError("forbidden runtime integration imported")
    if any(
        marker in source
        for marker in ("pw-play", "present_voice", "mcp_tools", "Command::new")
    ):
        raise ValueError("forbidden playback or MCP integration present")
    function_names = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    has_cli = "main" in function_names or 'if __name__ == "__main__"' in source
    source_record = {
        "line_count": len(source.splitlines()),
        "function_count": len(function_names),
        "execute_keyword_only_arguments": arguments,
        "has_cli_entrypoint": has_cli,
        "has_mcp_or_rust_wiring": False,
        "stdlib_import_roots": sorted(imports),
    }
    boundaries = {
        "external_authority_verifier_required": "authority_verifier" in arguments,
        "external_model_bundle_verifier_required": "model_verifier" in arguments,
        "authority_before_model_admission": order.index("validate_authorization")
        < order.index("model_verifier"),
        "nonce_before_output_directory": order.index("consume_nonce")
        < order.index("create_output_directory"),
        "nonce_before_runner_load": order.index("consume_nonce")
        < order.index("load_runner"),
        "single_use_nonce_persistent_sqlite": (
            "sqlite3" in imports
            and "consumed_nonces" in source
            and "begin immediate" in source
        ),
        "existing_output_rejected": "output target exists" in source,
        "atomic_segment_and_receipt_finalization": source.count("os.replace(") >= 3,
        "cleanup_scoped_to_owned_paths": (
            "_cleanup_owned" in function_names
            and "path.unlink(missing_ok=True)" in source
            and "output.rmdir()" in source
        ),
        "machine_pcm_and_non_silence_gate": (
            "_probe_wav" in function_names
            and "audio is silent" in source
            and "sample_rate != 24000" in source
        ),
        "playback_absent": "pw-play" not in source and "present_voice" not in source,
        "recording_absent": not bool(imports & {"sounddevice", "pyaudio"}),
        "memory_integration_absent": (
            "mcp_tools" not in source and "write_memory" not in source
        ),
        "runner_override_absent": "runner_override" not in source,
        "shell_and_subprocess_absent": "subprocess" not in imports,
    }
    if has_cli or not all(boundaries.values()):
        raise ValueError("executor source boundary incomplete")
    return source_record, boundaries


def build_source_review(
    *,
    executor_path: Path,
    executor_test_path: Path,
    implementation_review_path: Path,
    execution_contract_path: Path,
    trusted_runner_path: Path,
) -> dict[str, Any]:
    """Build a deterministic, static S607 source-adoption review."""

    for path, label in (
        (executor_path, "executor"),
        (executor_test_path, "executor test"),
        (implementation_review_path, "S605 review"),
        (execution_contract_path, "S604 contract"),
        (trusted_runner_path, "trusted runner"),
    ):
        if not path.is_file():
            raise ValueError(f"{label} missing")
    prior = _read_json(implementation_review_path)
    contract = _read_json(execution_contract_path)
    _validate_prior_review(prior, executor_path)
    _validate_contract(contract)
    if _sha256_file(trusted_runner_path) != prior.get("evidence", {}).get(
        "trusted_runner_sha256"
    ):
        raise ValueError("trusted runner SHA-256 mismatch")

    source = executor_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    source_record, boundaries = _source_analysis(source, tree)
    test_source = executor_test_path.read_text(encoding="utf-8")
    test_tree = ast.parse(test_source)
    test_names = sorted(
        node.name
        for node in test_tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )
    required_tests = {
        "test_executor_requires_external_authority_verification",
        "test_executor_requires_external_model_bundle_verification",
        "test_authority_is_verified_before_model_bundle_admission",
        "test_consumed_nonce_cannot_be_retried_after_render_failure",
        "test_machine_gate_rejects_silent_audio_and_cleans_owned_output",
        "test_executor_rejects_existing_or_escaping_output_directory",
        "test_source_has_no_shell_playback_or_memory_integration",
    }
    if not required_tests.issubset(test_names):
        raise ValueError("executor negative-control coverage incomplete")

    review_builder = Path(__file__).resolve()
    source_record = {
        "review_builder_path": str(review_builder),
        "review_builder_sha256": _sha256_file(review_builder),
        "executor_path": str(executor_path.resolve()),
        "executor_sha256": _sha256_file(executor_path),
        "executor_test_path": str(executor_test_path.resolve()),
        "executor_test_sha256": _sha256_file(executor_test_path),
        "trusted_runner_path": str(trusted_runner_path.resolve()),
        "trusted_runner_sha256": _sha256_file(trusted_runner_path),
        **source_record,
    }
    evidence = {
        "s604_contract_file_sha256": _sha256_file(execution_contract_path),
        "s604_contract_sha256": contract["contract_sha256"],
        "s605_review_file_sha256": _sha256_file(implementation_review_path),
        "s605_review_sha256": prior["review_sha256"],
        "s605_executor_target_absent_was_historical_precondition": True,
        "executor_static_test_count": len(test_names),
        "required_negative_controls_present": True,
    }
    blockers = [
        "authority_verifier_implementation_external",
        "model_bundle_verifier_implementation_external",
        "model_directory_manifest_not_bound_by_s604_contract",
        "nonce_store_path_not_contract_bound_or_deployed",
        "secure_runtime_configuration_not_installed",
        "bounded_render_receipt_schema_not_defined",
    ]
    runtime_effects = {
        "imported_executor": False,
        "called_executor": False,
        "created_nonce_store": False,
        "created_output_directory": False,
        "loaded_model": False,
        "executed_onnx": False,
        "rendered_audio": False,
        "played_audio": False,
        "recorded_audio": False,
        "wrote_memory": False,
    }
    bound = {
        "source": source_record,
        "evidence": evidence,
        "call_order": _execution_call_order(_function(tree, "execute_bounded_render")),
        "boundaries": boundaries,
        "blockers": blockers,
        "implementation_present": True,
        "deployment_authorized": False,
        "execution_authorized": False,
        "runtime_effects": runtime_effects,
    }
    return {
        "schema": "agent_bridge.story_bounded_render_executor_source_review.v1",
        "status": "story_bounded_render_executor_source_reviewable",
        "decision": "source_implementation_accepted_runtime_blocked",
        **bound,
        "review_sha256": _digest(bound),
        "claims": {
            "source_implementation_present": True,
            "authorization_and_model_hooks_present": True,
            "single_use_and_output_custody_present": True,
            "machine_audio_gate_present": True,
            "playback_recording_and_memory_closed": True,
            "real_model_executed": False,
            "runtime_execution_admitted": False,
        },
        "next_gate": "story_executor_authority_model_nonce_contract",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executor", type=Path, required=True)
    parser.add_argument("--executor-test", type=Path, required=True)
    parser.add_argument("--implementation-review", type=Path, required=True)
    parser.add_argument("--execution-contract", type=Path, required=True)
    parser.add_argument("--trusted-runner", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = build_source_review(
        executor_path=args.executor,
        executor_test_path=args.executor_test,
        implementation_review_path=args.implementation_review,
        execution_contract_path=args.execution_contract,
        trusted_runner_path=args.trusted_runner,
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
