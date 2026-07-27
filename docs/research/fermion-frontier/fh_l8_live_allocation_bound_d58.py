#!/usr/bin/env python3
"""Validate D58 allocation coverage without manufacturing numeric bounds."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
CONTRACT, RESULT = HERE / "fh_l8_live_allocation_bound_d58_contract.json", HERE / "fh_l8_live_allocation_bound_d58_result.json"
class D58Error(RuntimeError): pass
def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping): raise D58Error("object required")
    return value
def digest(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def validate(contract: Mapping[str, Any]) -> dict[str, Any]:
    if contract.get("contract_id") != "FH-L8-LIVE-ALLOCATION-BOUND-D58-V1": raise D58Error("id drift")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / name) != expected: raise D58Error(f"source pin mismatch: {name}")
    d51, d52, d56 = load(HERE / "fh_l8_full53_streaming_lifetime_d51_contract.json"), load(HERE / "fh_l8_full53_adapter_static_cost_d52_contract.json"), load(HERE / "fh_l8_resource_closure_plan_d56_contract.json")
    if d56["work_packages"][1]["gate"] != "D58_LIVE_ALLOCATION_CLASS_STATIC_BOUND": raise D58Error("D56 handoff drift")
    variables = contract.get("bound_variables")
    if not isinstance(variables, list) or len(variables) != 8 or len(set(variables)) != 8: raise D58Error("variable coverage drift")
    obligations, expressions = contract.get("proof_obligations"), contract.get("phase_expressions")
    if not isinstance(obligations, Mapping) or set(obligations) != set(variables): raise D58Error("obligation coverage drift")
    phases = [row["phase"] for row in d51["lifetime_phases"]]
    if not isinstance(expressions, Mapping) or list(expressions) != phases: raise D58Error("phase coverage drift")
    kernel = expressions["kernel_and_spill"]
    required_kernel = variables[:7]
    if any(name not in kernel for name in required_kernel) or "A_sort_key_heap" in kernel: raise D58Error("kernel lifetime drift")
    if "A_sort_key_heap" not in expressions["partition_external_merge"]: raise D58Error("merge lifetime drift")
    unresolved = set(d52["unresolved_allocation_costs"])
    if len(unresolved) != 7 or set(variables[1:7]) != {
        "A_sector_action_dictionary", "A_canonical_info_transient", "A_basis_images_transient",
        "A_fraction_objects", "A_reduced_column_dictionary", "A_partition_writer_state",
    }: raise D58Error("D52 allocation mapping drift")
    if len(contract.get("forbidden_substitutions", [])) != 4: raise D58Error("substitution boundary drift")
    authority = contract["authority"]
    if any(authority.get(k) is not False for k in ("numeric_peak_memory_proven", "numeric_runtime_seconds_proven", "external_resource_reservation_admitted", "full53_execution_authorized")): raise D58Error("authority open")
    if any(authority.get(k) != 0 for k in ("scientific_kernel_calls_executed", "object_measurements_executed", "packed_q3_reads")): raise D58Error("D58 must not execute")
    return {"status":"VERIFIED_D58_SYMBOLIC_LIVE_ALLOCATION_INVENTORY_NUMERIC_PROOFS_PENDING", "bound_variable_count":len(variables), "proof_obligation_count":len(obligations), "phase_expression_count":len(expressions), "forbidden_substitution_count":len(contract["forbidden_substitutions"]), **authority, "next_gate":contract["next_gate"]}
def verify() -> dict[str, Any]:
    expected = validate(load(CONTRACT))
    if load(RESULT) != expected: raise D58Error("result drift")
    return expected
if __name__ == "__main__": print(json.dumps(verify(), indent=2, sort_keys=True))
