#!/usr/bin/env python3
"""D50 static FH-L8 kernel-binding and structural fan-out checker."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_full53_kernel_fanout_d50_contract.json"


class D50Error(ValueError):
    pass


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D50Error(f"{path.name}: JSON object required")
    return value


def _sha(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise D50Error(f"expected exactly one function {name}")
    return matches[0]


def check(contract_path: Path = CONTRACT) -> dict[str, Any]:
    contract = _load(contract_path)
    if contract.get("contract_id") != "FH-L8-FULL53-KERNEL-FANOUT-D50-V1":
        raise D50Error("contract id drift")
    if contract.get("analysis_class") != (
        "STATIC_SOURCE_BOUND_KERNEL_ADAPTER_AND_STRUCTURAL_FANOUT_PROOF_NO_EXECUTION"
    ):
        raise D50Error("analysis class drift")

    pins = contract.get("source_pins")
    if not isinstance(pins, Mapping):
        raise D50Error("source_pins object required")
    for name, expected in pins.items():
        path = HERE / name
        if not path.is_file() or _sha(path) != expected:
            raise D50Error(f"source pin mismatch: {name}")

    binding = contract["kernel_binding"]
    source = (HERE / binding["module"]).read_text(encoding="utf-8")
    function = _function(ast.parse(source), binding["symbol"])
    parameters = [argument.arg for argument in function.args.args]
    if parameters != binding["parameters"]:
        raise D50Error("kernel parameter boundary drift")
    calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == binding["required_call"]
    ]
    if len(calls) != 1:
        raise D50Error("kernel sector-action binding drift")
    if binding["production_adapter_implemented"] is not False:
        raise D50Error("D50 must not claim an implemented production adapter")

    d26 = _load(HERE / "fh_l8_kernel_fixture_boundary_d26_result.json")
    d49 = _load(HERE / "fh_l8_controlled_resource_stability_d49_result.json")
    d5 = _load(HERE / "fh_l8_symmetry_orbit_quotient_d5_result.json")
    d22_contract = _load(HERE / "fh_l8_tiny_recovery_d22_contract.json")
    d22_result = _load(HERE / "fh_l8_tiny_recovery_d22_result.json")
    if d26.get("structural_candidate_action_upper_bound") != 225:
        raise D50Error("D26 structural candidate bound drift")
    if d49.get("full53_extrapolation_forbidden") is not True:
        raise D50Error("D49 full53 non-extrapolation boundary drift")
    if d49.get("resource_stability_decision") != "stabilized":
        raise D50Error("D49 stability decision drift")
    if d22_contract["production_authority"]["full_53_shard_execution_authorized"] is not False:
        raise D50Error("D22 production authority unexpectedly open")
    if d22_result["production_authority"].get("production_scientific_kernel_calls") != 0:
        raise D50Error("D22 scientific call boundary drift")

    shape = contract["full53_shape"]
    if shape["source_records"] != (
        shape["full_shards"] * shape["full_shard_records"]
        + shape["last_shard_records"]
    ):
        raise D50Error("source shard arithmetic drift")
    if shape["source_shards"] != shape["full_shards"] + 1:
        raise D50Error("source shard count drift")
    if d5["resource_projection"]["candidate_actions_per_representative"] != (
        shape["candidate_actions_per_source"]
    ):
        raise D50Error("D5 candidate-actions-per-source drift")
    if d5["resource_projection"]["next_action_upper_bound"] != (
        shape["source_records"] * shape["candidate_actions_per_source"]
    ):
        raise D50Error("D5 total candidate upper bound drift")

    expected = {
        "full_shard_candidate_actions": (
            shape["full_shard_records"] * shape["candidate_actions_per_source"]
        ),
        "last_shard_candidate_actions": (
            shape["last_shard_records"] * shape["candidate_actions_per_source"]
        ),
        "total_candidate_actions": (
            shape["source_records"] * shape["candidate_actions_per_source"]
        ),
    }
    expected.update(
        {
            "full_shard_spill_bytes": (
                expected["full_shard_candidate_actions"] * shape["spill_record_bytes"]
            ),
            "last_shard_spill_bytes": (
                expected["last_shard_candidate_actions"] * shape["spill_record_bytes"]
            ),
            "total_spill_bytes": (
                expected["total_candidate_actions"] * shape["spill_record_bytes"]
            ),
        }
    )
    if expected != contract["expected_structural_bounds"]:
        raise D50Error("structural bound arithmetic drift")

    boundary = contract["proof_boundary"]
    required_false = {
        "full53_execution_authorized",
        "streaming_peak_memory_proven",
        "worst_case_runtime_proven",
        "external_resource_reservation_admitted",
    }
    if any(boundary.get(field) is not False for field in required_false):
        raise D50Error("proof boundary unexpectedly open")
    if boundary.get("scientific_kernel_calls") != 0 or boundary.get("packed_q3_reads") != 0:
        raise D50Error("D50 must execute no scientific action")

    return {
        "status": "VERIFIED_D50_SOURCE_BOUND_KERNEL_AND_STRUCTURAL_FANOUT_CONTRACT",
        "kernel_symbol": binding["symbol"],
        "kernel_sector_action_binding_verified": True,
        "production_adapter_implemented": False,
        "source_records": shape["source_records"],
        "source_shards": shape["source_shards"],
        "candidate_actions_per_source": shape["candidate_actions_per_source"],
        **expected,
        "scientific_kernel_calls": 0,
        "packed_q3_reads": 0,
        "full53_execution_authorized": False,
        "streaming_peak_memory_proven": False,
        "worst_case_runtime_proven": False,
        "external_resource_reservation_admitted": False,
        "next_gate": contract["next_gate"],
    }


def main() -> None:
    print(json.dumps(check(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
