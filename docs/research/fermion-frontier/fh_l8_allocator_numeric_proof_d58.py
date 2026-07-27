#!/usr/bin/env python3
import hashlib, json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
C = HERE / "fh_l8_allocator_numeric_proof_d58_contract.json"
R = HERE / "fh_l8_allocator_numeric_proof_d58_result.json"
class D58NumericProofError(RuntimeError): pass

def digest(name: str) -> str:
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()

def verify() -> dict[str, Any]:
    c = json.loads(C.read_text(encoding="utf-8"))
    if c.get("contract_id") != "FH-L8-ALLOCATOR-NUMERIC-PROOF-D58-V1": raise D58NumericProofError("id")
    if any(v == "TO_BE_FILLED" for v in c["source_pins"].values()): raise D58NumericProofError("unsealed source pin")
    for name, expected in c["source_pins"].items():
        if digest(name) != expected: raise D58NumericProofError(f"source pin mismatch: {name}")
    variables = c["variables"]
    if len(variables) != 8 or set(c["proof_inputs"]) != set(variables): raise D58NumericProofError("variable coverage")
    missing, total = [], 0
    for name in variables:
        row = c["proof_inputs"][name]
        if any(row.get(field) is None for field in c["required_fields_per_variable"]):
            missing.append(name); continue
        if any(not isinstance(row[field], int) or row[field] < 0 for field in c["required_fields_per_variable"][:3]):
            raise D58NumericProofError(f"invalid numeric input: {name}")
        total += row["instance_count"] * (row["payload_bytes_per_instance"] + row["allocator_overhead_bytes_per_instance"])
    if missing:
        result = {"status": "VERIFIED_D58_NUMERIC_PROOF_FAIL_CLOSED", "decision": "NO_GO_D58_NUMERIC_INPUTS_INCOMPLETE", "variable_count": 8, "missing_variable_count": len(missing), "missing_variables": missing, "recomputed_peak_bytes": None, "numeric_peak_memory_proven": False, "full53_execution_authorized": False}
    else:
        result = {"status": "VERIFIED_D58_NUMERIC_PROOF_RECOMPUTED", "decision": "GO_D58_NUMERIC_PROOF_RECOMPUTED", "variable_count": 8, "missing_variable_count": 0, "missing_variables": [], "recomputed_peak_bytes": total, "numeric_peak_memory_proven": True, "full53_execution_authorized": False}
    if json.loads(R.read_text(encoding="utf-8")) != result: raise D58NumericProofError("result drift")
    return result

if __name__ == "__main__": print(json.dumps(verify(), indent=2, sort_keys=True))
