#!/usr/bin/env python3
"""Adversarial tests for P11-G3 evidence-feasibility governance."""

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
PATH = BASE / "majorana_certificate_p11_g3_evidence_feasibility_governance_validator.py"
SPEC = importlib.util.spec_from_file_location("p11g3", PATH)
assert SPEC and SPEC.loader
G3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = G3
SPEC.loader.exec_module(G3)


class P11G3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.raw = G3.load_json(BASE / G3.CONTRACT_NAME, "contract")
        G3.validate_contract(cls.contract)
        cls.projection = G3.validate_p11c(cls.contract)
        cls.expected = G3.expected_record(cls.contract, cls.raw, cls.projection)
        cls.record, cls.record_raw = G3.load_json(BASE / G3.RECORD_NAME, "record", canonical=True)

    def test_content_opens_only_read_only_evidence_feasibility(self) -> None:
        result = G3.validate_content()
        self.assertEqual(result["disposition"], G3.DISPOSITION)
        self.assertEqual(result["next_gate"], G3.NEXT_GATE)
        self.assertEqual(self.record_raw, G3.canonical_bytes(self.record))
        self.assertEqual(self.record["implementation_gate"], "CLOSED")
        self.assertEqual(self.record["execution_gate"], "CLOSED")

    def test_p11c_topology_custody_and_projection(self) -> None:
        self.assertEqual(G3._parent(G3.DIRECT_PARENT), G3.G2)
        self.assertEqual(G3._paths(G3.DIRECT_PARENT), G3.P11C_PATHS)
        self.assertEqual(self.projection["implicit_zero_padding_bytes_total"], 4)
        self.assertEqual(self.projection["wide_scratch_bits"], 2112)

    def test_forbidden_authority_mutations_fail(self) -> None:
        keys = ("candidate_source_allowed", "C_assembly_or_linker_script_source_allowed", "prototype_allowed",
                "compilation_or_linking_allowed", "Julia_or_candidate_execution_allowed", "benchmark_or_host_measurement_allowed",
                "package_index_update_installation_or_environment_mutation_allowed", "binary_or_source_archive_download_allowed",
                "scientific_schedule_semantics_or_cap_change_allowed")
        for key in keys:
            changed = copy.deepcopy(self.contract)
            changed["P11_D_authorization"][key] = True
            with self.subTest(key=key), self.assertRaises(G3.GovernanceError):
                G3.validate_contract(changed)

    def test_record_cannot_claim_custody_peak_or_open_gates(self) -> None:
        for key, value in (("source_archive_download_allowed", True), ("candidate_source_allowed", True),
                           ("exact_static_process_peak_bytes", 1028653056), ("difference_is_proven_headroom", True),
                           ("semantic_equivalence_established", True), ("implementation_gate", "OPEN"),
                           ("execution_gate", "OPEN"), ("resource_no_go_inference", True)):
            changed = copy.deepcopy(self.record)
            changed[key] = value
            with self.subTest(key=key):
                self.assertNotEqual(changed, self.expected)

    def test_p11c_blob_drift_fails(self) -> None:
        with mock.patch.object(G3, "_git_bytes", return_value=b"wrong"):
            with self.assertRaises(G3.GovernanceError):
                G3.validate_p11c(self.contract)

    def test_exact_staged_lifecycle(self) -> None:
        staged = "".join(f"{status}\t{path}\n" for path, status in G3.CHANGED_PATHS.items())
        def good(*args):
            if args == ("rev-parse", "HEAD"):
                return G3.DIRECT_PARENT + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return staged
            if args in (("diff", "--name-only"), ("ls-files", "--others", "--exclude-standard")):
                return ""
            raise AssertionError(args)
        with mock.patch.object(G3, "_git", side_effect=good):
            self.assertEqual(G3.validate_lifecycle(), "STAGED_DIRECT_CHILD")

    def test_subprocesses_are_git_only(self) -> None:
        tree = ast.parse(PATH.read_text(encoding="utf-8"))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"]
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertEqual(call.args[0].elts[0].value, "git")


if __name__ == "__main__":
    unittest.main()
