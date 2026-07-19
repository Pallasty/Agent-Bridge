#!/usr/bin/env python3
"""Independent checker for the T11 clock-skew authority/resource decision."""

from __future__ import annotations
import argparse, ast, copy, hashlib, importlib.util, json, sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Mapping, NoReturn
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
REVIEWER_REL = "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_clock_skew_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py"
CHECKER_REL = "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_clock_skew_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.py"
OWNER_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_clock_skew_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
EXPECTED_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_clock_skew_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv"
MANIFEST_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_clock_skew_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_v0.json"
SEMANTIC_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
PREDECESSOR_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_freshness_synthetic_exact_t09_receipt_track_observed_at_validation_checked_at_decision_recheck_at_expires_at_and_max_age_seconds_verifier_isolated_lab_v1_pack_v0.json"
OWNER_KEYS = ("authorized_component_contract", "boundary", "date", "decision", "implementation_authority", "next_unit", "nonclaims", "owner_implementation_actor", "predecessor", "resource_binding", "rollback", "schema", "schema_version", "state_machine", "status")
PACK_PATHS = (
    "docs/reports/goal-c-u/2026-07-19-biocortex-track-b-reference-provider-fault-injection-runner-clock-skew-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.md",
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-clock-skew-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh",
    REVIEWER_REL, CHECKER_REL, EXPECTED_REL, OWNER_REL, MANIFEST_REL,
)
class CheckError(ValueError): pass
def require(ok: bool, code: str, detail: str) -> None:
    if not ok: raise CheckError(f"{code}: {detail}")
def path(rel: str) -> Path:
    require(type(rel) is str and rel and not rel.startswith("/") and all(x not in ("", ".", "..") for x in rel.split("/")), "E_PATH", rel)
    candidate = ROOT.joinpath(*rel.split("/")); resolved = candidate.resolve(strict=True); require(ROOT in resolved.parents and candidate.is_file() and not candidate.is_symlink(), "E_PATH_ESCAPE", rel); return candidate
def sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def raw_sha(rel: str) -> str: return sha(path(rel).read_bytes())
def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items: require(type(key) is str and key not in result, "E_JSON_DUPLICATE", repr(key)); result[key] = value
    return result
def no_float(value: str) -> NoReturn: raise CheckError(f"E_JSON_FLOAT:{value}")
def parse_int(value: str) -> int:
    result = int(value); require(-(2**63) <= result <= 2**63 - 1, "E_JSON_INT", value); return result
def load(rel: str) -> dict[str, Any]:
    raw = path(rel).read_bytes(); text = raw.decode("utf-8", "strict"); decoder = json.JSONDecoder(object_pairs_hook=pairs, parse_int=parse_int, parse_float=no_float, parse_constant=no_float, strict=True); value, end = decoder.raw_decode(text); require(not text[end:].strip() and type(value) is dict, "E_JSON_ROOT", rel); return value
def module_load() -> ModuleType:
    p = path(REVIEWER_REL); spec = importlib.util.spec_from_file_location("_t11_decision", p); require(spec is not None and spec.loader is not None, "E_IMPORT", "spec"); module = importlib.util.module_from_spec(spec); sys.modules["_t11_decision"] = module; spec.loader.exec_module(module); return module
def expect_fail(module: ModuleType, owner: dict[str, Any], manifest: dict[str, Any], semantic: dict[str, Any], predecessor: dict[str, Any], op: Callable[[dict[str, Any]], None], label: str) -> None:
    candidate = copy.deepcopy(owner); op(candidate)
    try: module.validate(candidate, manifest, semantic, predecessor)
    except module.ReviewError: return
    raise CheckError(f"E_MUTATION_ACCEPTED:{label}")
