#!/usr/bin/env python3
"""Read-only validator for the P11-B preimplementation contract pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
REPO = BASE.parents[2]
DIRECT_PARENT = "fb9bcd3bcbedcde774f0c9e0e5b730efb350a7f5"
P11A = "71967df1b328cc40ad28c555f0c6ff9152f87774"
CONTRACT_NAME = "majorana_certificate_p11b_preimplementation_contract_pack_contract.json"
REPORT_NAME = "majorana_certificate_p11b_preimplementation_contract_pack_report.json"
MODULE_NAME = "majorana_certificate_p11b_preimplementation_contract_pack_validator.py"
TEST_NAME = "test_majorana_certificate_p11b_preimplementation_contract_pack.py"
CONTRACT_CANONICAL_SHA256 = "2fe5856a0f6768955f797d474bc1ceefd2a4976b23efbdddfab54889c3ebf123"
OUTCOME = "PREIMPLEMENTATION_CONTRACT_PACK_DEFINED_NOT_IMPLEMENTATION_AUTHORITY"
G1_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    "docs/research/fermion-frontier/majorana_certificate_p11_g1_preimplementation_governance_contract.json": "A",
    "docs/research/fermion-frontier/majorana_certificate_p11_g1_preimplementation_governance_record.json": "A",
    "docs/research/fermion-frontier/majorana_certificate_p11_g1_preimplementation_governance_validator.py": "A",
    "docs/research/fermion-frontier/test_majorana_certificate_p11_g1_preimplementation_governance.py": "A",
}
CHANGED_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    f"docs/research/fermion-frontier/{CONTRACT_NAME}": "A",
    f"docs/research/fermion-frontier/{REPORT_NAME}": "A",
    f"docs/research/fermion-frontier/{MODULE_NAME}": "A",
    f"docs/research/fermion-frontier/{TEST_NAME}": "A",
}
SECTION_IDS = ("BYTE_LAYOUT", "ARITHMETIC_WIDTH", "ARENA_LIFETIME", "AOT_TOOLCHAIN", "RUNTIME_TOTAL", "INDEPENDENT_CHECKER", "FROZEN_SEMANTICS")
REGION_IDS = ("TERM_TABLE_MAIN", "TERM_TABLE_AUX", "BOUNDARY_SNAPSHOT", "RANKING_ROWS_WITH_TICK2048", "CONSTITUENT_ACTIONS", "MERGE_COLLISIONS", "DROPPED_ROWS", "INDEX_AND_MEMBERSHIP_WORKSPACE")
LAYOUT_IDS = ("TERM_SLOT_64", "SNAPSHOT_ROW_48", "RANK_ROW_320", "ACTION_ROW_80", "COLLISION_ROW_64", "DROPPED_ROW_48", "INDEX_MEMBERSHIP_ROW_16")


class ContractError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ContractError(f"non-finite JSON constant: {value}")


def loads_strict(raw: bytes, label: str, *, canonical: bool = False) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError(f"malformed {label}") from error
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    if canonical and raw != canonical_bytes(value):
        raise ContractError(f"{label} is not canonical JSON")
    return value


def load_json(path: Path, label: str, *, canonical: bool = False) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise ContractError(f"invalid {label} file")
    raw = path.read_bytes()
    return loads_strict(raw, label, canonical=canonical), raw


def _authority() -> dict[str, Any]:
    return {"scientific_authority": "NONE", "execution_authority": False, "implementation_authority": False,
            "prototype_or_compilation_authority": False, "candidate_selection_authority": False,
            "candidate_or_cap_change_authority": False, "resource_or_no_go_authority": False, "S0_authority": False,
            "certificate_eligible": False, "result_contract_eligible": False}


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "MAJORANA-P11-B-PREIMPLEMENTATION-CONTRACT-PACK-V1" or contract.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise ContractError("contract identity drift")
    if contract.get("authority") != _authority() or sha256(canonical_bytes(contract)) != CONTRACT_CANONICAL_SHA256:
        raise ContractError("contract authority or semantic drift")
    scope = contract.get("scope", {})
    for key in ("implementation_source_allowed", "compilation_or_linking_allowed", "Julia_or_candidate_execution_allowed", "benchmark_or_host_measurement_allowed", "package_installation_or_environment_mutation_allowed", "binary_or_source_archive_download_allowed"):
        if scope.get(key) is not False:
            raise ContractError("scope authority drift")
    if contract.get("outcome") != OUTCOME:
        raise ContractError("outcome drift")
    rows = contract.get("section_disposition")
    if not isinstance(rows, list) or tuple(row.get("section_id") for row in rows if isinstance(row, dict)) != SECTION_IDS:
        raise ContractError("section disposition drift")


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def _parent(commit: str) -> str:
    row = _git("rev-list", "--parents", "-n", "1", commit).strip().split()
    if len(row) != 2 or row[0] != commit:
        raise ContractError("commit must have one parent")
    return row[1]


def _paths(commit: str) -> dict[str, str]:
    return {path: status for status, path in (line.split("\t", 1) for line in _git("diff-tree", "--no-commit-id", "--name-status", "-r", "--no-renames", commit).splitlines())}


def validate_sources(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    if _parent(DIRECT_PARENT) != P11A or _paths(DIRECT_PARENT) != G1_PATHS:
        raise ContractError("P11-G1 topology or path drift")
    inputs = contract.get("source_inputs")
    if not isinstance(inputs, list) or len(inputs) != 8:
        raise ContractError("source input count drift")
    values: dict[str, bytes] = {}
    for row in inputs:
        if not isinstance(row, dict) or set(row) != {"relative_path", "sha256", "role"}:
            raise ContractError("source input row drift")
        raw = (BASE / row["relative_path"]).read_bytes()
        if sha256(raw) != row["sha256"]:
            raise ContractError("source input digest drift")
        values[row["relative_path"]] = raw
    g1 = loads_strict(values["majorana_certificate_p11_g1_preimplementation_governance_record.json"], "P11-G1 record", canonical=True)
    if g1.get("next_gate") != "P11-B-PREIMPLEMENTATION-CONTRACT-PACK-V1" or g1.get("implementation_source_allowed") is not False or g1.get("compilation_or_linking_allowed") is not False:
        raise ContractError("P11-G1 authority drift")
    p11a = loads_strict(values["majorana_certificate_p11a_explicit_memory_kernel_design_report.json"], "P11-A report", canonical=True)
    if p11a.get("outcome") != "FEASIBLE_EXPLICIT_MEMORY_ROUTE_IDENTIFIED_NOT_IMPLEMENTATION_AUTHORITY" or p11a.get("derived_explicit_region_subtotal_bytes") != 872415232:
        raise ContractError("P11-A result drift")
    p6 = loads_strict(values["majorana_certificate_p6_contract.json"], "P6 contract")
    witness = p6.get("witness", {})
    final = witness.get("authoritative_two_step_final_state", {})
    raw_witness = witness.get("raw_witness", {})
    if final.get("retained_term_count") != 284847 or final.get("term_stream_sha256") != "9bd44992823cc6f8cf731f84954840d4927a972fb6a78c1583c3d8c0983a7c51":
        raise ContractError("P6 final-state custody drift")
    if raw_witness.get("trig_table", {}).get("entries_sha256") != "2cf79510f1f76728e9cbe22cd168d220845b0be328833d04f0da322da331ee0a":
        raise ContractError("P6 trig custody drift")
    if "serialized_term_state" in witness or "term_rows" in final:
        raise ContractError("unexpected serialized P6 state claim")
    return [dict(row) for row in inputs]


def validate_layout(contract: Mapping[str, Any]) -> dict[str, Any]:
    layout = contract.get("byte_layout_contract", {})
    rows = layout.get("slot_layouts")
    if not isinstance(rows, list) or tuple(row.get("layout_id") for row in rows if isinstance(row, dict)) != LAYOUT_IDS:
        raise ContractError("slot layout identity drift")
    for row in rows:
        size = row["size_bytes"]
        occupied: set[int] = set()
        for field in row["fields"]:
            start, width = field["offset"], field["size"]
            if not isinstance(start, int) or not isinstance(width, int) or start < 0 or width <= 0 or start + width > size:
                raise ContractError("slot field outside layout")
            span = set(range(start, start + width))
            if occupied & span:
                raise ContractError("slot field overlap")
            occupied |= span
    table = layout.get("term_table_rules", {})
    if table.get("capacity_slots_each") != 2097152 or table.get("maximum_occupied_slots_each") != 1048576 or table.get("maximum_load_factor_numerator") * table.get("capacity_slots_each") != table.get("maximum_load_factor_denominator") * table.get("maximum_occupied_slots_each"):
        raise ContractError("term-table capacity drift")
    return {"slot_layout_manifest_sha256": sha256(canonical_bytes(rows)), "term_table_rules_sha256": sha256(canonical_bytes(table))}


def validate_arena(contract: Mapping[str, Any]) -> dict[str, Any]:
    arena = contract.get("arena_contract", {})
    rows = arena.get("regions_in_offset_order")
    if not isinstance(rows, list) or tuple(row.get("region_id") for row in rows if isinstance(row, dict)) != REGION_IDS:
        raise ContractError("arena region identity drift")
    cursor = 0
    for row in rows:
        if row.get("offset_bytes") != cursor or row["offset_bytes"] % 64 or row["size_bytes"] <= 0:
            raise ContractError("arena offset or alignment drift")
        cursor += row["size_bytes"]
    if cursor != 872415232 or arena.get("explicit_arena_bytes") != cursor or arena.get("all_regions_reserved_simultaneously_and_never_alias") is not True:
        raise ContractError("arena subtotal or alias drift")
    return {"arena_manifest_sha256": sha256(canonical_bytes(rows)), "explicit_arena_bytes": cursor}


def validate_arithmetic(contract: Mapping[str, Any]) -> dict[str, Any]:
    arithmetic = contract.get("arithmetic_width_contract", {})
    rows = arithmetic.get("derivation_rows")
    expected = (53, 129, 182, 1154, 2049, 2050)
    if not isinstance(rows, list) or tuple(row.get("maximum_magnitude_bits") for row in rows if isinstance(row, dict)) != expected:
        raise ContractError("arithmetic derivation drift")
    if arithmetic.get("stored_magnitude_limb_count") * arithmetic.get("limb_bits") != 2048 or arithmetic.get("reused_wide_scratch_limb_count") * arithmetic.get("limb_bits") != 2112 or max(expected) > 2112:
        raise ContractError("arithmetic width closure drift")
    return {"arithmetic_derivation_sha256": sha256(canonical_bytes(rows)), "stored_magnitude_bits": 2048, "wide_scratch_bits": 2112}


def validate_runtime(contract: Mapping[str, Any]) -> dict[str, Any]:
    rows = contract.get("runtime_bound_target_ledger")
    if not isinstance(rows, list) or len(rows) != 8:
        raise ContractError("runtime target row drift")
    total = sum(row["target_bytes"] for row in rows)
    rules = contract.get("runtime_target_rules", {})
    if total != 1028653056 or rules.get("target_component_sum_bytes") != total or rules.get("difference_to_fixed_cap_bytes") != 2147483648 - total or rules.get("sum_is_a_preimplementation_target_not_an_exact_peak_bound") is not True or rules.get("difference_is_not_proven_headroom") is not True:
        raise ContractError("runtime target arithmetic drift")
    return {"runtime_target_ledger_sha256": sha256(canonical_bytes(rows)), "target_component_sum_bytes": total, "difference_to_fixed_cap_bytes": 2147483648 - total}


def validate_toolchain_shape(contract: Mapping[str, Any]) -> dict[str, Any]:
    receipt = contract.get("local_toolchain_identity_receipt", {})
    binaries = receipt.get("binaries")
    if not isinstance(binaries, list) or len(binaries) != 8 or receipt.get("compiler_version") != "15.2.0" or receipt.get("compiler_target") != "x86_64-linux-gnu":
        raise ContractError("toolchain receipt drift")
    if any(not isinstance(row.get("size_bytes"), int) or len(row.get("sha256", "")) != 64 or not row.get("absolute_path", "").startswith("/usr/") for row in binaries):
        raise ContractError("toolchain binary row drift")
    flags = contract.get("compile_and_link_contract", {})
    required_compile = {"-std=c17", "-ffreestanding", "-fno-builtin", "-nostdinc", "-ffp-contract=off", "-fno-fast-math", "-frounding-math", "-fexcess-precision=standard", "-mfpmath=sse", "-fno-lto", "-fstack-usage"}
    if not required_compile <= set(flags.get("compile_flags_in_order", ())) or flags.get("link_input_policy") != "explicit_allowlisted_object_files_only_no_dash_l_no_startfiles_no_default_libraries":
        raise ContractError("compile/link contract drift")
    return {"toolchain_receipt_sha256": sha256(canonical_bytes(receipt)), "compile_flags_sha256": sha256(canonical_bytes(flags["compile_flags_in_order"])), "linker_flags_sha256": sha256(canonical_bytes(flags["linker_flags_in_order"]))}


def verify_local_toolchain(contract: Mapping[str, Any]) -> dict[str, Any]:
    receipt = contract["local_toolchain_identity_receipt"]
    for row in receipt["binaries"]:
        path = Path(row["absolute_path"])
        if path.is_symlink() or not path.is_file() or path.stat().st_size != row["size_bytes"] or sha256(path.read_bytes()) != row["sha256"]:
            raise ContractError(f"local toolchain binary drift: {row['role']}")
    driver = receipt["binaries"][0]["absolute_path"]
    if _run_identity((driver, "-dumpfullversion", "-dumpversion")).strip() != "15.2.0":
        raise ContractError("local compiler version drift")
    if _run_identity((driver, "-dumpmachine")).strip() != "x86_64-linux-gnu":
        raise ContractError("local compiler target drift")
    if sha256(_run_identity_bytes((driver, "-dumpspecs"))) != receipt["driver_specs_stdout_sha256"]:
        raise ContractError("local compiler specs drift")
    return {"status": "VERIFIED_READ_ONLY_LOCAL_TOOLCHAIN_IDENTITY", "binary_count": 8}


def _run_identity(command: Sequence[str]) -> str:
    allowed = {("/usr/bin/x86_64-linux-gnu-gcc-15", "-dumpfullversion", "-dumpversion"), ("/usr/bin/x86_64-linux-gnu-gcc-15", "-dumpmachine")}
    if tuple(command) not in allowed:
        raise ContractError("non-allowlisted identity command")
    return subprocess.run(tuple(command), check=True, capture_output=True, text=True, encoding="utf-8").stdout


def _run_identity_bytes(command: Sequence[str]) -> bytes:
    if tuple(command) != ("/usr/bin/x86_64-linux-gnu-gcc-15", "-dumpspecs"):
        raise ContractError("non-allowlisted identity command")
    return subprocess.run(tuple(command), check=True, capture_output=True).stdout


def expected_report(contract: Mapping[str, Any], raw: bytes, sources: list[dict[str, Any]], derived: Mapping[str, Any]) -> dict[str, Any]:
    return {"schema_version": 1, "report_type": "majorana_p11_b_preimplementation_contract_pack_report_v1",
            "gate_id": "P11-B-PREIMPLEMENTATION-CONTRACT-PACK-V1", "parent_commit": DIRECT_PARENT,
            "contract_raw_sha256": sha256(raw), "contract_canonical_sha256": sha256(canonical_bytes(contract)), "source_inputs": sources,
            "outcome": OUTCOME, "selected_target": contract["selected_target"], "derived_contract_digests_and_totals": dict(derived),
            "section_disposition": contract["section_disposition"], "prelude_requirement": contract["prelude_and_semantics_contract"],
            "toolchain_receipt_status": "LOCAL_BINARY_IDENTITY_OBSERVED_NOT_SOURCE_ARCHIVE_CUSTODY",
            "official_metadata_status": "IDENTIFIED_NOT_BYTE_PINNED", "unresolved_before_implementation_authority": contract["unresolved_before_implementation_authority"],
            "fixed_process_cap_bytes": 2147483648, "preimplementation_target_component_sum_bytes": 1028653056,
            "difference_to_fixed_cap_bytes": 1118830592, "difference_is_proven_headroom": False,
            "exact_static_process_peak_bytes": None, "strict_integer_peak_less_than_fixed_cap": None,
            "semantic_equivalence_established": False, "implementation_gate": "CLOSED", "execution_gate": "CLOSED",
            "scientific_authority": "NONE", "execution_authority": False, "implementation_authority": False,
            "candidate_selection_authority": False, "candidate_or_cap_change_authority": False,
            "resource_or_no_go_authority": False, "resource_no_go_inference": False, "S0_authority": False,
            "certificate_eligible": False, "result_contract_eligible": False,
            "next_governance_requirement": "NEW_INDEPENDENT_POST_P11_B_GOVERNANCE_REQUIRED_BEFORE_ANY_IMPLEMENTATION_SOURCE"}


def validate_content() -> dict[str, Any]:
    contract, raw = load_json(BASE / CONTRACT_NAME, "P11-B contract")
    validate_contract(contract)
    sources = validate_sources(contract)
    derived: dict[str, Any] = {}
    for check in (validate_layout, validate_arena, validate_arithmetic, validate_runtime, validate_toolchain_shape):
        derived.update(check(contract))
    report, _ = load_json(BASE / REPORT_NAME, "P11-B report", canonical=True)
    if report != expected_report(contract, raw, sources, derived):
        raise ContractError("report reconstruction drift")
    return {"status": "VERIFIED_P11_B_PREIMPLEMENTATION_CONTRACT_PACK", "outcome": OUTCOME,
            "target_component_sum_bytes": derived["target_component_sum_bytes"], "implementation_gate": "CLOSED", "execution_gate": "CLOSED"}


def validate_lifecycle() -> str:
    if _git("rev-parse", "HEAD").strip() != DIRECT_PARENT:
        raise ContractError("staging must begin at P11-G1")
    staged = {path: status for status, path in (line.split("\t", 1) for line in _git("diff", "--cached", "--name-status", "--no-renames").splitlines())}
    if staged != CHANGED_PATHS:
        raise ContractError("staged changed-path set drift")
    if _git("diff", "--name-only").strip() or _git("ls-files", "--others", "--exclude-standard").strip():
        raise ContractError("unstaged or untracked files are forbidden")
    return "STAGED_DIRECT_CHILD"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-content", action="store_true")
    parser.add_argument("--verify-lifecycle", action="store_true")
    parser.add_argument("--verify-local-toolchain", action="store_true")
    args = parser.parse_args()
    if not any((args.verify_content, args.verify_lifecycle, args.verify_local_toolchain)):
        parser.error("choose a verification mode")
    contract = None
    if args.verify_content:
        print(json.dumps(validate_content(), sort_keys=True))
    if args.verify_local_toolchain:
        contract, _ = load_json(BASE / CONTRACT_NAME, "P11-B contract")
        validate_contract(contract)
        print(json.dumps(verify_local_toolchain(contract), sort_keys=True))
    if args.verify_lifecycle:
        print(validate_lifecycle())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
