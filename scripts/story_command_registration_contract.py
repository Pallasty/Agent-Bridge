#!/usr/bin/env python3
"""Build the default-hidden static MCP registration contract for `/story`."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


TOOL_NAME = "story_command_preflight"


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


def _tool_input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "source_path": {
                "type": "string",
                "minLength": 1,
                "pattern": r"(?i)\.(txt|md|markdown)$",
                "description": "UTF-8 TXT or Markdown novel path.",
            },
            "start": {
                "oneOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["kind"],
                        "properties": {"kind": {"const": "from_start"}},
                    },
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["kind", "chapter"],
                        "properties": {
                            "kind": {"const": "chapter"},
                            "chapter": {"type": "integer", "minimum": 1},
                        },
                    },
                ]
            },
            "dry_run": {"const": True},
        },
        "required": ["source_path", "start", "dry_run"],
    }


def build_registration_contract(
    *,
    preflight_receipt_path: Path,
    preflight_schema_path: Path,
    preflight_script_path: Path,
    registry_source_path: Path,
) -> dict[str, Any]:
    """Bind an MCP schema proposal while proving it is not registered."""

    preflight = json.loads(preflight_receipt_path.read_text(encoding="utf-8"))
    if (
        preflight.get("status")
        != "story_command_integration_preflight_reviewable"
        or preflight.get("execution_authorized") is not False
        or any(preflight.get("runtime_effects", {}).values())
    ):
        raise ValueError("preflight execution boundary invalid")
    if preflight.get("next_gate") != "story_command_static_registration_contract":
        raise ValueError("preflight next gate mismatch")

    registry_source = registry_source_path.read_text(encoding="utf-8")
    if re.search(rf'["\']{re.escape(TOOL_NAME)}["\']', registry_source):
        raise ValueError(f"tool name already present:{TOOL_NAME}")

    tool = {
        "name": TOOL_NAME,
        "description": (
            "Validate a source-bound story chapter render preflight without "
            "registering playback, loading a model, rendering audio, or writing state."
        ),
        "proposed_tier": "Niche",
        "proposed_toolset_extras": [],
        "input_schema": _tool_input_schema(),
        "output_schema": "agent_bridge.story_command_integration_preflight.v1",
    }
    activation = {
        "compiled_registered": False,
        "current_registry_collision": False,
        "registry_source_path": str(registry_source_path.resolve()),
        "registry_source_sha256": _sha256_file(registry_source_path),
        "default_exposed": False,
        "codex_essential_exposed": False,
        "codex_voice_exposed": False,
        "activation_env": "AB_STORY_COMMAND_PREFLIGHT_ENABLE",
        "activation_env_required_value": "1",
        "activation_env_evaluated": False,
    }
    handler = {
        "kind": "future_isolated_python_adapter",
        "preflight_script_path": str(preflight_script_path.resolve()),
        "preflight_script_sha256": _sha256_file(preflight_script_path),
        "preflight_schema_path": str(preflight_schema_path.resolve()),
        "preflight_schema_sha256": _sha256_file(preflight_schema_path),
        "accepted_preflight_receipt_path": str(preflight_receipt_path.resolve()),
        "accepted_preflight_sha256": preflight["preflight_sha256"],
        "subprocess_allowed": False,
    }
    runtime_effects = {
        "modified_rust_registry": False,
        "registered_story_command": False,
        "loaded_model": False,
        "executed_onnx": False,
        "rendered_audio": False,
        "played_audio": False,
        "wrote_cache": False,
        "wrote_memory": False,
    }
    bound = {
        "tool": tool,
        "activation": activation,
        "handler": handler,
        "execution_authorized": False,
        "runtime_effects": runtime_effects,
    }
    return {
        "schema": "agent_bridge.story_command_static_registration_contract.v1",
        "status": "story_command_static_registration_contract_reviewable",
        **bound,
        "contract_sha256": _digest(bound),
        "claims": {
            "input_boundary_defined": True,
            "implementation_and_schema_hash_bound": True,
            "current_registry_collision_absent": True,
            "default_hidden": True,
            "static_registration_contract_ready": True,
            "runtime_registration_ready": False,
        },
        "next_gate": "isolated_story_preflight_adapter",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-receipt", type=Path, required=True)
    parser.add_argument("--preflight-schema", type=Path, required=True)
    parser.add_argument("--preflight-script", type=Path, required=True)
    parser.add_argument("--registry-source", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = build_registration_contract(
        preflight_receipt_path=args.preflight_receipt,
        preflight_schema_path=args.preflight_schema,
        preflight_script_path=args.preflight_script,
        registry_source_path=args.registry_source,
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
