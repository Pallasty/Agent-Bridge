#!/usr/bin/env python3
"""D26 static boundary audit for the source-bound D5 scientific kernel."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
D5 = HERE / "fh_l8_symmetry_orbit_quotient_d5_checker.py"
D18C = HERE / "fh_l8_fresh_consumer_d18c_runner.py"


class AuditError(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit() -> dict:
    d5_tree = ast.parse(D5.read_text(encoding="utf-8"))
    d18_tree = ast.parse(D18C.read_text(encoding="utf-8"))
    funcs = {node.name: node for node in d5_tree.body if isinstance(node, ast.FunctionDef)}
    reduced = funcs.get("_reduced_column")
    if reduced is None:
        raise AuditError("source-bound kernel absent")
    params = [arg.arg for arg in reduced.args.args]
    expected = ["d4", "backend", "bonds", "representative", "symmetries"]
    if params != expected:
        raise AuditError("kernel parameter boundary drift")
    calls = [n for n in ast.walk(reduced) if isinstance(n, ast.Call)]
    invokes_sector_action = any(isinstance(c.func, ast.Attribute) and c.func.attr == "_sector_action" for c in calls)
    if not invokes_sector_action:
        raise AuditError("kernel no longer binds sector action")
    # The D5 source itself documents this as a candidate-action upper bound;
    # it is structural, not a measured cost or memory proof.
    literals = {n.value for n in ast.walk(d5_tree) if isinstance(n, ast.Constant) and type(n.value) is int}
    candidate_upper_bound = 225 if 225 in literals else None
    d18_calls = [n for n in ast.walk(d18_tree) if isinstance(n, ast.Call)]
    d18_binds_kernel = any(isinstance(c.func, ast.Attribute) and c.func.attr == "_reduced_column" for c in d18_calls)
    return {
        "status": "NO_GO_D26_SYNTHETIC_KERNEL_FIXTURE_ACTION_UNAUTHORIZED",
        "d5_sha256": _sha(D5),
        "d18c_runner_sha256": _sha(D18C),
        "kernel_name": "_reduced_column",
        "kernel_parameters": params,
        "kernel_invokes_sector_action": invokes_sector_action,
        "d18c_binds_kernel": d18_binds_kernel,
        "structural_candidate_action_upper_bound": candidate_upper_bound,
        "per_record_runtime_proven": False,
        "peak_memory_composition_proven": False,
        "synthetic_kernel_fixture_executed": False,
        "real_packed_q3_reads": 0,
        "scientific_action_calls": 0,
        "full_53_scientific_execution_authorized": False,
        "next_gate": "SOURCE_BOUND_MICRO_ACTION_AUTHORIZATION_AND_MEASURED_MEMORY_RUNTIME_RECEIPT",
    }


def main() -> int:
    print(json.dumps(audit(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
