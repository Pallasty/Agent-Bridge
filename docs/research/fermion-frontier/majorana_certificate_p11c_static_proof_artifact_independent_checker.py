#!/usr/bin/env python3
"""Independent, non-candidate checker for P11-C contract-level artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
REPO = BASE.parents[2]
DIRECT_PARENT = "fa9792d456b9c6bd32a0393fec9e9baa508cb7b7"
P11B = "9659d7cdf4a75768b358f0085e50dbf9f76bbc02"
CONTRACT_NAME = "majorana_certificate_p11c_static_proof_artifact_contract.json"
MANIFEST_NAME = "majorana_certificate_p11c_static_proof_artifact_manifest.json"
REPORT_NAME = "majorana_certificate_p11c_static_proof_artifact_report.json"
MODULE_NAME = "majorana_certificate_p11c_static_proof_artifact_independent_checker.py"
TEST_NAME = "test_majorana_certificate_p11c_static_proof_artifact.py"
CONTRACT_CANONICAL_SHA256 = "a91f1d4c50118f46a0a1efce31300afae189bd6a51b2f3a17bf1602222c76bbd"
OUTCOME = "STATIC_PROOF_ARTIFACTS_ESTABLISHED_PARTIAL_OBLIGATION_CLOSURE"
SOURCE_PREFIX = "docs/research/fermion-frontier/"
G2_PATHS = {
    SOURCE_PREFIX + "ARTIFACTS.md": "M",
    SOURCE_PREFIX + "PROGRESS.md": "M",
    SOURCE_PREFIX + "majorana_certificate_p11_g2_proof_artifact_governance_contract.json": "A",
    SOURCE_PREFIX + "majorana_certificate_p11_g2_proof_artifact_governance_record.json": "A",
    SOURCE_PREFIX + "majorana_certificate_p11_g2_proof_artifact_governance_validator.py": "A",
    SOURCE_PREFIX + "test_majorana_certificate_p11_g2_proof_artifact_governance.py": "A",
}
CHANGED_PATHS = {
    SOURCE_PREFIX + "ARTIFACTS.md": "M",
    SOURCE_PREFIX + "PROGRESS.md": "M",
    SOURCE_PREFIX + CONTRACT_NAME: "A",
    SOURCE_PREFIX + MANIFEST_NAME: "A",
    SOURCE_PREFIX + REPORT_NAME: "A",
    SOURCE_PREFIX + MODULE_NAME: "A",
    SOURCE_PREFIX + TEST_NAME: "A",
}
LAYOUT_SIZES = {
    "TERM_SLOT_64": 64,
    "SNAPSHOT_ROW_48": 48,
    "RANK_ROW_320": 320,
    "ACTION_ROW_80": 80,
    "COLLISION_ROW_64": 64,
    "DROPPED_ROW_48": 48,
    "INDEX_MEMBERSHIP_ROW_16": 16,
}
REGION_SIZES = {
    "TERM_TABLE_MAIN": 134217728,
    "TERM_TABLE_AUX": 134217728,
    "BOUNDARY_SNAPSHOT": 50331648,
    "RANKING_ROWS_WITH_TICK2048": 335544320,
    "CONSTITUENT_ACTIONS": 83886080,
    "MERGE_COLLISIONS": 67108864,
    "DROPPED_ROWS": 50331648,
    "INDEX_AND_MEMBERSHIP_WORKSPACE": 16777216,
}
RUNTIME_TARGETS = {
    "EXPLICIT_ARENA": 872415232,
    "CODE_RODATA_LIMIT": 67108864,
    "NONARENA_DATA_BSS_LIMIT": 8388608,
    "STACK_TOUCHED_LIMIT": 8388608,
    "OUTPUT_BUFFERS_LIMIT": 2097152,
    "HASH_ENCODING_SCRATCH_LIMIT": 1048576,
    "ELF_PAGE_PADDING_LIMIT": 2097152,
    "KERNEL_CGROUP_ACCOUNTED_RESERVE_TARGET": 67108864,
}
ARITHMETIC_BITS = (53, 129, 182, 1154, 2049, 2050)
MUTATIONS = ("slot_offset_overlap", "one_byte_slot_shrink", "capacity_minus_one", "load_factor_relaxation",
             "scratch_2049_instead_of_2112", "arena_region_overlap", "runtime_component_sum_drift",
             "headroom_claim_flip", "prelude_checkpoint_hash_mismatch")


class ArtifactError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ArtifactError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _constant(value: str) -> None:
    raise ArtifactError(f"non-finite JSON constant: {value}")


def loads_strict(raw: bytes, label: str, *, canonical: bool = False) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArtifactError(f"malformed {label}") from error
    if not isinstance(value, dict):
        raise ArtifactError(f"{label} must be an object")
    if canonical and raw != canonical_bytes(value):
        raise ArtifactError(f"{label} is not canonical JSON")
    return value


def load_json(path: Path, label: str, *, canonical: bool = False) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise ArtifactError(f"invalid {label} file")
    raw = path.read_bytes()
    return loads_strict(raw, label, canonical=canonical), raw


def _authority() -> dict[str, Any]:
    return {"scientific_authority": "NONE", "execution_authority": False, "implementation_authority": False,
            "prototype_or_compilation_authority": False, "candidate_selection_authority": False,
            "candidate_or_cap_change_authority": False, "resource_or_no_go_authority": False,
            "S0_authority": False, "certificate_eligible": False, "result_contract_eligible": False}


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "MAJORANA-P11-C-STATIC-PROOF-ARTIFACT-PACK-V1" or contract.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise ArtifactError("contract identity drift")
    if contract.get("authority") != _authority() or sha256(canonical_bytes(contract)) != CONTRACT_CANONICAL_SHA256:
        raise ArtifactError("contract authority or semantic drift")
    scope = contract.get("scope", {})
    for key in ("candidate_source_allowed", "C_assembly_or_linker_script_source_allowed", "compilation_or_linking_allowed",
                "Julia_or_candidate_execution_allowed", "benchmark_or_host_measurement_allowed",
                "package_installation_or_environment_mutation_allowed", "binary_or_source_archive_download_allowed",
                "network_retrieval_allowed", "scientific_schedule_semantics_or_cap_change_allowed"):
        if scope.get(key) is not False:
            raise ArtifactError("scope authority drift")
    if contract.get("outcome") != OUTCOME or tuple(contract.get("required_adversarial_mutations", ())) != MUTATIONS:
        raise ArtifactError("outcome or mutation-vector drift")


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def _git_bytes(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True).stdout


def _parent(commit: str) -> str:
    row = _git("rev-list", "--parents", "-n", "1", commit).strip().split()
    if len(row) != 2 or row[0] != commit:
        raise ArtifactError("commit must have one parent")
    return row[1]


def _paths(commit: str) -> dict[str, str]:
    return {path: status for status, path in (line.split("\t", 1) for line in _git("diff-tree", "--no-commit-id", "--name-status", "-r", "--no-renames", commit).splitlines())}


def validate_sources(contract: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    if _parent(DIRECT_PARENT) != P11B or _paths(DIRECT_PARENT) != G2_PATHS:
        raise ArtifactError("P11-G2 topology or path drift")
    inputs = contract.get("source_inputs")
    if not isinstance(inputs, list) or len(inputs) != 3:
        raise ArtifactError("source input list drift")
    values: dict[str, bytes] = {}
    for row in inputs:
        path = row.get("relative_path")
        if not isinstance(path, str) or path in values:
            raise ArtifactError("source path drift")
        raw = _git_bytes("show", f"{DIRECT_PARENT}:{SOURCE_PREFIX}{path}")
        if sha256(raw) != row.get("sha256"):
            raise ArtifactError("source input digest drift")
        values[path] = raw
    g2 = loads_strict(values["majorana_certificate_p11_g2_proof_artifact_governance_record.json"], "P11-G2 record", canonical=True)
    if g2.get("next_gate") != "P11-C-STATIC-PROOF-ARTIFACT-PACK-V1" or g2.get("candidate_source_allowed") is not False or g2.get("compilation_or_linking_allowed") is not False or g2.get("Julia_or_candidate_execution_allowed") is not False:
        raise ArtifactError("P11-G2 authority drift")
    return [dict(row) for row in inputs], values


def _padding_ranges(covered: list[bool]) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    cursor = 0
    while cursor < len(covered):
        if covered[cursor]:
            cursor += 1
            continue
        start = cursor
        while cursor < len(covered) and not covered[cursor]:
            cursor += 1
        rows.append({"offset_bytes": start, "size_bytes": cursor - start})
    return rows


def derive_layout(p11b: Mapping[str, Any]) -> dict[str, Any]:
    layout = p11b.get("byte_layout_contract", {})
    if layout.get("byte_order") != "little_endian":
        raise ArtifactError("byte-order drift")
    source_rows = layout.get("slot_layouts")
    if not isinstance(source_rows, list) or tuple(row.get("layout_id") for row in source_rows if isinstance(row, dict)) != tuple(LAYOUT_SIZES):
        raise ArtifactError("layout identity drift")
    out = []
    for row in source_rows:
        layout_id = row["layout_id"]
        size = row.get("size_bytes")
        if size != LAYOUT_SIZES[layout_id]:
            raise ArtifactError("layout size drift")
        fields = row.get("fields")
        if not isinstance(fields, list) or not fields:
            raise ArtifactError("layout fields missing")
        covered = [False] * size
        normalized = []
        for field in fields:
            name, start, width = field.get("name"), field.get("offset"), field.get("size")
            if not isinstance(name, str) or not isinstance(start, int) or not isinstance(width, int) or start < 0 or width <= 0 or start + width > size:
                raise ArtifactError("slot field outside layout")
            if any(covered[start:start + width]):
                raise ArtifactError("slot field overlap")
            covered[start:start + width] = [True] * width
            normalized.append({"name": name, "offset_bytes": start, "size_bytes": width})
        padding = _padding_ranges(covered)
        padding_bytes = sum(item["size_bytes"] for item in padding)
        out.append({"layout_id": layout_id, "size_bytes": size, "fields": normalized,
                    "declared_field_bytes": size - padding_bytes, "implicit_zero_padding_ranges": padding,
                    "implicit_zero_padding_bytes": padding_bytes})
    table = layout.get("term_table_rules", {})
    if table.get("capacity_slots_each") != 2097152 or table.get("maximum_occupied_slots_each") != 1048576 or table.get("maximum_load_factor_numerator") != 1 or table.get("maximum_load_factor_denominator") != 2:
        raise ArtifactError("term-table capacity or load-factor drift")
    if table["maximum_occupied_slots_each"] * table["maximum_load_factor_denominator"] != table["capacity_slots_each"] * table["maximum_load_factor_numerator"]:
        raise ArtifactError("term-table load-factor equation fails")
    return {"byte_order": "little_endian",
            "implicit_padding_policy": "all_unassigned_slot_bytes_are_zero_initialized_remain_zero_and_are_never_semantic_fields",
            "slot_layouts": out,
            "term_table": {"capacity_slots_each": 2097152, "maximum_occupied_slots_each": 1048576,
                           "load_factor_numerator": 1, "load_factor_denominator": 2,
                           "two_table_reserved_bytes": 2 * 2097152 * 64}}


def derive_arena(p11b: Mapping[str, Any]) -> dict[str, Any]:
    arena = p11b.get("arena_contract", {})
    rows = arena.get("regions_in_offset_order")
    if not isinstance(rows, list) or tuple(row.get("region_id") for row in rows if isinstance(row, dict)) != tuple(REGION_SIZES):
        raise ArtifactError("arena identity drift")
    cursor = 0
    out = []
    for row in rows:
        region_id, offset, size = row.get("region_id"), row.get("offset_bytes"), row.get("size_bytes")
        if size != REGION_SIZES[region_id] or offset != cursor or offset % 64 or size <= 0:
            raise ArtifactError("arena offset size alignment or contiguity drift")
        out.append({"region_id": region_id, "offset_bytes": offset, "size_bytes": size, "end_offset_exclusive": offset + size})
        cursor += size
    if cursor != 872415232 or arena.get("explicit_arena_bytes") != cursor or arena.get("all_regions_reserved_simultaneously_and_never_alias") is not True:
        raise ArtifactError("arena total or nonalias drift")
    return {"base_alignment_bytes": 64, "region_count": len(out), "regions": out,
            "explicit_arena_bytes": cursor, "all_regions_reserved_simultaneously_and_never_alias": True}


def derive_arithmetic(p11b: Mapping[str, Any]) -> dict[str, Any]:
    arithmetic = p11b.get("arithmetic_width_contract", {})
    rows = arithmetic.get("derivation_rows")
    if not isinstance(rows, list) or tuple(row.get("maximum_magnitude_bits") for row in rows if isinstance(row, dict)) != ARITHMETIC_BITS:
        raise ArtifactError("arithmetic derivation drift")
    if arithmetic.get("limb_bits") != 64 or arithmetic.get("stored_magnitude_bits") != 2048 or arithmetic.get("stored_magnitude_limb_count") != 32:
        raise ArtifactError("stored magnitude width drift")
    if arithmetic.get("reused_wide_scratch_bits") != 2112 or arithmetic.get("reused_wide_scratch_limb_count") != 33:
        raise ArtifactError("wide scratch width drift")
    if 32 * 64 != 2048 or 33 * 64 != 2112 or max(ARITHMETIC_BITS) > 2112:
        raise ArtifactError("arithmetic width equation fails")
    return {"limb_bits": 64, "stored_magnitude_bits": 2048, "stored_magnitude_limbs": 32,
            "stored_magnitude_bytes": 256, "wide_scratch_bits": 2112, "wide_scratch_limbs": 33,
            "wide_scratch_bytes": 264,
            "derivation_rows": [{"operation": row["operation"], "maximum_magnitude_bits": row["maximum_magnitude_bits"]} for row in rows],
            "largest_derived_magnitude_bits": 2050, "scratch_margin_over_largest_derived_bits": 62,
            "implementation_path_proof_established": False}


def derive_runtime(p11b: Mapping[str, Any]) -> dict[str, Any]:
    rows = p11b.get("runtime_bound_target_ledger")
    if not isinstance(rows, list) or tuple(row.get("component_id") for row in rows if isinstance(row, dict)) != tuple(RUNTIME_TARGETS):
        raise ArtifactError("runtime component identity drift")
    normalized = []
    for row in rows:
        component, target = row.get("component_id"), row.get("target_bytes")
        if target != RUNTIME_TARGETS[component]:
            raise ArtifactError("runtime component target drift")
        normalized.append({"component_id": component, "target_bytes": target, "status": row.get("status")})
    total = sum(row["target_bytes"] for row in normalized)
    rules = p11b.get("runtime_target_rules", {})
    if total != 1028653056 or rules.get("target_component_sum_bytes") != total or rules.get("difference_to_fixed_cap_bytes") != 2147483648 - total:
        raise ArtifactError("runtime target arithmetic drift")
    if rules.get("sum_is_a_preimplementation_target_not_an_exact_peak_bound") is not True or rules.get("difference_is_not_proven_headroom") is not True:
        raise ArtifactError("runtime nonclaim drift")
    return {"components": normalized, "target_component_sum_bytes": total, "fixed_process_cap_bytes": 2147483648,
            "difference_to_fixed_cap_bytes": 2147483648 - total, "sum_is_exact_process_peak": False,
            "difference_is_proven_headroom": False, "kernel_cgroup_accounting_bound_established": False}


def derive_prelude(p11b: Mapping[str, Any]) -> dict[str, Any]:
    row = p11b.get("prelude_and_semantics_contract", {})
    expected = {"serialized_P6_step2_term_state_available": False, "step1_output_term_count": 42704,
                "step1_output_term_stream_sha256": "067f02a72d50f8061c746896d9eb02e3b60f7e5d6b42f21f0191b8e5887a9c9e",
                "step2_output_term_count": 284847,
                "step2_output_term_stream_sha256": "9bd44992823cc6f8cf731f84954840d4927a972fb6a78c1583c3d8c0983a7c51",
                "frozen_trig_entries_sha256": "2cf79510f1f76728e9cbe22cd168d220845b0be328833d04f0da322da331ee0a"}
    if any(row.get(key) != value for key, value in expected.items()):
        raise ArtifactError("prelude checkpoint custody drift")
    if row.get("required_action") != "reconstruct_frozen_step1_and_step2_in_the_same_explicit_memory_process_before_step3":
        raise ArtifactError("prelude reconstruction obligation drift")
    return {**expected, "required_action": row["required_action"], "semantic_equivalence_established": False}


def derive_manifest(p11b: Mapping[str, Any]) -> dict[str, Any]:
    if p11b.get("contract_id") != "MAJORANA-P11-B-PREIMPLEMENTATION-CONTRACT-PACK-V1":
        raise ArtifactError("P11-B identity drift")
    return {"schema_version": 1, "manifest_id": "MAJORANA-P11-C-STATIC-PROOF-ARTIFACT-MANIFEST-V1",
            "source_P11_B_contract_raw_sha256": "590ee6f0054aea499145ab388efbca45b20a56306b2f069101990ab206b80f80",
            "layout_artifact": derive_layout(p11b), "arena_artifact": derive_arena(p11b),
            "arithmetic_artifact": derive_arithmetic(p11b), "runtime_target_artifact": derive_runtime(p11b),
            "prelude_checkpoint_artifact": derive_prelude(p11b), "adversarial_mutation_ids": list(MUTATIONS),
            "proof_scope": "CONTRACT_LEVEL_STATIC_ARTIFACTS_ONLY_NO_CANDIDATE_IMPLEMENTATION_POSTLINK_SEMANTICS_OR_EXACT_PEAK"}


def expected_report(contract: Mapping[str, Any], contract_raw: bytes, sources: list[dict[str, Any]],
                    manifest: Mapping[str, Any], manifest_raw: bytes) -> dict[str, Any]:
    return {"schema_version": 1, "report_type": "majorana_p11_c_static_proof_artifact_report_v1",
            "gate_id": "P11-C-STATIC-PROOF-ARTIFACT-PACK-V1", "parent_commit": DIRECT_PARENT,
            "contract_raw_sha256": sha256(contract_raw), "contract_canonical_sha256": sha256(canonical_bytes(contract)),
            "source_inputs": sources, "manifest_raw_sha256": sha256(manifest_raw),
            "manifest_canonical_sha256": sha256(canonical_bytes(manifest)), "outcome": OUTCOME,
            "section_disposition": contract["section_disposition"],
            "derived_summary": {"slot_layout_count": len(manifest["layout_artifact"]["slot_layouts"]),
                                "implicit_zero_padding_bytes_total": sum(row["implicit_zero_padding_bytes"] for row in manifest["layout_artifact"]["slot_layouts"]),
                                "arena_region_count": manifest["arena_artifact"]["region_count"],
                                "explicit_arena_bytes": manifest["arena_artifact"]["explicit_arena_bytes"],
                                "stored_magnitude_bits": manifest["arithmetic_artifact"]["stored_magnitude_bits"],
                                "wide_scratch_bits": manifest["arithmetic_artifact"]["wide_scratch_bits"],
                                "target_component_sum_bytes": manifest["runtime_target_artifact"]["target_component_sum_bytes"],
                                "difference_to_fixed_cap_bytes": manifest["runtime_target_artifact"]["difference_to_fixed_cap_bytes"],
                                "adversarial_mutation_count": len(manifest["adversarial_mutation_ids"])},
            "unresolved_after_this_pack": contract["unresolved_after_this_pack"],
            "candidate_implementation_present": False, "toolchain_source_custody_established": False,
            "postlink_and_stack_proof_established": False, "kernel_cgroup_accounting_bound_established": False,
            "semantic_equivalence_established": False, "fixed_process_cap_bytes": 2147483648,
            "contract_target_component_sum_bytes": 1028653056, "difference_to_fixed_cap_bytes": 1118830592,
            "difference_is_proven_headroom": False, "exact_static_process_peak_bytes": None,
            "strict_integer_peak_less_than_fixed_cap": None, "implementation_gate": "CLOSED", "execution_gate": "CLOSED",
            "scientific_authority": "NONE", "execution_authority": False, "implementation_authority": False,
            "candidate_selection_authority": False, "candidate_or_cap_change_authority": False,
            "resource_or_no_go_authority": False, "resource_no_go_inference": False, "S0_authority": False,
            "certificate_eligible": False, "result_contract_eligible": False,
            "next_governance_requirement": "NEW_INDEPENDENT_POST_P11_C_GOVERNANCE_REQUIRED_BEFORE_ANY_CANDIDATE_SOURCE"}


def validate_content() -> dict[str, Any]:
    contract, contract_raw = load_json(BASE / CONTRACT_NAME, "P11-C contract")
    validate_contract(contract)
    sources, values = validate_sources(contract)
    p11b = loads_strict(values["majorana_certificate_p11b_preimplementation_contract_pack_contract.json"], "P11-B contract")
    expected_manifest = derive_manifest(p11b)
    manifest, manifest_raw = load_json(BASE / MANIFEST_NAME, "P11-C manifest", canonical=True)
    if manifest != expected_manifest:
        raise ArtifactError("manifest reconstruction drift")
    report, _ = load_json(BASE / REPORT_NAME, "P11-C report", canonical=True)
    if report != expected_report(contract, contract_raw, sources, manifest, manifest_raw):
        raise ArtifactError("report reconstruction drift")
    return {"status": "VERIFIED_P11_C_STATIC_PROOF_ARTIFACT_PACK", "outcome": OUTCOME,
            "implicit_zero_padding_bytes_total": 4, "target_component_sum_bytes": 1028653056,
            "implementation_gate": "CLOSED", "execution_gate": "CLOSED"}


def validate_lifecycle() -> str:
    if _git("rev-parse", "HEAD").strip() != DIRECT_PARENT:
        raise ArtifactError("staging must begin at P11-G2")
    staged = {path: status for status, path in (line.split("\t", 1) for line in _git("diff", "--cached", "--name-status", "--no-renames").splitlines())}
    if staged != CHANGED_PATHS:
        raise ArtifactError("staged changed-path set drift")
    if _git("diff", "--name-only").strip() or _git("ls-files", "--others", "--exclude-standard").strip():
        raise ArtifactError("unstaged or untracked files are forbidden")
    return "STAGED_DIRECT_CHILD"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-content", action="store_true")
    parser.add_argument("--verify-lifecycle", action="store_true")
    args = parser.parse_args()
    if not args.verify_content and not args.verify_lifecycle:
        parser.error("choose a verification mode")
    if args.verify_content:
        print(json.dumps(validate_content(), sort_keys=True))
    if args.verify_lifecycle:
        print(validate_lifecycle())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
