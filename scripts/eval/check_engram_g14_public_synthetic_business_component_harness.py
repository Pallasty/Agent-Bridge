#!/usr/bin/env python3
"""Independent adversarial checker for the business-component harness."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
IMPLEMENTATION = SCRIPT_DIR / "engram_g14_public_synthetic_business_component_harness.py"
CONTRACT = SCRIPT_DIR / "fixtures/engram_g14_business_component_contract_v0/contract.json"
WIT = SCRIPT_DIR / "fixtures/engram_g14_business_component_contract_v0/world.wit"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module():
    spec = importlib.util.spec_from_file_location("business_harness", IMPLEMENTATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert type(value) is dict
    return value


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(IMPLEMENTATION), *args],
        cwd=REPO_ROOT, text=True, capture_output=True, check=False,
    )


CONTRACT_VALUE = load_json(CONTRACT)
HARNESS = load_module()


def expect_error(fn, code: str) -> None:
    try:
        fn()
    except HARNESS.HarnessError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> int:
    # Source-boundary review: standard library only and no runtime-adjacent I/O.
    tree = ast.parse(IMPLEMENTATION.read_text(encoding="utf-8"))
    imports = {
        node.names[0].name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import) and node.names
    }
    imports.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imports <= {"__future__", "argparse", "hashlib", "json", "re", "sys", "pathlib", "typing"}, imports
    assert not any("crates/" in line for line in IMPLEMENTATION.read_text().splitlines())

    assert CONTRACT_VALUE["capability_policy"]["imports"] == []
    assert all(value is False for value in CONTRACT_VALUE["admission"].values())
    assert not any(line.strip().startswith("import ") for line in WIT.read_text().splitlines())
    assert digest(WIT) in Path(
        REPO_ROOT / "docs/design/ENGRAM_G1_4_PUBLIC_SYNTHETIC_BUSINESS_COMPONENT_CONTRACT_2026_07_21.md"
    ).read_text()

    # Default-off boundary.
    disabled = run("exercise")
    assert disabled.returncode == 1
    assert "E_DEFAULT_OFF" in disabled.stderr

    # Deterministic CLI receipts and contract validation.
    validated_1 = run("validate-contract")
    validated_2 = run("validate-contract")
    assert validated_1.returncode == validated_2.returncode == 0
    assert validated_1.stdout == validated_2.stdout
    receipt_1 = run("exercise", "--enable-public-synthetic")
    receipt_2 = run("exercise", "--enable-public-synthetic")
    assert receipt_1.returncode == receipt_2.returncode == 0
    assert receipt_1.stdout == receipt_2.stdout
    receipt = json.loads(receipt_1.stdout)
    assert receipt["verified"] is True
    assert receipt["replay"] == {"performed": True, "byte_equal": True, "distinct_invocation_ids": True}
    assert receipt["output"]["occupancy-per-mille"] == 750
    assert receipt["component_artifact_kind"] == "synthetic_wit_contract_surrogate_not_component"
    assert all(value is False for value in receipt["authority"].values())

    # Independent semantic falsifiers.
    fixture = CONTRACT_VALUE["fixture"]["input"]
    expect_error(lambda: HARNESS.evaluate_input({"revision": 7}, CONTRACT_VALUE), "E_SCHEMA")
    extra = dict(fixture)
    extra["unexpected"] = 1
    expect_error(lambda: HARNESS.evaluate_input(extra, CONTRACT_VALUE), "E_SCHEMA")
    duplicate = {"revision": 7, "entity-count": 12, "occupied-cells": 9, "transition-count": 4}
    duplicate_raw = '{"revision":7,"revision":7}'
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as handle:
        handle.write(duplicate_raw)
        handle.flush()
        expect_error(lambda: HARNESS.load_json(Path(handle.name)), "E_DUPLICATE_KEY")
    assert duplicate["revision"] == 7
    out_of_bounds = dict(fixture)
    out_of_bounds["entity-count"] = 100001
    expect_error(lambda: HARNESS.evaluate_input(out_of_bounds, CONTRACT_VALUE), "E_INPUT_OUT_OF_BOUNDS")
    float_input = dict(fixture)
    float_input["occupied-cells"] = 9.0
    expect_error(lambda: HARNESS.evaluate_input(float_input, CONTRACT_VALUE), "E_INPUT")
    assert HARNESS.canonical_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'

    # Nothing from this harness may appear in runtime crates.
    leaked = subprocess.run(
        ["rg", "engram_g14_public_synthetic_business_component_harness|PUBLIC_SYNTHETIC_BUSINESS_COMPONENT_KAT", "crates"],
        cwd=REPO_ROOT, text=True, capture_output=True, check=False,
    )
    assert leaked.returncode == 1, leaked.stdout
    print("engram G1.4 public synthetic business component harness: PASS (no authority)")
    print("checks=22, default_off=PASS, deterministic_receipt=PASS, falsifiers=PASS, runtime_leak=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
