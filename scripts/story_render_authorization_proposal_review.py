#!/usr/bin/env python3
"""Build S615's unsigned Story authorization proposal source review."""

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
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT))


def _validate_s614(result: dict[str, Any]) -> None:
    installation = result.get("installation", {})
    effects = result.get("runtime_effects", {})
    if (
        result.get("schema")
        != "agent_bridge.story_render_secure_configuration_installation.v1"
        or result.get("status")
        != "story_render_secure_configuration_installed"
        or result.get("decision")
        != "configuration_installed_executor_invocation_blocked"
        or result.get("execution_authorized") is not False
        or installation.get("active_key_id") != "story-render-owner-v1"
        or installation.get("runtime_directory_mode") != "0700"
        or installation.get("key_bundle_mode") != "0600"
        or installation.get("nonce_store_absent") is not True
        or installation.get("key_material_disclosed") is not False
        or effects.get("created_key_bundle") is not True
        or effects.get("generated_key") is not True
        or effects.get("created_nonce_store") is not False
        or effects.get("called_executor") is not False
        or effects.get("loaded_model") is not False
        or effects.get("rendered_audio") is not False
        or effects.get("wrote_memory") is not False
    ):
        raise ValueError("S614 installation result invalid")


def _public_signature(tree: ast.Module) -> list[str]:
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    if (
        len(functions) != 1
        or functions[0].name
        != "build_story_render_authorization_proposal"
    ):
        raise ValueError("S615 public signature invalid")
    function = functions[0]
    if (
        function.args.args
        or function.args.posonlyargs
        or function.args.vararg
        or function.args.kwarg
        or [argument.arg for argument in function.args.kwonlyargs]
        != ["execution_contract", "request"]
    ):
        raise ValueError("S615 public signature invalid")
    return [argument.arg for argument in function.args.kwonlyargs]


def _key_content_access_absent(tree: ast.Module) -> bool:
    forbidden_attributes = {"open", "read_bytes", "read_text"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == "key_bundle"
            and function.attr in forbidden_attributes
        ):
            return False
        if (
            isinstance(function, ast.Name)
            and function.id == "_sha256_file"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "key_bundle"
        ):
            return False
    return True


