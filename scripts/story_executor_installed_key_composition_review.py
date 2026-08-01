#!/usr/bin/env python3
"""Build S613's static installed-key-only public composition review."""

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


def _validate_s612(review: dict[str, Any]) -> None:
    bound = {key: review[key] for key in (
        "evidence", "boundaries", "blockers", "implementation_present",
        "installation_authorized", "execution_authorized", "runtime_effects")}
    if (review.get("schema")
            != "agent_bridge.story_executor_posix_runtime_binding_review.v1"
            or review.get("next_gate")
            != "story_executor_installed_key_composition_implementation_review"
            or review.get("installation_authorized") is not False
            or review.get("execution_authorized") is not False
            or any(review.get("runtime_effects", {}).values())
            or _digest(bound) != review.get("review_sha256")):
        raise ValueError("S612 review invalid")


def _public_signature(tree: ast.Module) -> list[str]:
    public = [node for node in tree.body if isinstance(node, ast.FunctionDef)
              and not node.name.startswith("_")]
    if len(public) != 1 or public[0].name != "prepare_installed_secure_bounded_render":
        raise ValueError("S613 public signature invalid")
    function = public[0]
    if function.args.args or function.args.posonlyargs or function.args.vararg or function.args.kwarg:
        raise ValueError("S613 public signature invalid")
    names = [argument.arg for argument in function.args.kwonlyargs]
    if names != ["execution_contract", "envelope", "request"]:
        raise ValueError("S613 public signature invalid")
    return names


def _public_function(tree: ast.Module) -> ast.FunctionDef:
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "prepare_installed_secure_bounded_render")


def _call_names(node: ast.AST) -> set[str]:
    names = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        function = item.func
        if isinstance(function, ast.Name):
            names.add(function.id)
        elif isinstance(function, ast.Attribute):
            names.add(function.attr)
    return names


