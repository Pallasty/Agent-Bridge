#!/usr/bin/env python3
"""D30: exactly one owner-authorized D5 micro action, no packed-q3 input."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import resource
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError("source-bound module load failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run() -> dict:
    resource.setrlimit(resource.RLIMIT_AS, (536_870_912, 536_870_912))
    d5 = _load("d30_d5", "fh_l8_symmetry_orbit_quotient_d5_checker.py")
    d4 = _load("d30_d4", "fh_l8_scalar_supremum_d4_checker.py")
    backend = _load("d30_backend", "hubbard_strang_commutator_checker.py")
    contract_path = HERE / "fh_l8_symmetry_orbit_quotient_d5_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    symmetries, _ = d5._build_symmetries(contract)
    bonds = {name: backend._hopping_bonds(8, name) for name in ("H1", "H2", "H3", "H4")}
    representative = int(contract["workload"]["neel_basis_hex"], 16)
    info = d5._canonical_info(representative, symmetries)
    if info["representative"] != representative or info["projected_zero"]:
        raise RuntimeError("D5 contract representative is not admissible")
    column, orbit, dropped = d5._reduced_column(d4, backend, bonds, representative, symmetries)
    encoded = json.dumps([[hex(key), str(value)] for key, value in sorted(column.items())], separators=(",", ":")).encode()
    return {"status": "VERIFIED_D30_OWNER_SCOPED_SINGLE_MICRO_ACTION", "representative_hex": hex(representative), "source_orbit_size": orbit, "reduced_column_entries": len(column), "projected_zero_outputs": dropped, "column_sha256": hashlib.sha256(encoded).hexdigest(), "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "packed_q3_reads": 0, "scientific_action_calls": 1, "full_53_scientific_execution_authorized": False}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
