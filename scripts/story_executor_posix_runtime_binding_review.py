#!/usr/bin/env python3
"""Build S612's static POSIX runtime-binding adoption review."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any


POSIX_NONCE = "/home/pallasting/.agent-bridge-secure/story-render/story-render-nonces.sqlite3"
LEGACY_NONCE = "/Data/Models/agent-bridge/runtime/voice-scene/story-render-nonces.sqlite3"


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
    if (contract.get("schema")
            != "agent_bridge.story_executor_authority_model_nonce_contract.v1"
            or contract.get("nonce_store", {}).get("path") != POSIX_NONCE
            or contract.get("execution_authorized") is not False
            or _digest(bound) != contract.get("contract_sha256")):
        raise ValueError("S608 POSIX contract invalid")


def _validate_s611(contract: dict[str, Any]) -> None:
    bound = {key: contract[key] for key in (
        "evidence", "custody", "installation", "blockers",
        "installation_authorized", "execution_authorized", "runtime_effects")}
    if (contract.get("schema")
            != "agent_bridge.story_executor_secure_runtime_configuration_contract.v1"
            or contract.get("next_gate")
            != "story_executor_posix_runtime_binding_implementation_review"
            or contract.get("custody", {}).get("nonce_store", {}).get("path")
            != POSIX_NONCE
            or contract.get("installation_authorized") is not False
            or contract.get("execution_authorized") is not False
            or any(contract.get("runtime_effects", {}).values())
            or _digest(bound) != contract.get("contract_sha256")):
        raise ValueError("S611 contract invalid")


def build_review(*, binding_path: Path, binding_test_path: Path,
                 s608_contract_path: Path, s611_contract_path: Path,
                 verifier_path: Path, composition_path: Path) -> dict[str, Any]:
    paths = (binding_path, binding_test_path, s608_contract_path,
             s611_contract_path, verifier_path, composition_path)
    if any(not path.is_file() for path in paths):
        raise ValueError("S612 review input missing")
    s608 = _read(s608_contract_path)
    s611 = _read(s611_contract_path)
    _validate_s608(s608)
    _validate_s611(s611)
    source = binding_path.read_text(encoding="utf-8")
    verifier = verifier_path.read_text(encoding="utf-8")
    composition = composition_path.read_text(encoding="utf-8")
    if LEGACY_NONCE in verifier or LEGACY_NONCE in composition:
        raise ValueError("active legacy FUSE nonce binding present")
    if POSIX_NONCE not in verifier or POSIX_NONCE not in source:
        raise ValueError("POSIX nonce binding incomplete")
    tree = ast.parse(source)
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    required_functions = {"secure_nonce_store_path", "secure_key_bundle_path",
                          "_open_private_parent", "_load_authority_key",
                          "load_installed_authority_key"}
    if not required_functions.issubset(functions):
        raise ValueError("S612 binding function missing")
    test_tree = ast.parse(binding_test_path.read_text(encoding="utf-8"))
    tests = sorted(node.name for node in test_tree.body
                   if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
    required_tests = {
        "test_fd_loader_returns_requested_key_and_clears_context",
        "test_loader_rejects_mode_symlink_and_hardlink",
        "test_loader_rejects_unknown_revoked_and_non_closed_schema",
        "test_fixed_binding_comes_from_s611_with_key_installed_and_nonce_absent",
        "test_source_uses_fd_identity_checks_and_has_no_fallback_surface",
    }
    if not required_tests.issubset(tests):
        raise ValueError("S612 negative controls incomplete")
    boundaries = {
        "s608_nonce_binding_is_posix": s608["nonce_store"]["path"] == POSIX_NONCE,
        "s609_verifier_nonce_binding_is_posix": POSIX_NONCE in verifier,
        "legacy_fuse_absent_from_active_sources": LEGACY_NONCE not in verifier and LEGACY_NONCE not in composition,
        "s611_contract_digest_checked": "_read_contract" in source,
        "parent_components_opened_no_follow": "os.O_DIRECTORY" in source and "os.O_NOFOLLOW" in source,
        "key_opened_no_follow_close_on_exec": "os.O_CLOEXEC" in source and "path.name" in source,
        "same_fd_identity_checked": "os.fstat(" in source,
        "mode_owner_and_nlink_checked": all(marker in source for marker in
            ("metadata.st_uid", "metadata.st_gid", "metadata.st_nlink", "0o600")),
        "closed_key_schema_and_revocation_checked": "verify_only" in source and "revoked" in source,
        "key_buffer_cleared": "self._key[index] = 0" in source,
        "secret_generation_and_environment_fallback_absent": "secrets.token_bytes" not in source and "os.environ" not in source,
        "database_creation_absent": "import sqlite3" not in source,
        "executor_and_model_runtime_absent": "execute_bounded_render" not in source and "onnxruntime" not in source,
        "cli_absent": 'if __name__ == "__main__"' not in source,
    }
    if not all(boundaries.values()):
        raise ValueError("S612 source boundary incomplete")
    blockers = ["secure_configuration_not_installed",
                "installed_key_not_composed_into_preparation",
                "executor_invocation_not_authorized"]
    runtime = {"created_runtime_directory": False, "created_key_bundle": False,
               "generated_key": False, "created_nonce_store": False,
               "loaded_installed_key": False, "called_executor": False,
               "loaded_model": False, "executed_onnx": False,
               "rendered_audio": False, "played_audio": False,
               "recorded_audio": False, "wrote_memory": False}
    evidence = {
        "s608_contract_file_sha256": _sha(s608_contract_path),
        "s608_contract_sha256": s608["contract_sha256"],
        "s611_contract_file_sha256": _sha(s611_contract_path),
        "s611_contract_sha256": s611["contract_sha256"],
        "binding_path": str(binding_path.resolve()), "binding_sha256": _sha(binding_path),
        "binding_test_path": str(binding_test_path.resolve()),
        "binding_test_sha256": _sha(binding_test_path), "test_count": len(tests),
        "verifier_sha256": _sha(verifier_path),
        "composition_sha256": _sha(composition_path),
    }
    bound = {"evidence": evidence, "boundaries": boundaries, "blockers": blockers,
             "implementation_present": True, "installation_authorized": False,
             "execution_authorized": False, "runtime_effects": runtime}
    return {"schema": "agent_bridge.story_executor_posix_runtime_binding_review.v1",
            "status": "story_executor_posix_runtime_binding_reviewable",
            "decision": "posix_binding_and_fd_key_loader_accepted_installation_blocked",
            **bound, "review_sha256": _digest(bound),
            "claims": {"posix_nonce_binding_implemented": True,
                       "fd_authority_key_loader_implemented": True,
                       "legacy_fuse_active_binding_removed": True,
                       "secure_configuration_installed": False,
                       "installed_key_loaded": False, "executor_invoked": False},
            "next_gate": "story_executor_installed_key_composition_implementation_review"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--binding-test", type=Path, required=True)
    parser.add_argument("--s608-contract", type=Path, required=True)
    parser.add_argument("--s611-contract", type=Path, required=True)
    parser.add_argument("--verifier", type=Path, required=True)
    parser.add_argument("--composition", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    value = build_review(binding_path=args.binding, binding_test_path=args.binding_test,
        s608_contract_path=args.s608_contract, s611_contract_path=args.s611_contract,
        verifier_path=args.verifier, composition_path=args.composition)
    print(json.dumps(value, ensure_ascii=False, indent=2 if args.pretty else None,
                     separators=None if args.pretty else (",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