def build_review(*, composition_path: Path, composition_test_path: Path,
                 base_composition_path: Path, binding_path: Path,
                 prior_review_path: Path) -> dict[str, Any]:
    paths = (composition_path, composition_test_path, base_composition_path,
             binding_path, prior_review_path)
    if any(not path.is_file() for path in paths):
        raise ValueError("S613 review input missing")
    prior = _read(prior_review_path)
    _validate_s612(prior)
    source = composition_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    signature = _public_signature(tree)
    base_source = base_composition_path.read_text(encoding="utf-8")
    base_tree = ast.parse(base_source)
    if any(isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
           for node in base_tree.body):
        raise ValueError("caller-supplied key public seam remains")
    binding_sha = _sha(binding_path)
    base_sha = _sha(base_composition_path)
    if binding_sha not in source or base_sha not in source:
        raise ValueError("S613 pinned dependency mismatch")
    test_tree = ast.parse(composition_test_path.read_text(encoding="utf-8"))
    tests = sorted(node.name for node in test_tree.body
                   if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
    required = {
        "test_public_entrypoint_has_no_key_or_path_override_parameters",
        "test_public_entrypoint_loads_envelope_key_id_and_clears_context",
        "test_public_entrypoint_rejects_missing_key_id_before_loading",
        "test_public_entrypoint_rejects_malformed_envelope_before_loading",
        "test_loaded_key_context_clears_when_preparation_rejects_request",
        "test_loaded_key_context_clears_when_mac_is_rejected",
        "test_key_is_cleared_before_non_secret_preparation",
        "test_fixed_installed_key_is_present_after_authorized_installation",
        "test_source_has_no_executor_invocation_cli_or_key_path_override",
    }
    if not required.issubset(tests):
        raise ValueError("S613 negative controls incomplete")
    public_function = _public_function(tree)
    key_contexts = [node for node in public_function.body if isinstance(node, ast.With)]
    key_context = key_contexts[0] if len(key_contexts) == 1 else None
    top_level_finish = [node for node in public_function.body
                        if "_prepare_secure_bounded_render_with_authority_verifier_context"
                        in _call_names(node)]
    envelope_validation = source.find("key_id = _validate_closed_envelope(envelope)")
    binding_load = source.find("binding = _load_binding()")
    composition_load = source.find("composition = _load_composition()")
    boundaries = {
        "only_one_public_preparation_entrypoint": signature
        == ["execution_contract", "envelope", "request"],
        "caller_supplied_key_parameter_absent": "key" not in signature,
        "caller_path_override_parameter_absent": "path" not in signature,
        "envelope_key_id_selects_installed_key": 'envelope.get("key_id")' in source
        and "load_installed_authority_key(key_id)" in source,
        "closed_envelope_validated_before_dependency_or_key_load":
        0 <= envelope_validation < binding_load < composition_load,
        "base_composition_source_pinned": base_sha in source,
        "posix_binding_source_pinned": binding_sha in source,
        "hashed_dependency_bytes_are_executed": "source = path.read_bytes()" in source
        and "compile(source, str(path), \"exec\")" in source,
        "base_hashed_verifier_bytes_are_executed":
        "source = VERIFIER_PATH.read_bytes()" in base_source
        and "compile(source, str(VERIFIER_PATH), \"exec\")" in base_source,
        "authority_verifier_built_inside_key_context": key_context is not None
        and "_build_authority_verifier_context_with_key" in _call_names(key_context),
        "key_context_exited_before_non_secret_preparation": key_context is not None
        and len(top_level_finish) == 1
        and key_context.lineno < top_level_finish[0].lineno,
        "same_keyless_dependency_context_reused_after_clear":
        "authority_verifier_context=authority_verifier_context" in source,
        "loaded_key_id_rechecked": "loaded.key_id != key_id" in source,
        "nonce_binding_rechecked": "binding.secure_nonce_store_path()" in source,
        "base_key_seam_private": "def _prepare_secure_bounded_render_with_key" in base_source,
        "base_verifier_completion_seam_private":
        "def _prepare_secure_bounded_render_with_authority_verifier_context" in base_source,
        "executor_invocation_absent": "execute_bounded_render" not in source,
        "environment_and_database_fallback_absent": "os.environ" not in source and "sqlite3" not in source,
        "model_runtime_absent": "onnxruntime" not in source,
        "cli_absent": 'if __name__ == "__main__"' not in source,
    }
    if not all(boundaries.values()):
        raise ValueError("S613 composition boundary incomplete")
    blockers = ["secure_configuration_not_installed", "executor_invocation_not_authorized"]
    runtime = {"created_runtime_directory": False, "created_key_bundle": False,
               "generated_key": False, "created_nonce_store": False,
               "loaded_installed_key": False, "called_executor": False,
               "loaded_model": False, "executed_onnx": False,
               "rendered_audio": False, "played_audio": False,
               "recorded_audio": False, "wrote_memory": False}
    evidence = {
        "review_builder_path": str(Path(__file__).resolve()),
        "review_builder_sha256": _sha(Path(__file__).resolve()),
        "s612_review_file_sha256": _sha(prior_review_path),
        "s612_review_sha256": prior["review_sha256"],
        "composition_path": str(composition_path.resolve()),
        "composition_sha256": _sha(composition_path),
        "composition_test_path": str(composition_test_path.resolve()),
        "composition_test_sha256": _sha(composition_test_path),
        "base_composition_sha256": base_sha, "binding_sha256": binding_sha,
        "test_count": len(tests), "public_keyword_only_arguments": signature,
    }
    bound = {"evidence": evidence, "boundaries": boundaries, "blockers": blockers,
             "implementation_present": True, "installation_authorized": False,
             "execution_authorized": False, "runtime_effects": runtime}
    return {"schema": "agent_bridge.story_executor_installed_key_composition_review.v1",
            "status": "story_executor_installed_key_composition_reviewable",
            "decision": "installed_key_only_public_preparation_accepted_installation_blocked",
            **bound, "review_sha256": _digest(bound),
            "claims": {"installed_key_public_composition_implemented": True,
                       "caller_supplied_key_public_interface_absent": True,
                       "mutable_key_buffer_best_effort_cleared_before_non_secret_preparation": True,
                       "complete_python_key_zeroization_claimed": False,
                       "secure_configuration_installed": False,
                       "installed_key_loaded": False, "executor_invoked": False},
            "next_gate": "owner_authorized_story_executor_secure_configuration_installation"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--composition", type=Path, required=True)
    parser.add_argument("--composition-test", type=Path, required=True)
    parser.add_argument("--base-composition", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--prior-review", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    value = build_review(composition_path=args.composition,
        composition_test_path=args.composition_test,
        base_composition_path=args.base_composition,
        binding_path=args.binding, prior_review_path=args.prior_review)
    print(json.dumps(value, ensure_ascii=False, indent=2 if args.pretty else None,
                     separators=None if args.pretty else (",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
