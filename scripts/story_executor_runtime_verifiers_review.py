#!/usr/bin/env python3
"""Statically review S609 verifier source without importing it."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def _validate_s608(contract: dict[str, Any]) -> None:
    bound = {key: contract[key] for key in (
        "evidence", "authority_proof", "model_bundle", "nonce_store",
        "receipt_schema", "blockers", "execution_authorized", "runtime_effects")}
    if (contract.get("schema") != "agent_bridge.story_executor_authority_model_nonce_contract.v1"
            or contract.get("next_gate")
            != "story_executor_authority_model_nonce_verifier_implementation_review"
            or contract.get("execution_authorized") is not False
            or any(contract.get("runtime_effects", {}).values())
            or _digest(bound) != contract.get("contract_sha256")):
        raise ValueError("S608 contract invalid")


def _imports(tree: ast.AST) -> set[str]:
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module.split(".", 1)[0])
    return result


def build_review(*, verifier_path: Path, verifier_test_path: Path,
                 contract_path: Path) -> dict[str, Any]:
    for path in (verifier_path, verifier_test_path, contract_path):
        if not path.is_file():
            raise ValueError(f"required source missing:{path}")
    contract = _read(contract_path)
    _validate_s608(contract)
    source = verifier_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = _imports(tree)
    forbidden = {"story_bounded_render_executor", "sqlite3", "onnxruntime", "subprocess", "socket"}
    if imports & forbidden:
        raise ValueError("forbidden runtime import present")
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    required = {"canonical_authorization_message", "build_authority_verifier",
                "build_model_verifier", "fixed_nonce_store_path"}
    if not required.issubset(functions):
        raise ValueError("required verifier implementation missing")
    test_tree = ast.parse(verifier_test_path.read_text(encoding="utf-8"))
    tests = sorted(node.name for node in test_tree.body
                   if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
    required_tests = {
        "test_authority_verifier_accepts_only_exact_signed_executor_view",
        "test_authority_verifier_rejects_mac_key_and_envelope_drift",
        "test_model_verifier_stream_hashes_exact_bound_bundle",
        "test_model_verifier_rejects_content_path_and_symlink_drift",
        "test_fixed_nonce_path_is_contract_bound_without_creation",
        "test_source_has_no_secret_loading_executor_import_or_runtime_effects",
    }
    if not required_tests.issubset(tests):
        raise ValueError("verifier negative controls incomplete")
    boundaries = {
        "constant_time_mac_comparison": "hmac.compare_digest" in source,
        "domain_separated_canonical_message": "domain_separator" in source and "b\"\\0\"" in source,
        "executor_view_exactly_bound": "EXECUTOR_AUTHORIZATION_FIELDS" in source,
        "all_model_files_stream_hashed": "stream.read(1024 * 1024)" in source,
        "model_symlinks_rejected": "path.resolve() == path" in source,
        "nonce_path_fixed": "FIXED_NONCE_STORE" in source,
        "secret_loading_absent": "os.environ" not in source and "open(key" not in source,
        "executor_import_absent": "story_bounded_render_executor" not in imports,
        "model_runtime_import_absent": "onnxruntime" not in imports,
        "nonce_database_creation_absent": "sqlite3" not in imports,
        "cli_entrypoint_absent": 'if __name__ == "__main__"' not in source,
    }
    if not all(boundaries.values()):
        raise ValueError("verifier source boundary incomplete")
    runtime = {"loaded_secret": False, "created_nonce_store": False,
               "imported_executor": False, "called_executor": False,
               "loaded_model": False, "executed_onnx": False,
               "rendered_audio": False, "played_audio": False,
               "recorded_audio": False, "wrote_memory": False}
    blockers = ["secure_authority_key_not_installed", "nonce_store_parent_not_installed",
                "executor_composition_entrypoint_not_implemented"]
    bound = {
        "evidence": {"s608_contract_file_sha256": _sha(contract_path),
                     "s608_contract_sha256": contract["contract_sha256"],
                     "verifier_path": str(verifier_path.resolve()),
                     "verifier_sha256": _sha(verifier_path),
                     "verifier_test_path": str(verifier_test_path.resolve()),
                     "verifier_test_sha256": _sha(verifier_test_path),
                     "test_count": len(tests)},
        "boundaries": boundaries, "blockers": blockers,
        "implementation_present": True, "configuration_installed": False,
        "execution_authorized": False, "runtime_effects": runtime,
    }
    return {"schema": "agent_bridge.story_executor_runtime_verifiers_review.v1",
            "status": "story_executor_runtime_verifiers_reviewable",
            "decision": "verifier_source_accepted_runtime_configuration_blocked",
            **bound, "review_sha256": _digest(bound),
            "claims": {"authority_verifier_implemented": True,
                       "model_bundle_verifier_implemented": True,
                       "fixed_nonce_path_adapter_implemented": True,
                       "secure_configuration_installed": False,
                       "executor_composed": False, "real_model_executed": False},
            "next_gate": "story_executor_secure_runtime_composition_implementation_review"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verifier", type=Path, required=True)
    parser.add_argument("--verifier-test", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    value = build_review(verifier_path=args.verifier, verifier_test_path=args.verifier_test,
                         contract_path=args.contract)
    print(json.dumps(value, ensure_ascii=False, indent=2 if args.pretty else None,
                     separators=None if args.pretty else (",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
