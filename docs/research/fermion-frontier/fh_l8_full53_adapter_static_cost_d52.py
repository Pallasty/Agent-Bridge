#!/usr/bin/env python3
"""D52 static adapter-IR and allocation/operation-cost checker."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_full53_adapter_static_cost_d52_contract.json"
RESULT = HERE / "fh_l8_full53_adapter_static_cost_d52_result.json"


class D52Error(ValueError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D52Error(f"{path.name}: JSON object required")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function_node(path: Path, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise D52Error(f"expected exactly one function {name}")
    return matches[0]


def named_calls(node: ast.AST, name: str) -> int:
    return sum(
        isinstance(item, ast.Call)
        and (
            isinstance(item.func, ast.Name)
            and item.func.id == name
            or isinstance(item.func, ast.Attribute)
            and item.func.attr == name
        )
        for item in ast.walk(node)
    )


def check(contract_path: Path = CONTRACT) -> dict[str, Any]:
    contract = load(contract_path)
    if contract.get("contract_id") != "FH-L8-FULL53-ADAPTER-STATIC-COST-D52-V1":
        raise D52Error("contract id drift")
    if contract.get("analysis_class") != (
        "STATIC_ADAPTER_IR_ALLOCATION_CLASS_AND_OPERATION_COUNT_NO_EXECUTION"
    ):
        raise D52Error("analysis class drift")
    pins = contract.get("source_pins")
    if not isinstance(pins, Mapping) or len(pins) != 5:
        raise D52Error("source pin set drift")
    for name, expected in pins.items():
        path = HERE / name
        if not path.is_file() or sha256(path) != expected:
            raise D52Error(f"source pin mismatch: {name}")

    d51 = load(HERE / "fh_l8_full53_streaming_lifetime_d51_result.json")
    if d51.get("next_gate") != "D52_PRODUCTION_ADAPTER_STATIC_ALLOCATION_AND_OPERATION_COST_BOUND":
        raise D52Error("D51 next-gate drift")
    ir = contract.get("adapter_ir")
    expected_stages = [
        "decode_one_source_record",
        "invoke_bound_reduced_column",
        "encode_partition_records",
        "release_column_before_next_source",
    ]
    if not isinstance(ir, list) or [row.get("stage") for row in ir] != expected_stages:
        raise D52Error("adapter IR stage drift")
    if ir[-1].get("output") != "no_live_column_reference":
        raise D52Error("column lifetime release is not explicit")
    if ir[1].get("bound_symbol") != "_reduced_column":
        raise D52Error("scientific kernel binding drift")

    source = HERE / "fh_l8_symmetry_orbit_quotient_d5_checker.py"
    node = function_node(source, "_reduced_column")
    ast_contract = contract["kernel_ast_contract"]
    observed_ast = {
        "function": node.name,
        "positional_parameters": [argument.arg for argument in node.args.args],
        "sector_action_call_sites": named_calls(node, "_sector_action"),
        "canonical_info_call_sites": named_calls(node, "_canonical_info"),
        "fraction_call_sites": named_calls(node, "Fraction"),
        "for_loops": sum(isinstance(item, ast.For) for item in ast.walk(node)),
        "dict_literals": sum(isinstance(item, ast.Dict) for item in ast.walk(node)),
    }
    if observed_ast != ast_contract:
        raise D52Error("kernel AST contract drift")

    bounds = contract["operation_bounds"]
    sources = d51["source_records"]
    candidates = d51["candidate_visits"] // sources
    expected_bounds = {
        "source_records": sources,
        "candidate_actions_per_source": candidates,
        "canonical_info_calls_per_source_upper": 1 + candidates,
        "basis_images_per_canonical_info": 8,
        "fraction_constructions_per_candidate_upper": 2,
        "reduced_column_updates_per_source_upper": candidates,
        "total_canonical_info_calls_upper": sources * (1 + candidates),
        "total_basis_images_upper": sources * (1 + candidates) * 8,
        "total_fraction_constructions_upper": sources * candidates * 2,
        "total_reduced_column_updates_upper": sources * candidates,
    }
    if bounds != expected_bounds:
        raise D52Error("operation-bound arithmetic drift")

    unresolved = contract.get("unresolved_allocation_costs")
    if not isinstance(unresolved, list) or len(unresolved) != 7:
        raise D52Error("unresolved allocation-cost coverage drift")
    authority = contract["authority"]
    false_fields = {
        "executable_production_adapter_created",
        "full53_executed",
        "numeric_peak_memory_proven",
        "numeric_runtime_seconds_proven",
        "external_resource_reservation_admitted",
        "full53_execution_authorized",
    }
    if any(authority.get(field) is not False for field in false_fields):
        raise D52Error("authority unexpectedly open")
    if authority.get("packed_q3_reads") != 0 or authority.get("scientific_kernel_calls_executed") != 0:
        raise D52Error("D52 must execute no scientific action")

    return {
        "status": "VERIFIED_D52_STATIC_ADAPTER_IR_AND_OPERATION_BOUNDS_COSTS_UNRESOLVED",
        "adapter_ir_stage_count": len(ir),
        **expected_bounds,
        "unresolved_allocation_cost_count": len(unresolved),
        "executable_production_adapter_created": False,
        "packed_q3_reads": 0,
        "scientific_kernel_calls_executed": 0,
        "numeric_peak_memory_proven": False,
        "numeric_runtime_seconds_proven": False,
        "external_resource_reservation_admitted": False,
        "full53_execution_authorized": False,
        "next_gate": contract["next_gate"],
    }


def main() -> None:
    result = check()
    if load(RESULT) != result:
        raise D52Error("committed result drift")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
