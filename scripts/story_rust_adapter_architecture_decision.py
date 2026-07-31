#!/usr/bin/env python3
"""Choose the Rust integration path for the accepted story preflight."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence


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


def _python_imports(paths: Sequence[Path]) -> tuple[list[str], list[str], int]:
    imported: set[str] = set()
    total_lines = 0
    for path in paths:
        source = path.read_text(encoding="utf-8")
        total_lines += len(source.splitlines())
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
    stdlib = sorted(name for name in imported if name in sys.stdlib_module_names)
    third_party = sorted(imported - set(stdlib))
    return stdlib, third_party, total_lines


def _cargo_dependency(source: str, name: str) -> bool:
    return (
        re.search(
            rf"(?m)^\s*{re.escape(name)}(?:\.[A-Za-z0-9_-]+)?\s*=",
            source,
        )
        is not None
    )


def build_architecture_decision(
    *,
    bridge_cargo_path: Path,
    workspace_cargo_path: Path,
    deploy_script_path: Path,
    python_module_paths: Sequence[Path],
    adapter_receipt_path: Path,
) -> dict[str, Any]:
    """Audit current constraints and select a fail-closed integration path."""

    bridge_cargo = bridge_cargo_path.read_text(encoding="utf-8")
    workspace_cargo = workspace_cargo_path.read_text(encoding="utf-8")
    cargo_evidence = f"{bridge_cargo}\n{workspace_cargo}".lower()
    has_pyo3 = any(
        marker in cargo_evidence for marker in ("pyo3", "libpython", "pythonize")
    )
    if has_pyo3:
        raise ValueError("embedded-Python dependency evidence changed")

    stdlib_imports, third_party_imports, total_lines = _python_imports(
        python_module_paths
    )
    if third_party_imports:
        raise ValueError(
            "third-party Python dependency requires review:"
            + ",".join(third_party_imports)
        )
    rust_primitives = {
        "serde_json": _cargo_dependency(bridge_cargo, "serde_json"),
        "sha2": _cargo_dependency(bridge_cargo, "sha2"),
    }
    if not all(rust_primitives.values()):
        raise ValueError("required Rust primitive dependency missing")

    deploy_source = deploy_script_path.read_text(encoding="utf-8")
    native_deploy = all(
        marker in deploy_source
        for marker in ("agent-bridge.real", "is_native_exe", "ADAPTER_SOURCE")
    )
    if not native_deploy:
        raise ValueError("native binary deploy contract unresolved")

    adapter_receipt = json.loads(adapter_receipt_path.read_text(encoding="utf-8"))
    claims = adapter_receipt.get("claims", {})
    if (
        adapter_receipt.get("status") != "python_inprocess_adapter_verified"
        or claims.get("python_same_process_direct_call") is not True
        or claims.get("rust_inprocess_adapter_proven") is not False
        or claims.get("mcp_tool_registered") is not False
        or any(adapter_receipt.get("runtime_effects", {}).values())
    ):
        raise ValueError("S5ZH adapter evidence invalid")

    evidence = {
        "bridge_cargo_path": str(bridge_cargo_path.resolve()),
        "bridge_cargo_sha256": _sha256_file(bridge_cargo_path),
        "workspace_cargo_path": str(workspace_cargo_path.resolve()),
        "workspace_cargo_sha256": _sha256_file(workspace_cargo_path),
        "deploy_script_path": str(deploy_script_path.resolve()),
        "deploy_script_sha256": _sha256_file(deploy_script_path),
        "adapter_receipt_path": str(adapter_receipt_path.resolve()),
        "adapter_receipt_sha256": adapter_receipt["adapter_receipt_sha256"],
        "bridge_has_pyo3": has_pyo3,
        "rust_primitives_available": rust_primitives,
        "python_stdlib_imports": stdlib_imports,
        "python_third_party_imports": third_party_imports,
        "python_total_lines": total_lines,
        "python_module_sha256": {
            str(path.resolve()): _sha256_file(path) for path in python_module_paths
        },
        "native_binary_deploy_contract": native_deploy,
    }
    options = [
        {
            "name": "incremental_rust_native_port",
            "verdict": "selected",
            "benefits": [
                "preserves_single_native_binary_runtime",
                "avoids_python_abi_gil_and_interpreter_lifecycle",
                "reuses_serde_json_and_sha2",
                "keeps_mcp_cancellation_and_error_model_native",
            ],
            "costs": [
                "ports_deterministic_story_logic",
                "requires_cross_language_golden_parity",
                "temporarily_maintains_python_oracle",
            ],
        },
        {
            "name": "embedded_python_interpreter",
            "verdict": "rejected_for_current_scope",
            "benefits": ["reuses_current_python_implementation"],
            "costs": [
                "adds_python_abi_and_packaging_to_bridge",
                "adds_gil_and_interpreter_lifecycle",
                "widens_binary_supply_chain",
                "conflicts_with_current_native_deploy_contract",
            ],
            "revisit_trigger": (
                "a_required_python_only_dependency_blocks_a_bounded_native_port_"
                "or_measured_parity_maintenance_cost_exceeds_embedding_cost"
            ),
        },
    ]
    decision = {
        "selected": "incremental_rust_native_port",
        "embedded_python": "rejected_for_current_scope",
        "rationale": [
            "story_preflight_is_stdlib_only_deterministic_logic",
            "required_rust_json_and_hash_primitives_already_exist",
            "bridge_has_no_embedded_python_dependency_or_lifecycle",
            "deployment_is_centered_on_one_native_binary",
        ],
        "revisit_policy": "evidence_required_no_preference_only_reversal",
    }
    migration = {
        "python_role": "test_oracle_only",
        "runtime_authority_transfer": False,
        "rollback": "remove_unregistered_rust_module_and_keep_python_oracle",
        "stages": [
            {
                "id": "S5ZJ",
                "goal": "rust_story_contract_core",
                "required_proof": "typed_request_canonical_json_and_hash_parity",
                "registered_mcp_tool": False,
            },
            {
                "id": "S5ZK",
                "goal": "rust_story_source_ingest_parity",
                "required_proof": "chapter_source_and_selection_golden_parity",
                "registered_mcp_tool": False,
            },
            {
                "id": "S5ZL",
                "goal": "rust_story_voice_plan_parity",
                "required_proof": "segment_transition_and_cache_key_parity",
                "registered_mcp_tool": False,
            },
            {
                "id": "S5ZM",
                "goal": "rust_story_preflight_adapter_parity",
                "required_proof": "full_s5zf_schema_and_negative_control_parity",
                "registered_mcp_tool": False,
            },
        ],
        "post_parity_gate": "separate_owner_authorized_mcp_registration",
    }
    bound = {"evidence": evidence, "options": options, "decision": decision, "migration": migration}
    return {
        "schema": "agent_bridge.story_rust_adapter_architecture_decision.v1",
        "status": "architecture_decision_accepted_static",
        **bound,
        "decision_sha256": _digest(bound),
        "execution_authorized": False,
        "runtime_effects": {
            "modified_cargo_dependencies": False,
            "added_pyo3": False,
            "implemented_rust_adapter": False,
            "modified_rust_registry": False,
            "registered_story_command": False,
            "spawned_subprocess": False,
            "loaded_python_interpreter": False,
            "loaded_model": False,
            "executed_onnx": False,
            "rendered_audio": False,
            "played_audio": False,
            "wrote_cache": False,
            "wrote_memory": False,
        },
        "next_gate": "rust_story_contract_core",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge-cargo", type=Path, required=True)
    parser.add_argument("--workspace-cargo", type=Path, required=True)
    parser.add_argument("--deploy-script", type=Path, required=True)
    parser.add_argument("--python-module", type=Path, action="append", required=True)
    parser.add_argument("--adapter-receipt", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = build_architecture_decision(
        bridge_cargo_path=args.bridge_cargo,
        workspace_cargo_path=args.workspace_cargo,
        deploy_script_path=args.deploy_script,
        python_module_paths=args.python_module,
        adapter_receipt_path=args.adapter_receipt,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
