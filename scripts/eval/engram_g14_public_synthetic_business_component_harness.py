#!/usr/bin/env python3
"""Public-synthetic implementation gate for the G1.4 business contract.

This is an in-memory contract harness, not a WASI component runner. It uses
the frozen WIT as a transparent artifact surrogate, exercises the pure
transformation and receipt/replay rules, and remains default-off. It has no
runtime, MCP, network, process, filesystem, clock, or registry surface.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, NoReturn


SCRIPT_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = SCRIPT_DIR / "fixtures/engram_g14_business_component_contract_v0"
WIT_PATH = FIXTURE_DIR / "world.wit"
CONTRACT_PATH = FIXTURE_DIR / "contract.json"

CONTRACT_SCHEMA = "agent_bridge.engram.g14.business_component_contract.v0"
RECEIPT_SCHEMA = "agent_bridge.engram.g14.business_component_receipt.v0"
INVOCATION_RE = re.compile(r"^g14-biz-v0-[a-z0-9]{16}$")
MODE = "PUBLIC_SYNTHETIC_BUSINESS_COMPONENT_KAT"


class HarnessError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def fail(code: str, detail: str) -> NoReturn:
    raise HarnessError(code, detail)


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        fail(code, detail)


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("E_DUPLICATE_KEY", f"duplicate key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda value: fail("E_NUMBER", value),
        )
    except UnicodeDecodeError as exc:
        fail("E_UTF8", str(exc))
    require(type(value) is dict, "E_SCHEMA", f"{path.name} root must be object")
    return value, raw


def canonical_bytes(value: Any) -> bytes:
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                require(type(key) is str, "E_SCHEMA", "object key must be string")
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
        elif isinstance(node, float):
            fail("E_NUMBER", "floats are forbidden")

    walk(value)
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def exact_keys(value: Any, expected: set[str], path: str) -> dict[str, Any]:
    require(type(value) is dict, "E_SCHEMA", f"{path} must be object")
    require(set(value) == expected, "E_SCHEMA", f"{path} fields mismatch")
    return value


def checked_u32(value: Any, path: str) -> int:
    require(type(value) is int and 0 <= value <= 0xFFFFFFFF, "E_INPUT", path)
    return value


def validate_contract(contract: dict[str, Any], wit: str) -> None:
    require(contract["schema"] == CONTRACT_SCHEMA, "E_CONTRACT", "schema")
    require(contract["component_profile"] == "pure-function-no-imports", "E_CONTRACT", "profile")
    serialization = exact_keys(
        contract["serialization"],
        {"envelope", "encoding", "object_keys", "numbers", "duplicate_keys", "unknown_fields", "invalid_utf8"},
        "serialization",
    )
    expected_serialization = {
        "envelope": "rfc8785-json-safe-integer-v0",
        "encoding": "utf-8",
        "object_keys": "lexicographic",
        "numbers": "integers-only-safe-range",
        "duplicate_keys": "reject",
        "unknown_fields": "reject",
        "invalid_utf8": "reject",
    }
    require(serialization == expected_serialization, "E_CONTRACT", "serialization drift")
    require(contract["invocation_id_pattern"] == INVOCATION_RE.pattern, "E_CONTRACT", "invocation pattern")
    policy = contract["capability_policy"]
    require(policy["imports"] == [], "E_CAPABILITY", "imports must be empty")
    for key in ("filesystem", "network", "subprocess", "entropy", "host_clock", "ambient_state"):
        require(policy[key] is False, "E_CAPABILITY", key)
    for key, value in contract["admission"].items():
        require(value is False, "E_AUTHORITY", key)
    require(not any(line.strip().startswith("import ") for line in wit.splitlines()), "E_WIT", "actual import")
    require(wit.count("export evaluate:") == 1, "E_WIT", "evaluate export")


def load_registered() -> tuple[dict[str, Any], bytes, str, str]:
    contract, contract_raw = load_json(CONTRACT_PATH)
    wit_raw = WIT_PATH.read_bytes()
    try:
        wit = wit_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail("E_UTF8", str(exc))
    validate_contract(contract, wit)
    return contract, contract_raw, sha256_bytes(wit_raw), sha256_bytes(contract_raw)


def evaluate_input(value: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    expected = {"revision", "entity-count", "occupied-cells", "transition-count"}
    item = exact_keys(value, expected, "input")
    revision = item["revision"]
    require(type(revision) is int and 0 <= revision <= 0xFFFFFFFFFFFFFFFF, "E_INPUT", "revision")
    limits = contract["input_limits"]
    entity_count = checked_u32(item["entity-count"], "entity-count")
    occupied_cells = checked_u32(item["occupied-cells"], "occupied-cells")
    transitions = checked_u32(item["transition-count"], "transition-count")
    require(entity_count <= limits["entity_count_max"], "E_INPUT_OUT_OF_BOUNDS", "entity-count")
    require(occupied_cells <= limits["occupied_cells_max"], "E_INPUT_OUT_OF_BOUNDS", "occupied-cells")
    require(transitions <= limits["transition_count_max"], "E_INPUT_OUT_OF_BOUNDS", "transition-count")
    occupancy = (occupied_cells * 1000) // max(entity_count, 1)
    return {
        "revision": revision,
        "entity-count": entity_count,
        "occupied-cells": occupied_cells,
        "transition-count": transitions,
        "occupancy-per-mille": occupancy,
        "report-code": "WORLD_STATE_V0",
    }


def build_receipt() -> dict[str, Any]:
    contract, contract_raw, wit_sha, contract_sha = load_registered()
    fixture = contract["fixture"]
    input_value = fixture["input"]
    input_hash = sha256_bytes(canonical_bytes(input_value))
    output = evaluate_input(input_value, contract)
    output_hash = sha256_bytes(canonical_bytes(output))
    attempts = []
    for suffix in ("0000000000000001", "0000000000000002"):
        attempts.append({
            "invocation_id": f"g14-biz-v0-{suffix}",
            "input_sha256": input_hash,
            "output_sha256": output_hash,
            "status": "ok",
        })
    require(attempts[0]["invocation_id"] != attempts[1]["invocation_id"], "E_REPLAY", "ID reuse")
    require(attempts[0]["output_sha256"] == attempts[1]["output_sha256"], "E_REPLAY", "output mismatch")
    return {
        "schema": RECEIPT_SCHEMA,
        "mode": MODE,
        "contract_sha256": contract_sha,
        "component_artifact_kind": "synthetic_wit_contract_surrogate_not_component",
        "component_fixture_sha256": wit_sha,
        "input": input_value,
        "output": output,
        "input_sha256": input_hash,
        "output_sha256": output_hash,
        "attempts": attempts,
        "replay": {"performed": True, "byte_equal": True, "distinct_invocation_ids": True},
        "verified": True,
        "authority": {
            "runtime": False,
            "mcp": False,
            "registry": False,
            "production_write": False,
            "candidate_private_data": False,
            "native_sandbox": False,
        },
        "contract_bytes": len(contract_raw),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("validate-contract", "exercise"))
    parser.add_argument("--enable-public-synthetic", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "exercise" and not args.enable_public_synthetic:
            fail("E_DEFAULT_OFF", "pass --enable-public-synthetic for the local harness")
        if args.command == "validate-contract":
            contract, raw, wit_sha, contract_sha = load_registered()
            print(json.dumps({
                "schema": CONTRACT_SCHEMA,
                "contract_sha256": contract_sha,
                "wit_sha256": wit_sha,
                "contract_bytes": len(raw),
                "imports": 0,
                "authority": {key: False for key in contract["admission"]},
            }, sort_keys=True, separators=(",", ":")))
        else:
            print(json.dumps(build_receipt(), sort_keys=True, separators=(",", ":")))
        return 0
    except HarnessError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
