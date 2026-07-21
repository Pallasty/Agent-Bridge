#!/usr/bin/env python3
"""Adversarial tests for independent P11-C static proof artifacts."""

from __future__ import annotations

import ast
import copy
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
PATH = BASE / "majorana_certificate_p11c_static_proof_artifact_independent_checker.py"
SPEC = importlib.util.spec_from_file_location("p11c_checker", PATH)
assert SPEC and SPEC.loader
P11C = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = P11C
SPEC.loader.exec_module(P11C)


class P11CStaticProofArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.contract_raw = P11C.load_json(BASE / P11C.CONTRACT_NAME, "contract")
        P11C.validate_contract(cls.contract)
        cls.sources, cls.values = P11C.validate_sources(cls.contract)
        cls.p11b = P11C.loads_strict(cls.values["majorana_certificate_p11b_preimplementation_contract_pack_contract.json"], "P11-B contract")
        cls.expected_manifest = P11C.derive_manifest(cls.p11b)
        cls.manifest, cls.manifest_raw = P11C.load_json(BASE / P11C.MANIFEST_NAME, "manifest", canonical=True)
        cls.expected_report = P11C.expected_report(cls.contract, cls.contract_raw, cls.sources, cls.manifest, cls.manifest_raw)
        cls.report, cls.report_raw = P11C.load_json(BASE / P11C.REPORT_NAME, "report", canonical=True)

    def test_content_establishes_only_partial_static_artifacts(self) -> None:
        result = P11C.validate_content()
        self.assertEqual(result["outcome"], P11C.OUTCOME)
        self.assertEqual(result["implementation_gate"], "CLOSED")
        self.assertEqual(result["execution_gate"], "CLOSED")
        self.assertEqual(self.manifest, self.expected_manifest)
        self.assertEqual(self.report, self.expected_report)
        self.assertEqual(self.manifest_raw, P11C.canonical_bytes(self.manifest))
        self.assertEqual(self.report_raw, P11C.canonical_bytes(self.report))

    def test_layout_gap_enumeration_and_table_capacity(self) -> None:
        rows = {row["layout_id"]: row for row in self.manifest["layout_artifact"]["slot_layouts"]}
        self.assertEqual(rows["TERM_SLOT_64"]["implicit_zero_padding_ranges"], [{"offset_bytes": 49, "size_bytes": 3}])
        self.assertEqual(rows["RANK_ROW_320"]["implicit_zero_padding_ranges"], [{"offset_bytes": 305, "size_bytes": 1}])
        self.assertEqual(sum(row["implicit_zero_padding_bytes"] for row in rows.values()), 4)
        self.assertEqual(self.manifest["layout_artifact"]["term_table"]["two_table_reserved_bytes"], 268435456)

    def test_slot_overlap_and_shrink_mutations_fail(self) -> None:
        changed = copy.deepcopy(self.p11b)
        changed["byte_layout_contract"]["slot_layouts"][0]["fields"][1]["offset"] = 31
        with self.assertRaises(P11C.ArtifactError):
            P11C.derive_layout(changed)
        changed = copy.deepcopy(self.p11b)
        changed["byte_layout_contract"]["slot_layouts"][0]["size_bytes"] = 63
        with self.assertRaises(P11C.ArtifactError):
            P11C.derive_layout(changed)

    def test_capacity_and_load_factor_mutations_fail(self) -> None:
        changed = copy.deepcopy(self.p11b)
        changed["byte_layout_contract"]["term_table_rules"]["capacity_slots_each"] -= 1
        with self.assertRaises(P11C.ArtifactError):
            P11C.derive_layout(changed)
        changed = copy.deepcopy(self.p11b)
        changed["byte_layout_contract"]["term_table_rules"]["maximum_load_factor_numerator"] = 3
        changed["byte_layout_contract"]["term_table_rules"]["maximum_load_factor_denominator"] = 4
        with self.assertRaises(P11C.ArtifactError):
            P11C.derive_layout(changed)

    def test_arena_overlap_mutation_fails(self) -> None:
        changed = copy.deepcopy(self.p11b)
        changed["arena_contract"]["regions_in_offset_order"][4]["offset_bytes"] -= 64
        with self.assertRaises(P11C.ArtifactError):
            P11C.derive_arena(changed)

    def test_scratch_2049_mutation_fails(self) -> None:
        changed = copy.deepcopy(self.p11b)
        changed["arithmetic_width_contract"]["reused_wide_scratch_bits"] = 2049
        with self.assertRaises(P11C.ArtifactError):
            P11C.derive_arithmetic(changed)
        self.assertEqual(self.manifest["arithmetic_artifact"]["scratch_margin_over_largest_derived_bits"], 62)
        self.assertFalse(self.manifest["arithmetic_artifact"]["implementation_path_proof_established"])

    def test_runtime_sum_and_headroom_mutations_fail(self) -> None:
        changed = copy.deepcopy(self.p11b)
        changed["runtime_bound_target_ledger"][0]["target_bytes"] -= 1
        with self.assertRaises(P11C.ArtifactError):
            P11C.derive_runtime(changed)
        changed = copy.deepcopy(self.p11b)
        changed["runtime_target_rules"]["difference_is_not_proven_headroom"] = False
        with self.assertRaises(P11C.ArtifactError):
            P11C.derive_runtime(changed)
        self.assertFalse(self.report["difference_is_proven_headroom"])
        self.assertIsNone(self.report["exact_static_process_peak_bytes"])

    def test_prelude_hash_mutation_fails_and_equivalence_stays_open(self) -> None:
        changed = copy.deepcopy(self.p11b)
        changed["prelude_and_semantics_contract"]["step2_output_term_stream_sha256"] = "0" * 64
        with self.assertRaises(P11C.ArtifactError):
            P11C.derive_prelude(changed)
        self.assertFalse(self.manifest["prelude_checkpoint_artifact"]["semantic_equivalence_established"])
        self.assertFalse(self.report["semantic_equivalence_established"])

    def test_authority_mutations_fail_closed(self) -> None:
        for key in ("candidate_source_allowed", "C_assembly_or_linker_script_source_allowed", "compilation_or_linking_allowed",
                    "Julia_or_candidate_execution_allowed", "benchmark_or_host_measurement_allowed",
                    "package_installation_or_environment_mutation_allowed", "binary_or_source_archive_download_allowed",
                    "network_retrieval_allowed", "scientific_schedule_semantics_or_cap_change_allowed"):
            changed = copy.deepcopy(self.contract)
            changed["scope"][key] = True
            with self.subTest(key=key), self.assertRaises(P11C.ArtifactError):
                P11C.validate_contract(changed)

    def test_source_custody_drift_fails(self) -> None:
        with mock.patch.object(P11C, "_git_bytes", return_value=b"wrong"):
            with self.assertRaises(P11C.ArtifactError):
                P11C.validate_sources(self.contract)

    def test_exact_staged_lifecycle(self) -> None:
        staged = "".join(f"{status}\t{path}\n" for path, status in P11C.CHANGED_PATHS.items())
        def good(*args):
            if args == ("rev-parse", "HEAD"):
                return P11C.DIRECT_PARENT + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return staged
            if args in (("diff", "--name-only"), ("ls-files", "--others", "--exclude-standard")):
                return ""
            raise AssertionError(args)
        with mock.patch.object(P11C, "_git", side_effect=good):
            self.assertEqual(P11C.validate_lifecycle(), "STAGED_DIRECT_CHILD")

    def test_checker_is_independent_git_only_and_non_candidate(self) -> None:
        source = PATH.read_text(encoding="utf-8")
        self.assertNotIn("majorana_certificate_p11b_preimplementation_contract_pack_validator", source)
        self.assertNotIn("majorana_certificate_p11b_preimplementation_contract_pack_report", source)
        tree = ast.parse(source)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"]
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertEqual(call.args[0].elts[0].value, "git")


if __name__ == "__main__":
    unittest.main()
