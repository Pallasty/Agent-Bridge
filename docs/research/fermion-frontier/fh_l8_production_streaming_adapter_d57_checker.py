#!/usr/bin/env python3
"""Validate D57 without importing or invoking the scientific kernel."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_production_streaming_adapter_d57_contract.json"
RESULT = HERE / "fh_l8_production_streaming_adapter_d57_result.json"


class D57Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D57Error(f"{path.name}: object required")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def definitions(module: ast.Module) -> tuple[set[str], set[str]]:
    classes = {node.name for node in module.body if isinstance(node, ast.ClassDef)}
    functions = {node.name for node in module.body if isinstance(node, ast.FunctionDef)}
    return classes, functions


def function(module: ast.Module, name: str) -> ast.FunctionDef:
    matches = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise D57Error(f"function identity drift: {name}")
    return matches[0]


def validate(contract: Mapping[str, Any]) -> dict[str, Any]:
    if contract.get("contract_id") != "FH-L8-PRODUCTION-STREAMING-ADAPTER-D57-V1":
        raise D57Error("contract id drift")
    if contract.get("implementation_commit") != "14456707c4c286e52dc740f79f1eb1ee36774aae":
        raise D57Error("implementation chronology drift")
    pins = contract.get("source_pins")
    if not isinstance(pins, Mapping) or len(pins) != 9:
        raise D57Error("source pin set drift")
    for name, expected in pins.items():
        path = HERE / name
        if not path.is_file() or digest(path) != expected:
            raise D57Error(f"source pin mismatch: {name}")

    d56 = load(HERE / "fh_l8_resource_closure_plan_d56_contract.json")
    if d56.get("next_gate") != "D57_PRODUCTION_STREAMING_ADAPTER_IMPLEMENTATION_CONTRACT":
        raise D57Error("D56 handoff drift")
    if contract.get("next_gates") != d56["parallelism"]["after_D57_may_run_in_parallel"]:
        raise D57Error("D57 parallel handoff drift")

    module = tree(HERE / "fh_l8_production_streaming_adapter_d57.py")
    observed_classes, observed_functions = definitions(module)
    interfaces = contract.get("adapter_interfaces")
    if (
        not isinstance(interfaces, Mapping)
        or set(interfaces.get("classes", [])) - observed_classes
        or set(interfaces.get("functions", [])) - observed_functions
    ):
        raise D57Error("adapter interface drift")
    process = function(module, "process_one_source")
    clear_in_finally = any(
        isinstance(node, ast.Try)
        and any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "clear"
            for final in node.finalbody
            for child in ast.walk(final)
        )
        for node in ast.walk(process)
    )
    if not clear_in_finally:
        raise D57Error("column release is not protected by finally")
    full53 = function(module, "run_full53")
    if not any(isinstance(node, ast.Raise) for node in ast.walk(full53)):
        raise D57Error("full53 entrypoint is not fail-closed")
    forbidden_calls = {"open", "read_bytes", "write_bytes", "unlink", "replace", "_reduced_column"}
    observed_calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    if observed_calls & forbidden_calls:
        raise D57Error("adapter contains forbidden I/O or scientific call")
    formats = contract.get("record_formats")
    if (
        formats.get("source_bytes") != 32
        or formats.get("spill_bytes") != 32
        or formats.get("partition_count") != 256
        or formats.get("scaled_denominator") != 8
    ):
        raise D57Error("record format drift")
    binding = contract.get("kernel_binding")
    if (
        binding.get("future_symbol") != "_reduced_column"
        or binding.get("D57_imports_or_invokes_scientific_kernel") is not False
        or binding.get("production_invocation_authorized") is not False
    ):
        raise D57Error("kernel authority drift")
    tests = contract.get("synthetic_mock_tests")
    if tests != {
        "test_count": 7, "packed_q3_file_reads": 0, "scientific_kernel_calls": 0,
        "production_io_operations": 0, "object_measurements": 0,
    }:
        raise D57Error("test boundary drift")
    authority = contract.get("authority")
    if authority.get("production_adapter_interfaces_implemented") is not True:
        raise D57Error("interface implementation missing")
    false_fields = (
        "production_adapter_resource_ready", "full53_execution_authorized",
        "production_io_executed", "numeric_peak_memory_proven",
        "numeric_runtime_seconds_proven", "external_resource_reservation_admitted",
    )
    zero_fields = ("packed_q3_reads", "scientific_kernel_calls_executed", "object_measurements_executed")
    if any(authority.get(key) is not False for key in false_fields):
        raise D57Error("authority unexpectedly open")
    if any(authority.get(key) != 0 for key in zero_fields):
        raise D57Error("D57 execution count drift")
    return {
        "status": "VERIFIED_D57_STREAMING_ADAPTER_INTERFACES_FULL53_FAIL_CLOSED",
        "adapter_class_count": len(interfaces["classes"]),
        "adapter_function_count": len(interfaces["functions"]),
        "lifecycle_stage_count": len(contract["lifecycle"]),
        "synthetic_mock_test_count": tests["test_count"],
        "source_record_bytes": formats["source_bytes"],
        "spill_record_bytes": formats["spill_bytes"],
        "partition_count": formats["partition_count"],
        "maximum_merge_fan_in": 32,
        "column_release_in_finally": True,
        "production_adapter_interfaces_implemented": True,
        **{key: authority[key] for key in false_fields},
        **{key: authority[key] for key in zero_fields},
        "next_gate_count": len(contract["next_gates"]),
    }


def verify() -> dict[str, Any]:
    expected = validate(load(CONTRACT))
    if load(RESULT) != expected:
        raise D57Error("committed result drift")
    return expected


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