def independent_checks(module: ModuleType) -> dict[str, int]:
    owner, manifest, semantic, predecessor = map(load, (OWNER_REL, MANIFEST_REL, SEMANTIC_REL, PREDECESSOR_REL)); module.validate(owner, manifest, semantic, predecessor)
    require(set(owner) == set(OWNER_KEYS), "E_OWNER_KEYS", "closed")
    contract = owner["authorized_component_contract"]; require(set(contract) == {"binding_model", "clock_skew_arithmetic", "input_topology", "local_scope", "output_boundary", "reviewer_topology"}, "E_CONTRACT_KEYS", "closed")
    counts = {"closed_world": 0, "grounding": 0, "boundary": 0, "resource": 0, "state": 0}
    for key in OWNER_KEYS:
        expect_fail(module, owner, manifest, semantic, predecessor, lambda x, k=key: x.pop(k), f"drop:{key}"); counts["closed_world"] += 1
    mutations = (
        (lambda x: x.__setitem__("decision", "ALLOW"), "decision"),
        (lambda x: x.__setitem__("next_unit", "DRIFT"), "next"),
        (lambda x: x["predecessor"].__setitem__("exact_release_commit", "0" * 40), "baseline"),
        (lambda x: x["predecessor"].__setitem__("implementation_authority_consumed", False), "pred-consumed"),
        (lambda x: x["authorized_component_contract"]["binding_model"].__setitem__("policy_match_dimension_count", 6), "dimensions"),
        (lambda x: x["authorized_component_contract"]["binding_model"].__setitem__("request_field_count", 4), "request-count"),
        (lambda x: x["authorized_component_contract"]["binding_model"]["profiles"].reverse(), "profile-order"),
        (lambda x: x["authorized_component_contract"]["input_topology"].__setitem__("public_input_count", 17), "input-count"),
        (lambda x: x["authorized_component_contract"]["input_topology"]["review_order"].reverse(), "review-order"),
    )
    for op, label in mutations: expect_fail(module, owner, manifest, semantic, predecessor, op, label); counts["grounding"] += 1
    for index in range(2):
        arithmetic_mutations = (
            (lambda p: p.__setitem__("validation_reference_time_unix_seconds", p["decision_recheck_reference_time_unix_seconds"] + 1), "reference-order-validation"),
            (lambda p: p.__setitem__("validation_reference_time_unix_seconds", p["validation_reference_time_unix_seconds"] - 1000), "validation-skew"),
            (lambda p: p.__setitem__("decision_recheck_reference_time_unix_seconds", p["decision_recheck_reference_time_unix_seconds"] + 1000), "decision-skew"),
            (lambda p: p.__setitem__("decision_recheck_reference_time_unix_seconds", p["validation_reference_time_unix_seconds"] - 1), "reference-order-decision"),
            (lambda p: p.__setitem__("maximum_clock_skew_seconds", 301), "maximum-bound"),
            (lambda p: p.__setitem__("maximum_clock_skew_seconds", 1), "skew-too-small"),
        )
        for op, label in arithmetic_mutations:
            expect_fail(module, owner, manifest, semantic, predecessor, lambda x, i=index, mutate=op: mutate(x["authorized_component_contract"]["binding_model"]["profiles"][i]), f"arithmetic:{index}:{label}"); counts["grounding"] += 1
    for field, value in (("current_released_component_total", 9), ("future_successor_component_total_after_exact_integrated_full_gate", 10), ("production_ingestion_controls_implemented", 1), ("runtime_authority", True), ("provider_authority", True)):
        expect_fail(module, owner, manifest, semantic, predecessor, lambda x, f=field, v=value: x["boundary"].__setitem__(f, v), f"boundary:{field}"); counts["boundary"] += 1
    for field, value in (("effective_external_paid_spend_cap", 1), ("network", True)):
        expect_fail(module, owner, manifest, semantic, predecessor, lambda x, f=field, v=value: x["resource_binding"].__setitem__(f, v), f"resource:{field}"); counts["resource"] += 1
    for field, value in (("max_parallel_workers", 2), ("max_predecessor_review_calls", 2), ("max_private_scratch_bytes", 67108865), ("public_input_count", 17), ("max_clock_skew_entries", 3)):
        expect_fail(module, owner, manifest, semantic, predecessor, lambda x, f=field, v=value: x["resource_binding"]["component_limits"].__setitem__(f, v), f"limit:{field}"); counts["resource"] += 1
    for field, value in (("current_state", "CONSUMED_SCOPE_COMPLETE"), ("decision_full_gate_consumes_new_authority", True)):
        expect_fail(module, owner, manifest, semantic, predecessor, lambda x, f=field, v=value: x["state_machine"].__setitem__(f, v), f"state:{field}"); counts["state"] += 1
    forbidden = owner["implementation_authority"]["forbidden_operations"]
    for required in ("ACCESS_AMBIENT_SYSTEM_OR_PROVIDER_CLOCK", "BIND_OR_CLAIM_SIGNED_TRUSTED_TIME", "CLAIM_T12_OWNER_TOCTOU_COVERAGE", "USE_WALL_MONOTONIC_NETWORK_PROVIDER_SIGNED_OR_TRUSTED_TIME"):
        expect_fail(module, owner, manifest, semantic, predecessor, lambda x, r=required: x["implementation_authority"]["forbidden_operations"].remove(r), f"forbidden:{required}"); counts["boundary"] += 1
    expected_modes = {PACK_PATHS[0]: "100644", PACK_PATHS[1]: "100755", **{item: "100644" for item in PACK_PATHS[2:]}}
    require(manifest["packet_path_modes"] == expected_modes, "E_MANIFEST_PATHS", "drift")
    for rel, digest in manifest["raw_sha256"].items(): require(raw_sha(rel) == digest, "E_ARTIFACT_HASH", rel)
    return counts
def source_checks() -> int:
    tree = ast.parse(path(REVIEWER_REL).read_text()); imports = {a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names} | {n.module or "" for n in tree.body if isinstance(n, ast.ImportFrom)}
    require(imports <= {"__future__", "argparse", "hashlib", "json", "sys", "pathlib", "typing"}, "E_SOURCE_IMPORTS", repr(imports))
    text = path(REVIEWER_REL).read_text(); require(not any(token in text for token in ("subprocess", "socket", "requests", "urllib", "os.environ", "time.time", "datetime.now", "open(")), "E_SOURCE_CAPABILITY", "forbidden"); return 12
def evaluate() -> str:
    module = module_load(); counts = independent_checks(module); require(sum(counts.values()) == 54, "E_NEGATIVE_COUNT", repr(counts)); require(source_checks() == 12, "E_SOURCE_COUNT", "12"); output = module.evaluate(); require(output.count("\n") == 56, "E_RECEIPT_LINES", str(output.count("\n"))); return output
def self_test() -> str:
    evaluate(); names = ("json_duplicate", "json_float", "owner_closed", "baseline_bound", "predecessor_consumed", "profiles_ordered", "three_request_fields", "five_match_dimensions", "future_date_arithmetic", "symmetric_skew_arithmetic", "mode_first", "t10_once", "request_last", "no_ambient_clock", "t12_closed", "source_capability_free"); return "".join(f"self_test_{name}\tpass\n" for name in names)
def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--self-test", action="store_true"); args = parser.parse_args()
    try: sys.stdout.write(self_test() if args.self_test else evaluate()); return 0
    except (CheckError, OSError, UnicodeError, ValueError, TypeError, KeyError, AssertionError, StopIteration) as error: print(f"check_error\t{error}", file=sys.stderr); return 1
if __name__ == "__main__": raise SystemExit(main())
