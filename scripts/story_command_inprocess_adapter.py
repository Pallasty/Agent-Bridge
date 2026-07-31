#!/usr/bin/env python3
"""Call the accepted `/story` preflight directly in one Python process."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shlex
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
EXPECTED_REQUEST_FIELDS = {"source_path", "start", "dry_run"}


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


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required:{path}")
    return value


def _validate_request(request: dict[str, Any]) -> None:
    if set(request) != EXPECTED_REQUEST_FIELDS:
        raise ValueError("adapter request fields invalid")
    if request.get("dry_run") is not True:
        raise ValueError("adapter requires dry_run=true")
    source_path = request.get("source_path")
    if not isinstance(source_path, str) or not source_path:
        raise ValueError("adapter source_path invalid")
    start = request.get("start")
    if not isinstance(start, dict):
        raise ValueError("adapter start selector invalid")
    if start == {"kind": "from_start"}:
        return
    if (
        set(start) == {"kind", "chapter"}
        and start.get("kind") == "chapter"
        and isinstance(start.get("chapter"), int)
        and not isinstance(start.get("chapter"), bool)
        and start["chapter"] >= 1
    ):
        return
    raise ValueError("adapter start selector invalid")


def _validate_registration_contract(
    contract: dict[str, Any], *, preflight_script_path: Path
) -> None:
    bound = {
        key: contract.get(key)
        for key in (
            "tool",
            "activation",
            "handler",
            "execution_authorized",
            "runtime_effects",
        )
    }
    claims = contract.get("claims", {})
    if (
        contract.get("status")
        != "story_command_static_registration_contract_reviewable"
        or contract.get("contract_sha256") != _digest(bound)
        or contract.get("execution_authorized") is not False
        or any(contract.get("runtime_effects", {}).values())
        or claims.get("static_registration_contract_ready") is not True
        or claims.get("runtime_registration_ready") is not False
        or contract.get("next_gate") != "isolated_story_preflight_adapter"
    ):
        raise ValueError("registration contract invalid")
    handler = contract.get("handler", {})
    if handler.get("subprocess_allowed") is not False:
        raise ValueError("registration contract subprocess boundary invalid")
    if _sha256_file(preflight_script_path) != handler.get(
        "preflight_script_sha256"
    ):
        raise ValueError("preflight script SHA-256 mismatch")
    schema_path = Path(handler.get("preflight_schema_path", ""))
    if _sha256_file(schema_path) != handler.get("preflight_schema_sha256"):
        raise ValueError("preflight schema SHA-256 mismatch")
    accepted_receipt = _read_json(
        Path(handler.get("accepted_preflight_receipt_path", ""))
    )
    if accepted_receipt.get("preflight_sha256") != handler.get(
        "accepted_preflight_sha256"
    ):
        raise ValueError("accepted preflight SHA-256 mismatch")
    activation = contract.get("activation", {})
    registry_path = Path(activation.get("registry_source_path", ""))
    if _sha256_file(registry_path) != activation.get("registry_source_sha256"):
        raise ValueError("registry source SHA-256 mismatch")


def _command_from_request(request: dict[str, Any]) -> str:
    source = shlex.quote(request["source_path"])
    start = request["start"]
    if start["kind"] == "from_start":
        return f"/story {source} from-start"
    return f"/story {source} chapter {start['chapter']}"


def run_inprocess_story_preflight(
    request: dict[str, Any],
    *,
    registration_contract_path: Path,
    voice_plan_path: Path,
    mapping_path: Path,
    role_acceptance_path: Path,
    continuity_acceptance_path: Path,
    preflight_script_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Invoke S5ZF directly without a shell, child process, or MCP registry."""

    _validate_request(request)
    script_path = preflight_script_path or (
        SCRIPT_DIR / "story_command_integration_preflight.py"
    )
    contract = _read_json(registration_contract_path)
    _validate_registration_contract(contract, preflight_script_path=script_path)
    preflight = _load_module(script_path, "_story_preflight_for_inprocess_adapter")
    result = preflight.build_story_command_preflight(
        _command_from_request(request),
        voice_plan=_read_json(voice_plan_path),
        mapping=_read_json(mapping_path),
        role_acceptance=_read_json(role_acceptance_path),
        continuity_acceptance=_read_json(continuity_acceptance_path),
    )
    trace = {
        "adapter": "python_direct_function_call",
        "same_process": True,
        "used_shell": False,
        "spawned_subprocess": False,
        "registered_mcp_tool": False,
    }
    return result, trace


def build_adapter_receipt(
    request: dict[str, Any],
    **paths: Path,
) -> dict[str, Any]:
    """Produce durable evidence for one same-process adapter call."""

    preflight, trace = run_inprocess_story_preflight(request, **paths)
    contract = _read_json(paths["registration_contract_path"])
    bound = {
        "request": request,
        "registration_contract_sha256": contract["contract_sha256"],
        "adapter_script_sha256": _sha256_file(Path(__file__)),
        "preflight_sha256": preflight["preflight_sha256"],
        "trace": trace,
    }
    return {
        "schema": "agent_bridge.story_command_inprocess_adapter.v1",
        "status": "python_inprocess_adapter_verified",
        "request": request,
        "registration_contract_sha256": contract["contract_sha256"],
        "adapter": {
            "script_path": str(Path(__file__).resolve()),
            "script_sha256": bound["adapter_script_sha256"],
            **trace,
        },
        "preflight": preflight,
        "adapter_receipt_sha256": _digest(bound),
        "runtime_effects": {
            "modified_rust_registry": False,
            "registered_story_command": False,
            "spawned_subprocess": False,
            "used_shell": False,
            "loaded_model": False,
            "executed_onnx": False,
            "rendered_audio": False,
            "played_audio": False,
            "wrote_cache": False,
            "wrote_memory": False,
        },
        "claims": {
            "python_same_process_direct_call": True,
            "shell_or_subprocess_required": False,
            "rust_inprocess_adapter_proven": False,
            "mcp_tool_registered": False,
            "production_story_command_ready": False,
        },
        "next_gate": "rust_inprocess_story_preflight_design",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-path", required=True)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--from-start", action="store_true")
    selector.add_argument("--chapter", type=int)
    parser.add_argument("--registration-contract", type=Path, required=True)
    parser.add_argument("--voice-plan", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--role-acceptance", type=Path, required=True)
    parser.add_argument("--continuity-acceptance", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    start = (
        {"kind": "from_start"}
        if args.from_start
        else {"kind": "chapter", "chapter": args.chapter}
    )
    result = build_adapter_receipt(
        {"source_path": args.source_path, "start": start, "dry_run": True},
        registration_contract_path=args.registration_contract,
        voice_plan_path=args.voice_plan,
        mapping_path=args.mapping,
        role_acceptance_path=args.role_acceptance,
        continuity_acceptance_path=args.continuity_acceptance,
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
