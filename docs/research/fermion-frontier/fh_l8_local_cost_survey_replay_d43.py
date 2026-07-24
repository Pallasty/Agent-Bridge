#!/usr/bin/env python3
"""D43 independent replay of the D42 two-seed fixed64 local survey."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import resource
from pathlib import Path

HERE = Path(__file__).resolve().parent
D42_RESULT = "fh_l8_local_cost_survey_d42_result.json"
D42_RESULT_SHA256 = "0bb796b3cd65b38969768540968eb64ae02d179490a704cb1d0a7b763e07aabc"
PINS = (
    "fh_l8_symmetry_orbit_quotient_d5_checker.py",
    "fh_l8_scalar_supremum_d4_checker.py",
    "hubbard_strang_commutator_checker.py",
    "fh_l8_symmetry_orbit_quotient_d5_contract.json",
)


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _replay_once():
    d5 = load("d43_d5", PINS[0])
    d4 = load("d43_d4", PINS[1])
    hubbard = load("d43_hubbard", PINS[2])
    contract = json.loads((HERE / PINS[3]).read_text())
    symmetries, _ = d5._build_symmetries(contract)
    bonds = {name: hubbard._hopping_bonds(8, name) for name in ("H1", "H2", "H3", "H4")}
    seed = int(contract["workload"]["neel_basis_hex"], 16)
    initial, _, _ = d5._reduced_column(d4, hubbard, bonds, seed, symmetries)
    pool = set(initial)
    second_seed = sorted(initial)[0]
    second, _, _ = d5._reduced_column(d4, hubbard, bonds, second_seed, symmetries)
    pool.update(second)
    collector_calls = 1
    for candidate in sorted(initial):
        if len(pool) >= 64:
            break
        child, _, _ = d5._reduced_column(d4, hubbard, bonds, candidate, symmetries)
        pool.update(child)
        collector_calls += 1
    representatives = sorted(pool)[:64]
    if len(representatives) != 64:
        raise RuntimeError("D43 fixture did not produce 64 representatives")
    rows = []
    for representative in representatives:
        column, orbit, dropped = d5._reduced_column(
            d4, hubbard, bonds, representative, symmetries
        )
        rows.append(
            {
                "representative_hex": hex(representative),
                "entries": len(column),
                "orbit": orbit,
                "dropped": dropped,
            }
        )
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return {
        "structural_rows_sha256": hashlib.sha256(payload).hexdigest(),
        "selected_representatives": len(representatives),
        "selection_collector_calls": collector_calls,
        "scientific_action_calls": 2 + collector_calls + len(representatives),
        "entries_min": min(row["entries"] for row in rows),
        "entries_max": max(row["entries"] for row in rows),
        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


def run():
    resource.setrlimit(resource.RLIMIT_AS, (536_870_912, 536_870_912))
    frozen = (HERE / D42_RESULT).read_bytes()
    if hashlib.sha256(frozen).hexdigest() != D42_RESULT_SHA256:
        raise RuntimeError("D42 result content pin mismatch")
    d42 = json.loads(frozen)
    replay = _replay_once()
    if replay["structural_rows_sha256"] != d42["structural_rows_sha256"]:
        raise RuntimeError("D43 does not match D42 structural digest")
    if replay["scientific_action_calls"] != 67:
        raise RuntimeError("unexpected D43 action count")
    return {
        "status": "VERIFIED_D43_TWO_SEED_FIXED64_LOCAL_COST_REPLAY",
        "d42_result_sha256": D42_RESULT_SHA256,
        "d42_structural_rows_sha256": d42["structural_rows_sha256"],
        "d43_structural_rows_sha256": replay["structural_rows_sha256"],
        "structural_rows_match": True,
        "selected_representatives": 64,
        "scientific_action_calls": 67,
        "d43_peak_rss_kib": replay["process_peak_rss_kib"],
        "entries_min": replay["entries_min"],
        "entries_max": replay["entries_max"],
        "packed_q3_reads": 0,
        "full_53_scientific_execution_authorized": False,
        "full53_extrapolation_forbidden": True,
        "next_gate": "D44_RESOURCE_OBSERVATION_NORMALIZATION",
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, separators=(",", ":")))
