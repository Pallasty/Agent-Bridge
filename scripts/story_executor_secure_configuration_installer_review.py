#!/usr/bin/env python3
"""Build S614's source-only secure configuration installer review."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT))


def _validate_s611(contract: dict[str, Any]) -> None:
    bound = {key: contract[key] for key in (
        "evidence", "custody", "installation", "blockers",
        "installation_authorized", "execution_authorized", "runtime_effects")}
    if (contract.get("schema")
            != "agent_bridge.story_executor_secure_runtime_configuration_contract.v1"
            or contract.get("installation_authorized") is not False
            or contract.get("execution_authorized") is not False
            or any(contract.get("runtime_effects", {}).values())
            or _digest(bound) != contract.get("contract_sha256")):
        raise ValueError("S611 contract invalid")


def _validate_s613(review: dict[str, Any]) -> None:
    bound = {key: review[key] for key in (
        "evidence", "boundaries", "blockers", "implementation_present",
        "installation_authorized", "execution_authorized", "runtime_effects")}
    if (review.get("schema")
            != "agent_bridge.story_executor_installed_key_composition_review.v1"
            or review.get("next_gate")
            != "owner_authorized_story_executor_secure_configuration_installation"
            or review.get("installation_authorized") is not False
            or review.get("execution_authorized") is not False
            or any(review.get("runtime_effects", {}).values())
            or _digest(bound) != review.get("review_sha256")):
        raise ValueError("S613 review invalid")


def _public_signature(tree: ast.Module) -> list[str]:
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and not node.name.startswith("_")]
    if (len(functions) != 1
            or functions[0].name
            != "install_story_render_secure_configuration"):
        raise ValueError("S614 public signature invalid")
    function = functions[0]
    if (function.args.args or function.args.posonlyargs
            or function.args.kwonlyargs or function.args.vararg
            or function.args.kwarg):
        raise ValueError("S614 public signature invalid")
    return []


def build_review(
    *, installer_path: Path, installer_test_path: Path,
    s611_contract_path: Path, s613_review_path: Path,
    result_schema_path: Path,
) -> dict[str, Any]:
    paths = (installer_path, installer_test_path,
             s611_contract_path, s613_review_path, result_schema_path)
    if any(not path.is_file() for path in paths):
        raise ValueError("S614 review input missing")
    s611 = _read(s611_contract_path)
    s613 = _read(s613_review_path)
    result_schema = _read(result_schema_path)
    _validate_s611(s611)
    _validate_s613(s613)
    source = installer_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    signature = _public_signature(tree)
    functions = {node.name for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    if "_install_secure_configuration" not in functions:
        raise ValueError("S614 private transaction seam missing")
    tests_tree = ast.parse(installer_test_path.read_text(encoding="utf-8"))
    tests = sorted(node.name for node in tests_tree.body
                   if isinstance(node, ast.FunctionDef)
                   and node.name.startswith("test_"))
    required_tests = {
        "test_transaction_installs_loader_compatible_bundle_without_nonce",
        "test_transaction_rejects_unsafe_or_preexisting_targets",
        "test_transaction_rejects_bad_key_material_and_rolls_back",
        "test_prepublication_failure_removes_only_transaction_owned_objects",
        "test_prepublication_rollback_fsyncs_removed_directory_chain",
        "test_publication_collision_preserves_unowned_target",
        "test_postpublication_failure_requires_recovery_without_deleting_key",
        "test_process_umask_is_restored_after_success",
        "test_public_surface_is_fixed_after_authorized_installation",
        "test_fixed_policy_parses_the_same_bytes_that_were_hashed",
    }
    if not required_tests.issubset(tests):
        raise ValueError("S614 negative controls incomplete")
    s611_sha = _sha(s611_contract_path)
    s613_sha = _sha(s613_review_path)
    result_schema_sha = _sha(result_schema_path)
    boundaries = {
        "fixed_public_entrypoint_has_no_parameters": signature == [],
        "private_fault_injection_seam_not_public":
        "def _install_secure_configuration" in source,
        "s611_contract_hash_pinned": s611_sha in source,
        "s613_review_hash_pinned": s613_sha in source,
        "policy_json_parsed_from_hashed_bytes":
        "payload = path.read_bytes()" in source
        and "json.loads(payload.decode(\"utf-8\"))" in source,
        "fixed_custody_paths_only": all(marker in source for marker in (
            "/home/pallasting/.agent-bridge-secure",
            "authority-keys.v1.json", "story-render-nonces.sqlite3")),
        "fixed_non_secret_key_id":
        'FIXED_KEY_ID = "story-render-owner-v1"' in source,
        "approved_posix_filesystem_checked":
        "APPROVED_FILESYSTEMS" in source and "_filesystem_type" in source,
        "parent_components_opened_no_follow":
        "os.O_DIRECTORY" in source and "os.O_NOFOLLOW" in source,
        "root_mode_owner_identity_checked": all(marker in source for marker in (
            "0o700", "metadata.st_uid", "metadata.st_gid")),
        "runtime_directory_created_relative_to_root_fd":
        "os.mkdir(runtime_directory.name" in source and "dir_fd=root_fd" in source,
        "process_umask_set_and_restored":
        "previous_umask = os.umask(0o077)" in source
        and "os.umask(previous_umask)" in source,
        "temporary_key_created_exclusive_no_follow": all(
            marker in source for marker in
            ("os.O_CREAT", "os.O_EXCL", "os.O_NOFOLLOW", "os.O_CLOEXEC")),
        "key_material_exact_nonzero_32_bytes":
        "len(raw_key) != 32" in source and "not any(raw_key)" in source,
        "operational_key_source_is_os_csprng": "secrets.token_bytes" in source,
        "complete_write_and_file_fsync":
        "_write_all(key_fd, payload)" in source and "os.fsync(key_fd)" in source,
        "atomic_no_replace_publication":
        "os.link(" in source and "os.unlink(TEMPORARY_KEY_NAME" in source,
        "same_fd_mode_owner_nlink_checked":
        "os.fstat(descriptor)" in source and "metadata.st_nlink != 1" in source,
        "published_file_reopened_no_follow":
        "read_fd = os.open(" in source and "_validate_key_descriptor(read_fd)" in source,
        "prepublication_rollback_is_owned_only":
        "temporary_created" in source and "runtime_created" in source,
        "rollback_directory_chain_fsynced":
        "os.rmdir(runtime_directory.name" in source and "os.fsync(root_fd)" in source,
        "postpublication_failure_requires_recovery":
        "if published:" in source and "InstallationRecoveryRequired" in source,
        "nonce_store_remains_absent":
        "_assert_absent(" in source and "FIXED_NONCE_STORE.name" in source,
        "returned_receipt_redacts_key_material":
        '"key_material_disclosed": False' in source,
        "installation_result_schema_bound":
        result_schema.get("$id")
        == "agent_bridge.story_render_secure_configuration_installation.v1"
        and result_schema.get("properties", {}).get("schema", {}).get("const")
        == "agent_bridge.story_render_secure_configuration_installation.v1",
        "secret_logging_and_environment_fallback_absent":
        "os.environ" not in source and "print(" not in source
        and "logging" not in source,
        "executor_database_and_model_runtime_absent":
        "execute_bounded_render" not in source
        and "import sqlite3" not in source and "onnxruntime" not in source,
        "cli_absent": 'if __name__ == "__main__"' not in source,
    }
    if not all(boundaries.values()):
        raise ValueError("S614 installer boundary incomplete")
    blockers = [
        "owner_authorized_secure_configuration_installation_not_granted",
        "executor_invocation_not_authorized",
    ]
    runtime_effects = {
        "created_runtime_directory": False,
        "created_key_bundle": False,
        "generated_key": False,
        "created_nonce_store": False,
        "loaded_installed_key": False,
        "called_executor": False,
        "loaded_model": False,
        "executed_onnx": False,
        "rendered_audio": False,
        "played_audio": False,
        "recorded_audio": False,
        "wrote_memory": False,
    }
    builder_path = Path(__file__).resolve()
    evidence = {
        "review_builder_path": _relative(builder_path),
        "review_builder_sha256": _sha(builder_path),
        "s611_contract_path": _relative(s611_contract_path),
        "s611_contract_file_sha256": s611_sha,
        "s611_contract_sha256": s611["contract_sha256"],
        "s613_review_path": _relative(s613_review_path),
        "s613_review_file_sha256": s613_sha,
        "s613_review_sha256": s613["review_sha256"],
        "installer_path": _relative(installer_path),
        "installer_sha256": _sha(installer_path),
        "installer_test_path": _relative(installer_test_path),
        "installer_test_sha256": _sha(installer_test_path),
        "result_schema_path": _relative(result_schema_path),
        "result_schema_sha256": result_schema_sha,
        "test_count": len(tests),
        "public_arguments": signature,
    }
    bound = {
        "evidence": evidence,
        "boundaries": boundaries,
        "blockers": blockers,
        "implementation_present": True,
        "installation_authorized": False,
        "execution_authorized": False,
        "runtime_effects": runtime_effects,
    }
    return {
        "schema": "agent_bridge.story_executor_secure_configuration_installer_review.v1",
        "status": "story_executor_secure_configuration_installer_reviewable",
        "decision": "installer_source_accepted_installation_still_blocked",
        **bound,
        "review_sha256": _digest(bound),
        "claims": {
            "fixed_path_installer_implemented": True,
            "atomic_no_replace_publication_implemented": True,
            "prepublication_owned_rollback_implemented": True,
            "postpublication_recovery_gate_implemented": True,
            "secure_configuration_installed": False,
            "real_key_generated": False,
            "executor_invoked": False,
        },
        "next_gate": (
            "owner_authorized_story_executor_secure_configuration_installation"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--installer-test", type=Path, required=True)
    parser.add_argument("--s611-contract", type=Path, required=True)
    parser.add_argument("--s613-review", type=Path, required=True)
    parser.add_argument("--result-schema", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    value = build_review(
        installer_path=args.installer,
        installer_test_path=args.installer_test,
        s611_contract_path=args.s611_contract,
        s613_review_path=args.s613_review,
        result_schema_path=args.result_schema,
    )
    print(json.dumps(
        value, ensure_ascii=False, indent=2 if args.pretty else None,
        separators=None if args.pretty else (",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
