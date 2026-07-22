#!/usr/bin/env python3
"""Static, source-only checker for Free Recall Strategy R11 C1."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable


FILES = {
    "cargo": "crates/bridge/Cargo.toml",
    "lib": "crates/bridge/src/lib.rs",
    "hub": "crates/bridge/src/hub.rs",
    "main": "crates/bridge/src/main.rs",
    "tools": "crates/bridge/src/mcp_tools.rs",
    "tests": "crates/bridge/src/mcp_tools/tests.rs",
    "module": "crates/bridge/src/episode_observation_curation_batch.rs",
}


def load(root: Path) -> dict[str, str]:
    return {name: (root / path).read_text(encoding="utf-8") for name, path in FILES.items()}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate(source: dict[str, str]) -> list[str]:
    errors: list[str] = []
    cargo = source["cargo"]
    default_match = re.search(r"^default\s*=\s*\[([^\n]*)\]", cargo, re.MULTILINE)
    if not default_match or "episode-observation-slice-c1" in default_match.group(1):
        errors.append("feature_default_on")
    if 'episode-observation-slice-c1 = []' not in cargo:
        errors.append("feature_not_isolated")

    lib = source["lib"]
    declaration = (
        '#[cfg(feature = "episode-observation-slice-c1")]\n'
        "pub(crate) mod episode_observation_curation_batch;"
    )
    if declaration not in lib:
        errors.append("module_not_default_off_private")

    hub = source["hub"]
    if "pub(crate) curation_batch_observer" not in hub:
        errors.append("hub_capability_not_private")
    if "Option<Arc<dyn CurationBatchObservationCapability>>" not in hub:
        errors.append("hub_capability_not_optional")
    if "pub(crate) fn curation_batch_observer" not in hub:
        errors.append("hub_builder_not_private")
    if hub.count('#[cfg(feature = "episode-observation-slice-c1")]') < 4:
        errors.append("hub_feature_guard_missing")

    main = source["main"]
    if "curation_batch_observer" in main or "CurationBatchObservationCapability" in main:
        errors.append("production_wiring_present")

    module = source["module"]
    for forbidden in (
        "SqliteStore",
        "StateStore",
        "EpisodeRefKeyProvider",
        "ab_store",
        "std::env",
        "AGENT_BRIDGE",
        "memory_search",
        "sync_export",
    ):
        if forbidden in module:
            errors.append("module_coupling_present")
    if re.search(r"(?m)^pub (?!\(crate\))", module):
        errors.append("module_public_surface")
    test_boundary = module.find("#[cfg(test)]")
    production_impl = module.find("impl CurationBatchObservationCapability")
    if test_boundary < 0 or production_impl < test_boundary:
        errors.append("production_capability_implementation_present")
    for required in (
        "first observation error drops the attempt",
        "observe_saved(memory_key, saved_ordinal).await",
        "self.attempt = None",
        "self.saved_count == 0",
        "attempt.finish(self.saved_count).await",
    ):
        if required not in module:
            errors.append("fail_closed_or_ordering_contract_missing")

    tools = source["tools"]
    if "candidates.len() - saved.len() - errors.len()" in tools:
        errors.append("mixed_error_subtraction_present")
    for required in (
        "SessionCurateCandidateLedger",
        "auxiliary_errors: Vec<String>",
        "candidate_errors: Vec<String>",
        "record_duplicate()",
        "candidate_error_count",
    ):
        if required not in tools:
            errors.append("explicit_outcome_ledger_missing")
    order_tokens = [
        'record_auxiliary_error(format!("prior-handoff scan: {e}"))',
        "CurationBatchObservationRun::begin(",
        "for mem in &candidates",
        "store.memory_save(mem).await",
        ".observe_memory_saved(&mem.key)",
        "curation_batch_observation.finish().await",
    ]
    positions = [tools.find(token) for token in order_tokens]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        errors.append("producer_call_order_drift")
    if "record_session_curate_event(\n            &store,\n            false,\n            saved.len(),\n            skipped,\n            candidate_error_count," not in tools:
        errors.append("lifecycle_uses_mixed_error_count")

    tests = source["tests"] + module[test_boundary:]
    for required in (
        "session_curate_candidate_ledger_keeps_auxiliary_errors_out_of_counts",
        "absent_capability_and_empty_batch_emit_nothing",
        "saved_ordinals_are_contiguous_and_close_matches",
        "first_item_failure_latches_and_suppresses_close",
        "begin_close_and_zero_save_fail_closed_without_core_error",
    ):
        if required not in tests:
            errors.append("source_test_case_missing")
    return sorted(set(errors))


def mutate(source: dict[str, str], key: str, old: str, new: str) -> None:
    if old not in source[key]:
        raise AssertionError(f"mutation anchor missing: {key}: {old}")
    source[key] = source[key].replace(old, new, 1)


def swap_first(source: dict[str, str], key: str, first: str, second: str) -> None:
    value = source[key]
    first_at = value.find(first)
    second_at = value.find(second)
    if first_at < 0 or second_at < 0 or first_at >= second_at:
        raise AssertionError(f"ordered mutation anchors missing: {key}")
    placeholder = "__R11_C1_SWAP_PLACEHOLDER__"
    value = value.replace(first, placeholder, 1)
    value = value.replace(second, first, 1)
    source[key] = value.replace(placeholder, second, 1)


def mutations() -> list[tuple[str, str, Callable[[dict[str, str]], None]]]:
    return [
        ("default_on", "feature_default_on", lambda s: mutate(s, "cargo", 'default = ["onnx-embed"]', 'default = ["onnx-embed", "episode-observation-slice-c1"]')),
        ("feature_forwards_store", "feature_not_isolated", lambda s: mutate(s, "cargo", 'episode-observation-slice-c1 = []', 'episode-observation-slice-c1 = ["ab-store/episode-observation-slice-b"]')),
        ("remove_module_cfg", "module_not_default_off_private", lambda s: mutate(s, "lib", '#[cfg(feature = "episode-observation-slice-c1")]\n', "")),
        ("public_hub_field", "hub_capability_not_private", lambda s: mutate(s, "hub", "pub(crate) curation_batch_observer", "pub curation_batch_observer")),
        ("wire_main", "production_wiring_present", lambda s: s.__setitem__("main", s["main"] + "\n// curation_batch_observer\n")),
        ("couple_sqlite", "module_coupling_present", lambda s: s.__setitem__("module", s["module"] + "\n// SqliteStore\n")),
        ("public_module_api", "module_public_surface", lambda s: s.__setitem__("module", s["module"] + "\npub struct LeakedCapability;\n")),
        ("production_capability", "production_capability_implementation_present", lambda s: mutate(s, "module", "#[cfg(test)]", "impl CurationBatchObservationCapability for Production {}\n#[cfg(test)]")),
        ("restore_mixed_subtraction", "mixed_error_subtraction_present", lambda s: s.__setitem__("tools", s["tools"] + "\n// candidates.len() - saved.len() - errors.len()\n")),
        ("remove_auxiliary_split", "explicit_outcome_ledger_missing", lambda s: mutate(s, "tools", "auxiliary_errors: Vec<String>", "errors: Vec<String>")),
        ("item_before_save", "producer_call_order_drift", lambda s: swap_first(s, "tools", "store.memory_save(mem).await", ".observe_memory_saved(&mem.key)")),
        ("remove_failure_latch", "fail_closed_or_ordering_contract_missing", lambda s: mutate(s, "module", "self.attempt = None", "// attempt retained")),
        ("remove_zero_save_guard", "fail_closed_or_ordering_contract_missing", lambda s: mutate(s, "module", "self.saved_count == 0", "false")),
        ("drop_source_test", "source_test_case_missing", lambda s: mutate(s, "tests", "session_curate_candidate_ledger_keeps_auxiliary_errors_out_of_counts", "removed_ledger_test")),
    ]


def run(root: Path) -> dict[str, Any]:
    source = load(root)
    canonical_errors = validate(source)
    mutation_rows = []
    for name, expected, apply in mutations():
        candidate = copy.deepcopy(source)
        apply(candidate)
        mutation_rows.append({
            "name": name,
            "expected_error": expected,
            "rejected_as_expected": expected in validate(candidate),
        })
    gates = {
        "canonical_source": not canonical_errors,
        "directed_mutations": all(row["rejected_as_expected"] for row in mutation_rows),
        "zero_runtime_authority": not canonical_errors,
    }
    return {
        "schema_version": "agent_bridge.free_recall_strategy_r11_c1_source_report.v0",
        "fixture": "public_source_only",
        "source_sha256": {FILES[name]: sha256_text(value) for name, value in sorted(source.items())},
        "canonical_errors": canonical_errors,
        "mutation_count": len(mutation_rows),
        "mutation_rejection_count": sum(row["rejected_as_expected"] for row in mutation_rows),
        "mutations": mutation_rows,
        "gates": gates,
        "verdict": "PASS" if all(gates.values()) else "FAIL",
        "authority": {
            "source_landed": True,
            "cargo_invoked": False,
            "feature_compiled": False,
            "tests_executed": False,
            "database_accessed": False,
            "producer_integrated": False,
            "c2_open": False,
            "merge_authorized": False,
            "deployment_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    report = run(args.root)
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    if args.selftest:
        assert report["verdict"] == "PASS", encoded
        assert report["mutation_count"] == report["mutation_rejection_count"]
        print("selftest: PASS")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
