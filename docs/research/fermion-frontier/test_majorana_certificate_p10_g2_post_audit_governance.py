#!/usr/bin/env python3
"""Adversarial tests for P10-G2 governance."""

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
PATH = BASE / "majorana_certificate_p10_g2_post_audit_governance_validator.py"
SPEC = importlib.util.spec_from_file_location("p10g2", PATH)
assert SPEC and SPEC.loader
G2 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = G2
SPEC.loader.exec_module(G2)


class P10G2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.raw = G2.load_json(BASE / G2.CONTRACT_NAME, "contract")
        G2.validate_contract(cls.contract)
        cls.projection = G2.validate_p10b(cls.contract)
        cls.expected = G2.expected_record(cls.contract, cls.raw, cls.projection)
        cls.record, cls.record_raw = G2.load_json(BASE / G2.RECORD_NAME, "record", canonical=True)

    def test_content_closes_old_route_and_opens_design_only(self) -> None:
        result = G2.validate_content()
        self.assertEqual(result["disposition"], G2.DISPOSITION)
        self.assertEqual(result["next_gate"], G2.NEXT_GATE)
        self.assertEqual(self.record_raw, G2.canonical_bytes(self.record))
        self.assertEqual(self.record["execution_gate"], "CLOSED")

    def test_p10b_topology_custody_and_projection(self) -> None:
        self.assertEqual(G2._parent(G2.DIRECT_PARENT), G2.P10B_PARENT)
        self.assertEqual(G2._paths(G2.DIRECT_PARENT), G2.P10B_PATHS)
        self.assertEqual(self.projection["P10_B_evidence_row_count"], 7)
        self.assertEqual(self.projection["P10_B_outcome"], "CLOSED_NO_INDEPENDENT_STATIC_BYTE_CONTRACT_ROUTE")

    def test_contract_authority_mutations_fail_closed(self) -> None:
        for key in ("implementation_allowed", "prototype_allowed", "compilation_allowed", "Julia_or_candidate_execution_allowed", "benchmark_or_host_measurement_allowed", "network_or_external_source_acquisition_allowed", "scientific_schedule_or_semantics_change_allowed"):
            changed = copy.deepcopy(self.contract)
            changed["P11_A_design_authorization"][key] = True
            with self.subTest(key=key), self.assertRaises(G2.GovernanceError):
                G2.validate_contract(changed)

    def test_record_cannot_claim_peak_execution_or_no_go(self) -> None:
        for key, value in (("exact_static_peak_bytes", 1), ("execution_gate", "OPEN"), ("resource_no_go_inference", True), ("P11_A_implementation_allowed", True)):
            changed = copy.deepcopy(self.record)
            changed[key] = value
            with self.subTest(key=key):
                self.assertNotEqual(changed, self.expected)

    def test_source_blob_and_negative_ledger_drift_fail(self) -> None:
        with mock.patch.object(G2, "_git_bytes", return_value=b"wrong"):
            with self.assertRaises(G2.GovernanceError):
                G2.validate_p10b(self.contract)

    def test_lifecycle_requires_exact_staged_direct_child(self) -> None:
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

    def test_validator_subprocesses_are_git_only(self) -> None:
        tree = ast.parse(PATH.read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "subprocess"]
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertEqual(call.args[0].elts[0].value, "git")


if __name__ == "__main__":
    unittest.main()
