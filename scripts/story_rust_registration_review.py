#!/usr/bin/env python3
"""Build the fail-closed Rust `/story` MCP registration review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


TOOL_NAME = "story_command_preflight"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _parity_is_valid(receipt: dict[str, Any]) -> bool:
    return (
        receipt.get("status") == "rust_story_preflight_adapter_parity_verified"
        and all(receipt.get("parity", {}).values())
        and all(receipt.get("negative_controls", {}).values())
        and not any(receipt.get("scope", {}).values())
        and not any(receipt.get("runtime_effects", {}).values())
        and receipt.get("next_gate")
        == "owner_authorized_rust_story_registration_review"
    )


def build_registration_review(
    *,
    registry_path: Path,
    lib_path: Path,
    story_module_path: Path,
    parity_receipt_path: Path,
    prior_registration_receipt_path: Path,
) -> dict[str, Any]:
    registry_path = Path(registry_path)
    lib_path = Path(lib_path)
    story_module_path = Path(story_module_path)
    parity_receipt_path = Path(parity_receipt_path)
    prior_registration_receipt_path = Path(prior_registration_receipt_path)

    registry_source = registry_path.read_text(encoding="utf-8")
    lib_source = lib_path.read_text(encoding="utf-8")
    story_source = story_module_path.read_text(encoding="utf-8")

    if re.search(rf"['\"]{re.escape(TOOL_NAME)}['\"]", registry_source):
        raise ValueError(f"tool name collision: {TOOL_NAME}")

    parity = _load(parity_receipt_path)
    if not _parity_is_valid(parity):
        raise ValueError("S5ZM parity evidence invalid")
    if "pub fn build_story_command_preflight" not in story_source:
        raise ValueError("native story preflight entrypoint missing")

    prior = _load(prior_registration_receipt_path)
    prior_registry_sha = prior.get("activation", {}).get("registry_source_sha256")
    current_registry_sha = _sha256(registry_path)

    story_module_exported = bool(
        re.search(
            r"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+story_contract\s*;",
            lib_source,
        )
    )
    bounded_source_admission = all(
        marker in story_source
        for marker in ("MAX_STORY_SOURCE_BYTES", "STORY_SOURCE_ALLOWED_ROOT")
    )
    evidence_bundle_resolver = all(
        marker in story_source + lib_source + registry_source
        for marker in ("StoryEvidenceBundle", "resolve_story_evidence")
    )
    cancellation_contract = all(
        marker in story_source + lib_source + registry_source
        for marker in ("StoryPreflightCancellation", "tokio::select!")
    )

    blocker_probes = [
        ("bounded_source_admission_missing", bounded_source_admission),
        ("configured_evidence_bundle_resolver_missing", evidence_bundle_resolver),
        ("async_cancellation_contract_missing", cancellation_contract),
    ]
    blockers = [name for name, present in blocker_probes if not present]

    return {
        "schema": "agent_bridge.story_rust_registration_review.v1",
        "status": "rust_story_registration_review_complete",
        "decision": {
            "selected": "harden_native_adapter_before_registration",
            "registration_implementation_admitted": not blockers,
            "rejected_options": [
                "register_current_adapter_now",
                "reintroduce_python_adapter",
            ],
        },
        "evidence": {
            "s5zm_full_parity_verified": True,
            "current_registry_collision": False,
            "prior_registry_provenance_drift": prior_registry_sha
            != current_registry_sha,
            "story_module_exported": story_module_exported,
            "registry_source_path": str(registry_path.resolve()),
            "registry_source_sha256": current_registry_sha,
            "prior_registry_source_sha256": prior_registry_sha,
            "lib_source_path": str(lib_path.resolve()),
            "lib_source_sha256": _sha256(lib_path),
            "story_module_path": str(story_module_path.resolve()),
            "story_module_sha256": _sha256(story_module_path),
            "s5zm_receipt_path": str(parity_receipt_path.resolve()),
            "s5zm_receipt_sha256": _sha256(parity_receipt_path),
        },
        "hardening_probes": {
            "bounded_source_admission": bounded_source_admission,
            "configured_evidence_bundle_resolver": evidence_bundle_resolver,
            "async_cancellation_contract": cancellation_contract,
        },
        "blockers": blockers,
        "proposed_surface": {
            "tool_name": TOOL_NAME,
            "tier": "Niche",
            "default_exposed": False,
            "codex_essential_exposed": False,
            "codex_voice_exposed": False,
            "activation_env": "AB_STORY_COMMAND_PREFLIGHT_ENABLE",
            "activation_env_required_value": "1",
        },
        "hardening_contract": {
            "source_admission": "canonical allowed root plus fixed byte ceiling and strict UTF-8",
            "evidence_resolution": "configured hash-bound accepted evidence bundle",
            "cancellation": "async caller cancellation must stop owned blocking work",
            "tool_failure": "return a structured tool error without panic",
        },
        "execution_authorized": False,
        "runtime_effects": {
            "modified_rust_registry": False,
            "registered_story_command": False,
            "loaded_model": False,
            "executed_onnx": False,
            "rendered_audio": False,
            "played_audio": False,
            "wrote_cache": False,
            "wrote_memory": False,
        },
        "next_gate": "rust_story_preflight_adapter_hardening",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--lib", type=Path, required=True)
    parser.add_argument("--story-module", type=Path, required=True)
    parser.add_argument("--parity-receipt", type=Path, required=True)
    parser.add_argument("--prior-registration-receipt", type=Path, required=True)
    args = parser.parse_args()
    result = build_registration_review(
        registry_path=args.registry,
        lib_path=args.lib,
        story_module_path=args.story_module,
        parity_receipt_path=args.parity_receipt,
        prior_registration_receipt_path=args.prior_registration_receipt,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
