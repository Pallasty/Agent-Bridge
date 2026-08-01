#!/usr/bin/env python3
"""Build the static S610 preparation-composition review."""

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


def _validate_s609(review: dict[str, Any]) -> None:
    bound = {key: review[key] for key in (
        "evidence", "boundaries", "blockers", "implementation_present",
        "configuration_installed", "execution_authorized", "runtime_effects")}
    if (review.get("schema") != "agent_bridge.story_executor_runtime_verifiers_review.v1"
            or review.get("next_gate") != "story_executor_secure_runtime_composition_implementation_review"
            or review.get("execution_authorized") is not False
            or any(review.get("runtime_effects", {}).values())
            or _digest(bound) != review.get("review_sha256")):
        raise ValueError("S609 review invalid")


def build_review(*, composition_path: Path, composition_test_path: Path,
                 verifier_review_path: Path) -> dict[str, Any]:
    for path in (composition_path, composition_test_path, verifier_review_path):
        if not path.is_file():
            raise ValueError(f"required source missing:{path}")
    prior = _read(verifier_review_path)
    _validate_s609(prior)
    source = composition_path.read_text(encoding="utf-8")
    if "execute_bounded_render" in source:
        raise ValueError("executor execution surface forbidden")
    tree = ast.parse(source)
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    preparation_seams = {
        "prepare_secure_bounded_render",
        "_prepare_secure_bounded_render_with_key",
    }
    if functions.isdisjoint(preparation_seams):
        raise ValueError("preparation composition missing")
    test_tree = ast.parse(composition_test_path.read_text(encoding="utf-8"))
    tests = sorted(node.name for node in test_tree.body
                   if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
    required = {"test_prepare_composes_exact_executor_arguments_without_execution",
                "test_prepare_rejects_envelope_request_and_model_path_drift",
                "test_prepare_rejects_execution_contract_drift",
                "test_source_has_no_execution_cli_secret_or_database_surface"}
    if not required.issubset(tests):
        raise ValueError("composition negative controls incomplete")
    boundaries = {
        "s604_execution_contract_digest_checked": "_validate_execution_contract" in source,
        "s608_runtime_contract_fixed": "RUNTIME_CONTRACT_PATH" in source,
        "s609_verifier_source_pinned": "VERIFIER_SHA256" in source,
        "signed_executor_view_composed": "EXECUTOR_AUTHORIZATION_FIELDS" in source,
        "external_tts_support_path_bound": "TTS_SUPPORT_FILES" in source,
        "external_tts_support_hash_checked": "_validate_tts_support_assets" in source,
        "playback_recording_memory_rejected": all(marker in source for marker in
            ('request["playback"] is not False', 'request["record"] is not False', 'request["write_memory"] is not False')),
        "executor_import_and_invocation_absent": "execute_bounded_render" not in source,
        "secret_loading_absent": "os.environ" not in source,
        "nonce_creation_absent": "sqlite3" not in source,
        "onnx_runtime_absent": "onnxruntime" not in source,
        "cli_absent": 'if __name__ == "__main__"' not in source,
    }
    if not all(boundaries.values()):
        raise ValueError("composition boundary incomplete")
    runtime = {"loaded_secret": False, "created_nonce_store": False,
               "imported_executor": False, "called_executor": False,
               "loaded_model": False, "executed_onnx": False,
               "rendered_audio": False, "played_audio": False,
               "recorded_audio": False, "wrote_memory": False}
    blockers = ["secure_authority_key_not_installed", "nonce_store_parent_not_installed",
                "executor_invocation_not_authorized"]
    bound = {"evidence": {"s609_review_file_sha256": _sha(verifier_review_path),
                           "s609_review_sha256": prior["review_sha256"],
                           "composition_path": str(composition_path.resolve()),
                           "composition_sha256": _sha(composition_path),
                           "composition_test_path": str(composition_test_path.resolve()),
                           "composition_test_sha256": _sha(composition_test_path),
                           "test_count": len(tests)},
             "boundaries": boundaries, "blockers": blockers,
             "implementation_present": True, "configuration_installed": False,
             "execution_authorized": False, "runtime_effects": runtime}
    return {"schema": "agent_bridge.story_executor_secure_runtime_composition_review.v1",
            "status": "story_executor_secure_runtime_composition_reviewable",
            "decision": "preparation_composition_accepted_invocation_blocked", **bound,
            "review_sha256": _digest(bound),
            "claims": {"secure_preparation_composed": True,
                       "external_tts_support_path_corrected": True,
                       "executor_invocation_present": False,
                       "secure_configuration_installed": False,
                       "real_model_executed": False},
            "next_gate": "story_executor_secure_runtime_configuration_installation_contract"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--composition", type=Path, required=True)
    parser.add_argument("--composition-test", type=Path, required=True)
    parser.add_argument("--verifier-review", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    value = build_review(composition_path=args.composition,
                         composition_test_path=args.composition_test,
                         verifier_review_path=args.verifier_review)
    print(json.dumps(value, ensure_ascii=False, indent=2 if args.pretty else None,
                     separators=None if args.pretty else (",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
