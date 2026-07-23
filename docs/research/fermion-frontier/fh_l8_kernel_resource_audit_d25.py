#!/usr/bin/env python3
"""D25 read-only audit for the missing full-53 kernel/resource proof.

This module deliberately reads only JSON contracts and Python *source text*.
It never imports the D20 consumer, so its packed-q3 hash routine and any future
scientific action cannot run as an accidental side effect.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_kernel_resource_audit_d25_contract.json"
SOURCES = {
    "d20_consumer": "fh_l8_full_consumer_d20.py",
    "d20_contract": "fh_l8_full_consumer_d20_contract.json",
    "d23_envelope": "fh_l8_full_resource_envelope_d23.py",
    "d23_contract": "fh_l8_full_resource_envelope_d23_contract.json",
    "d24_reservation": "fh_l8_resource_reservation_d24.py",
    "d24_contract": "fh_l8_resource_reservation_d24_contract.json",
}


class AuditError(ValueError):
    pass


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in items:
        if key in out:
            raise AuditError("duplicate JSON key")
        out[key] = value
    return out


def _load_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if not raw or len(raw) > 262_144:
        raise AuditError(f"JSON size drift: {path.name}")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=lambda _: (_ for _ in ()).throw(AuditError("float forbidden")),
            parse_constant=lambda _: (_ for _ in ()).throw(AuditError("constant forbidden")),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"invalid JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise AuditError(f"JSON object required: {path.name}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise AuditError(f"D20 function drift: {name}")
    return matches[0]


def _called_names(node: ast.AST) -> set[str]:
    result: set[str] = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Call):
            if isinstance(item.func, ast.Name):
                result.add(item.func.id)
            elif isinstance(item.func, ast.Attribute):
                result.add(item.func.attr)
    return result


def _source_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for role, relative in SOURCES.items():
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise AuditError(f"source missing or unsafe: {relative}")
        hashes[role] = _sha(path)
    return hashes


def _validate_contract(contract: dict[str, Any], hashes: dict[str, str]) -> None:
    expected_keys = {
        "schema_version", "contract_id", "role", "source_hashes", "required_proofs",
        "authority", "expected_status", "next_gate",
    }
    if set(contract) != expected_keys or contract["schema_version"] != 1:
        raise AuditError("D25 contract schema drift")
    if contract["contract_id"] != "FH-L8-INDEPENDENT-REFERENCE-D25-KERNEL-RESOURCE-AUDIT-V1":
        raise AuditError("D25 contract identity drift")
    if contract["role"] != "read_only_source_bound_no_q3_read_no_scientific_action":
        raise AuditError("D25 role drift")
    if contract["source_hashes"] != hashes:
        raise AuditError("D25 source custody drift")
    if contract["required_proofs"] != [
        "source_bound_scientific_kernel", "per_input_output_memory_model",
        "peak_memory_composition", "worst_case_runtime_model", "independent_receipt_verification",
    ]:
        raise AuditError("D25 required-proof drift")
    if contract["authority"] != {
        "real_packed_q3_read_authorized": False,
        "scientific_kernel_authorized": False,
        "full_53_scientific_execution_authorized": False,
        "scientific_action_calls": 0,
    }:
        raise AuditError("D25 authority drift")


def audit(root: Path = HERE) -> dict[str, Any]:
    """Return a no-go result from pinned source, without opening checkpoint.bin."""
    root = Path(root)
    hashes = _source_hashes(root)
    contract = _load_json(root / CONTRACT.name)
    _validate_contract(contract, hashes)
    d20_contract = _load_json(root / SOURCES["d20_contract"])
    d23_contract = _load_json(root / SOURCES["d23_contract"])
    d24_contract = _load_json(root / SOURCES["d24_contract"])

    d20_tree = ast.parse((root / SOURCES["d20_consumer"]).read_text(encoding="utf-8"))
    run = _function(d20_tree, "run")
    run_calls = _called_names(run)
    run_has_unconditional_rejection = any(
        isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
        and node.exc.func.id == "ConsumerError"
        for node in run.body
    )
    implementation_names = {
        node.name for node in d20_tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    kernel_names = {name for name in implementation_names if "kernel" in name.lower() or "hamiltonian" in name.lower()}
    kernel_bound = bool(kernel_names) and not run_has_unconditional_rejection and bool(run_calls & kernel_names)

    resource_model_keys = {"per_input_output_memory_model", "peak_memory_composition", "worst_case_runtime_model"}
    d20_has_resource_model = resource_model_keys <= set(d20_contract)
    d23_requires_but_does_not_supply = (
        set(d23_contract["required_evidence"])
        == {"explicit_memory_bound", "explicit_runtime_bound", "external_resource_reservation", "fresh_full_execution_contract"}
        and "memory_requirement_bytes" not in d23_contract
        and "runtime_requirement_ns" not in d23_contract
    )
    d24_has_only_admission_schema = (
        d24_contract["role"] == "external_receipt_admission_only_not_execution_authorization"
        and d24_contract["authorization"]["external_receipt_present"] is False
    )
    missing = []
    if not kernel_bound:
        missing.append("source_bound_scientific_kernel")
    if not d20_has_resource_model:
        missing.extend(["per_input_output_memory_model", "peak_memory_composition", "worst_case_runtime_model"])
    if d24_has_only_admission_schema:
        missing.append("independent_receipt_verification")
    if not d23_requires_but_does_not_supply:
        raise AuditError("D23 evidence-boundary drift")
    if not missing:
        raise AuditError("unexpected D25 positive authorization path")
    return {
        "schema_version": 1,
        "contract_id": contract["contract_id"],
        "status": contract["expected_status"],
        "verified": True,
        "source_hashes": hashes,
        "d20_run_has_unconditional_rejection": run_has_unconditional_rejection,
        "d20_scientific_kernel_bound": kernel_bound,
        "d20_resource_model_present": d20_has_resource_model,
        "d23_requires_but_does_not_supply_memory_runtime": d23_requires_but_does_not_supply,
        "d24_independent_receipt_verified": False,
        "missing_proofs": missing,
        "real_packed_q3_reads": 0,
        "scientific_action_calls": 0,
        "full_53_scientific_execution_authorized": False,
        "next_gate": contract["next_gate"],
    }


def main() -> int:
    print(json.dumps(audit(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