def build_review(
    *,
    proposal_path: Path,
    proposal_test_path: Path,
    installation_result_path: Path,
) -> dict[str, Any]:
    """Review S615 source and tests without invoking its public entrypoint."""
    paths = (proposal_path, proposal_test_path, installation_result_path)
    if any(not path.is_file() for path in paths):
        raise ValueError("S615 review input missing")
    installation_result = _read(installation_result_path)
    _validate_s614(installation_result)
    source = proposal_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    signature = _public_signature(tree)
    tests_tree = ast.parse(proposal_test_path.read_text(encoding="utf-8"))
    tests = sorted(
        node.name
        for node in tests_tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )
    required_tests = {
        "test_public_proposal_binds_exact_request_without_signing",
        "test_proposal_rejects_output_effect_and_model_drift",
        "test_unsigned_proposal_matches_s609_canonical_fields_after_synthetic_mac",
        "test_proposal_reads_no_real_key_and_creates_no_nonce",
        "test_proposal_rejects_unreviewed_s614_receipt_drift",
        "test_source_has_no_secret_loader_executor_or_runtime_surface",
    }
    if not required_tests.issubset(tests):
        raise ValueError("S615 negative controls incomplete")
    boundaries = {
        "public_surface_accepts_only_contract_and_request": signature
        == ["execution_contract", "request"],
        "composition_source_sha256_pinned": (
            "COMPOSITION_SHA256" in source
            and "S610 composition source drift" in source
        ),
        "s614_installation_receipt_required": (
            "INSTALLATION_RESULT_PATH" in source
            and "_validate_installed_custody" in source
        ),
        "s614_installation_receipt_hash_pinned": (
            "INSTALLATION_RESULT_SHA256" in source
            and _sha(installation_result_path) in source
            and "S614 installation result source drift" in source
        ),
        "installed_key_checked_by_metadata_only": all(
            marker in source
            for marker in (
                "key_bundle.lstat()",
                "metadata_only",
                '"key_material_read": False',
            )
        ),
        "installed_key_content_access_absent": _key_content_access_absent(tree),
        "installed_key_loader_absent": (
            "load_installed_authority_key" not in source
        ),
        "mac_implementation_absent": "hmac" not in source,
        "fixed_non_secret_key_id": (
            'ACTIVE_KEY_ID = "story-render-owner-v1"' in source
        ),
        "fixed_issuer_and_subject": (
            'ISSUER = "agent-bridge-owner-console"' in source
            and 'SUBJECT = "story-bounded-render-executor"' in source
        ),
        "fixed_five_minute_ttl": "TTL_SECONDS = 300" in source,
        "public_identifiers_use_csprng": "secrets.token_hex" in source,
        "exact_contract_request_and_model_validated": all(
            marker in source
            for marker in (
                "_validate_execution_contract",
                "_validate_request_boundary",
                "composition._validate_request",
            )
        ),
        "output_is_single_absent_child_of_contract_root": (
            "output.resolve().parent != output_root" in source
            and "output.exists()" in source
        ),
        "nonce_store_family_must_remain_absent": (
            "nonce store must remain absent before execution" in source
        ),
        "proof_is_explicitly_absent": '"proof_present": False' in source,
        "owner_signature_remains_required": (
            '"owner_signature_required": True' in source
        ),
        "execution_remains_blocked": '"execution_authorized": False' in source,
        "executor_database_model_and_audio_runtime_absent": all(
            marker not in source
            for marker in (
                "execute_bounded_render",
                "sqlite3",
                "onnxruntime",
                "subprocess",
            )
        ),
        "environment_and_cli_surface_absent": (
            "os.environ" not in source
            and 'if __name__ == "__main__"' not in source
        ),
    }
    if not all(boundaries.values()):
        raise ValueError("S615 proposal boundary incomplete")
    blockers = [
        "owner_authorized_envelope_signature_not_granted",
        "executor_invocation_not_authorized",
    ]
    runtime_effects = {
        "read_real_key": False,
        "generated_real_mac": False,
        "created_nonce_store": False,
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
        "installation_result_path": _relative(installation_result_path),
        "installation_result_sha256": _sha(installation_result_path),
        "proposal_path": _relative(proposal_path),
        "proposal_sha256": _sha(proposal_path),
        "proposal_test_path": _relative(proposal_test_path),
        "proposal_test_sha256": _sha(proposal_test_path),
        "test_count": len(tests),
        "public_arguments": signature,
    }
    bound = {
        "evidence": evidence,
        "boundaries": boundaries,
        "blockers": blockers,
        "implementation_present": True,
        "owner_signature_authorized": False,
        "execution_authorized": False,
        "runtime_effects": runtime_effects,
    }
    return {
        "schema": "agent_bridge.story_render_authorization_proposal_review.v1",
        "status": "story_render_authorization_proposal_reviewable",
        "decision": (
            "unsigned_proposal_source_accepted_owner_signature_blocked"
        ),
        **bound,
        "review_sha256": _digest(bound),
        "claims": {
            "unsigned_owner_review_proposal_implemented": True,
            "exact_request_content_addressed": True,
            "real_authority_key_read": False,
            "real_owner_mac_generated": False,
            "executor_invoked": False,
        },
        "next_gate": (
            "owner_authorized_story_render_envelope_signing_preflight"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--proposal-test", type=Path, required=True)
    parser.add_argument("--installation-result", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    value = build_review(
        proposal_path=args.proposal,
        proposal_test_path=args.proposal_test,
        installation_result_path=args.installation_result,
    )
    print(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
