#!/usr/bin/env python3
"""Adversarial tests for P11-G2 proof-artifact governance."""

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
PATH = BASE / "majorana_certificate_p11_g2_proof_artifact_governance_validator.py"
SPEC = importlib.util.spec_from_file_location("p11g2", PATH)
assert SPEC and SPEC.loader
G2 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = G2
SPEC.loader.exec_module(G2)


class P11G2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.raw = G2.load_json(BASE / G2.CONTRACT_NAME, "contract")
        G2.validate_contract(cls.contract)
        cls.projection = G2.validate_p11b(cls.contract)
        cls.expected = G2.expected_record(cls.contract, cls.raw, cls.projection)
        cls.record, cls.record_raw = G2.load_json(BASE / G2.RECORD_NAME, "record", canonical=True)

    def test_content_opens_only_nonimplementing_static_artifacts(self) -> None:
        result = G2.validate_content()
        self.assertEqual(result["disposition"], G2.DISPOSITION)
        self.assertEqual(result["next_gate"], G2.NEXT_GATE)
        self.assertEqual(self.record_raw, G2.canonical_bytes(self.record))
        self.assertEqual(self.record["implementation_gate"], "CLOSED")
        self.assertEqual(self.record["execution_gate"], "CLOSED")

    def test_p11b_topology_custody_and_projection(self) -> None:
        self.assertEqual(G2._parent(G2.DIRECT_PARENT), G2.G1)
        self.assertEqual(G2._paths(G2.DIRECT_PARENT), G2.P11B_PATHS)
        self.assertEqual(self.projection["target_component_sum_bytes"], 1028653056)
        self.assertEqual(self.projection["wide_scratch_bits"], 2112)

    def test_forbidden_authority_mutations_fail(self) -> None:
        keys = ("implementation_source_allowed", "C_assembly_or_linker_script_source_allowed", "prototype_allowed",
                "compilation_or_linking_allowed", "Julia_or_candidate_execution_allowed", "benchmark_or_host_measurement_allowed",
                "package_installation_or_environment_mutation_allowed", "binary_or_source_archive_download_allowed",
                "network_retrieval_allowed", "scientific_schedule_semantics_or_cap_change_allowed")
        for key in keys:
            changed = copy.deepcopy(self.contract)
            changed["P11_C_authorization"][key] = True
            with self.subTest(key=key), self.assertRaises(G2.GovernanceError):
                G2.validate_contract(changed)

    def test_record_cannot_claim_peak_equivalence_or_open_gates(self) -> None:
        for key, value in (("candidate_source_allowed", True), ("compilation_or_linking_allowed", True),
                           ("exact_static_process_peak_bytes", 1028653056), ("difference_is_proven_headroom", True),
                           ("semantic_equivalence_established", True), ("implementation_gate", "OPEN"),
                           ("execution_gate", "OPEN"), ("resource_no_go_inference", True)):
            changed = copy.deepcopy(self.record)
            changed[key] = value
            with self.subTest(key=key):
                self.assertNotEqual(changed, self.expected)

    def test_p11b_blob_drift_fails(self) -> None:
        with mock.patch.object(G2, "_git_bytes", return_value=b"wrong"):
            with self.assertRaises(G2.GovernanceError):
                G2.validate_p11b(self.contract)

    def test_exact_staged_lifecycle(self) -> None:
        staged = "".join(f"{status}\t{path}\n" for path, status in G2.CHANGED_PATHS.items())
        def good(*args):
            if args == ("rev-parse", "HEAD"):
                return G2.DIRECT_PARENT + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return staged
            if args in (("diff", "--name-only"), ("ls-files", "--others", "--exclude-standard")):
                return ""
            raise AssertionError(args)
        with mock.patch.object(G2, "_git", side_effect=good):
            self.assertEqual(G2.validate_lifecycle(), "STAGED_DIRECT_CHILD")

    def test_subprocesses_are_git_only(self) -> None:
        tree = ast.parse(PATH.read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "subprocess"]
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertEqual(call.args[0].elts[0].value, "git")


if __name__ == "__main__":
    unittest.main()
