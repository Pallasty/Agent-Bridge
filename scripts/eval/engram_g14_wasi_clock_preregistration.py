#!/usr/bin/env python3
"""Render the bounded receipt for the static G1.4 WASI clock preregistration.

The renderer reads one checked-in public JSON fixture and writes one JSON line.
It performs no network access, dependency resolution, component build or run,
clock read, sleep, entropy read, repository write, or authority transition.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    REPO_ROOT
    / "scripts/eval/fixtures/engram_g14_wasi_clock_preregistration_v0.json"
)
CONTRACT_SCHEMA = "agent_bridge.engram_g14_wasi_clock_preregistration.v0"
RECEIPT_SCHEMA = "agent_bridge.engram_g14_wasi_clock_preregistration_receipt.v0"


class PreregistrationError(RuntimeError):
    """Closed validation error for this public-static renderer."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def load_contract() -> dict[str, Any]:
    value = json.loads(CONTRACT_PATH.read_bytes())
    if not isinstance(value, dict):
        raise PreregistrationError("contract must be a JSON object")
    if value.get("schema") != CONTRACT_SCHEMA:
        raise PreregistrationError("unexpected contract schema")
    return value


def render_receipt(contract: dict[str, Any]) -> dict[str, Any]:
    scope = contract["scope"]
    decision = contract["decision"]
    integrity = contract["acceptance_integrity"]
    review_targets = contract["public_review_target_pins"]
    component = contract["component_abi_template"]
    clock = contract["deterministic_clock_state_machine"]
    replay = contract["transcript_and_replay_contract"]
    return {
        "schema": RECEIPT_SCHEMA,
        "gate": contract["gate"],
        "mode": contract["mode"],
        "status": contract["status"],
        "verdict": decision["verdict"],
        "authority_class": scope["authority_class"],
        "contract_sha256": hashlib.sha256(canonical_json(contract)).hexdigest(),
        "review_target_version": review_targets["wasmtime_release"]["version"],
        "review_target_commit": review_targets["wasmtime_release"]["git_commit"],
        "review_target_crate_count": len(review_targets["crates_io_rows_in_order"]),
        "review_target_source_pin_count": len(review_targets["source_rows_in_order"]),
        "allowed_import_count": len(component["allowed_imports_in_exact_order"]),
        "clock_quantum_nanoseconds": clock["quantum_nanoseconds"],
        "fresh_future_instance_count": replay["fresh_instance_count"],
        "built_in_wasmtime_timer_host_acceptable": decision[
            "built_in_wasmtime_timer_host_acceptable"
        ],
        "runtime_or_dependency_adopted": decision["runtime_or_dependency_adopted"],
        "component_built_or_executed": scope["component_built_or_executed"],
        "build_or_run_authorized": decision["build_or_run_authorized"],
        "candidate_or_private_authorized": decision[
            "candidate_or_private_authorized"
        ],
        "runtime_or_deployment_authorized": decision[
            "runtime_or_deployment_authorized"
        ],
        "g1_4_execution_open": decision["g1_4_execution_open"],
        "checker_self_authenticating": integrity["checker_self_authenticating"],
        "out_of_band_acceptance_pin_required": integrity[
            "independent_out_of_band_commit_and_file_hash_pin_required"
        ],
        "no_authority_before_verified_pin": integrity[
            "no_authority_before_verified_pin"
        ],
        "only_permitted_successor": decision["only_permitted_successor"],
    }


def main(argv: list[str]) -> int:
    if argv:
        raise PreregistrationError("renderer accepts no arguments")
    encoded = canonical_json(render_receipt(load_contract()))
    if len(encoded) > 4096:
        raise PreregistrationError("receipt exceeds the 4096-byte public bound")
    sys.stdout.buffer.write(encoded + b"\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (OSError, ValueError, KeyError, TypeError, PreregistrationError) as exc:
        print(f"engram G1.4 WASI preregistration: invalid: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
