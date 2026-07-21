#!/usr/bin/env python3
"""Adversarial tests for the P11-A explicit-memory feasibility design."""

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
PATH = BASE / "majorana_certificate_p11a_explicit_memory_kernel_design_validator.py"
SPEC = importlib.util.spec_from_file_location("p11a", PATH)
assert SPEC and SPEC.loader
P11A = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = P11A
SPEC.loader.exec_module(P11A)


class P11AExplicitMemoryDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.raw = P11A.load_json(BASE / P11A.CONTRACT_NAME, "contract")
        P11A.validate_contract(cls.contract)
        cls.sources = P11A.validate_sources(cls.contract)
        cls.regions, cls.subtotal = P11A.derive_regions(cls.contract)
        cls.expected = P11A.expected_report(cls.contract, cls.raw, cls.sources, cls.regions, cls.subtotal)
        cls.report, cls.report_raw = P11A.load_json(BASE / P11A.REPORT_NAME, "report", canonical=True)

    def test_route_is_identified_but_all_active_gates_stay_closed(self) -> None:
        result = P11A.validate_content()
        self.assertEqual(result["outcome"], P11A.OUTCOME)
        self.assertEqual(result["implementation_gate"], "CLOSED")
        self.assertEqual(result["execution_gate"], "CLOSED")
        self.assertEqual(self.report_raw, P11A.canonical_bytes(self.report))
        self.assertIsNone(self.report["exact_static_process_peak_bytes"])
        self.assertFalse(self.report["semantic_equivalence_established"])

    def test_region_ledger_rederives_exact_design_subtotal(self) -> None:
        self.assertEqual(self.subtotal, 872415232)
        self.assertEqual(tuple(row["region_id"] for row in self.regions), P11A.REGION_IDS)
        self.assertEqual(self.report["unassigned_difference_to_fixed_cap_bytes"], 2147483648 - self.subtotal)
        self.assertIn("NOT_AN_IMPLEMENTED_LAYOUT", self.report["subtotal_interpretation"])

    def test_all_seven_questions_have_routes_but_still_require_contracts(self) -> None:
        rows = self.report["design_question_disposition"]
        self.assertEqual(tuple(row["question_id"] for row in rows), P11A.QUESTION_IDS)
        self.assertTrue(all(row["status"] == "ROUTE_IDENTIFIED_CONTRACT_REQUIRED" for row in rows))

    def test_region_width_capacity_or_subtotal_mutations_fail(self) -> None:
        for field, value in (("bytes_per_slot", 63), ("capacity_multiplier_M", 3), ("derived_bytes", 1)):
            changed = copy.deepcopy(self.contract)
            changed["provisional_explicit_region_ledger"][0][field] = value
            with self.subTest(field=field), self.assertRaises(P11A.DesignError):
                P11A.derive_regions(changed)
        changed = copy.deepcopy(self.contract)
        changed["provisional_ledger_rules"]["subtotal_is_a_design_budget_not_an_implemented_layout_or_process_peak_bound"] = False
        with self.assertRaises(P11A.DesignError):
            P11A.derive_regions(changed)

    def test_authority_and_report_mutations_fail_closed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["authority"]["implementation_authority"] = True
        with self.assertRaises(P11A.DesignError):
            P11A.validate_contract(changed)
        for key, value in (("implementation_gate", "OPEN"), ("execution_gate", "OPEN"), ("exact_static_process_peak_bytes", self.subtotal), ("semantic_equivalence_established", True), ("resource_no_go_inference", True)):
            report = copy.deepcopy(self.report)
            report[key] = value
            with self.subTest(key=key):
                self.assertNotEqual(report, self.expected)

    def test_source_hash_and_semantic_anchor_drift_fail(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["source_inputs"][0]["sha256"] = "0" * 64
        with self.assertRaises(P11A.DesignError):
            P11A.validate_sources(changed)
        with mock.patch.object(Path, "read_bytes", return_value=b"wrong"):
            with self.assertRaises(P11A.DesignError):
                P11A.validate_sources(self.contract)

    def test_lifecycle_requires_exact_staged_direct_child(self) -> None:
        staged = "".join(f"{status}\t{path}\n" for path, status in P11A.CHANGED_PATHS.items())
        def good(*args):
            if args == ("rev-parse", "HEAD"):
                return P11A.DIRECT_PARENT + "\n"
            if args == ("diff", "--cached", "--name-status", "--no-renames"):
                return staged
            if args in (("diff", "--name-only"), ("ls-files", "--others", "--exclude-standard")):
                return ""
            raise AssertionError(args)
        with mock.patch.object(P11A, "_git", side_effect=good):
            self.assertEqual(P11A.validate_lifecycle(), "STAGED_DIRECT_CHILD")

    def test_validator_uses_only_read_only_git_subprocesses(self) -> None:
        tree = ast.parse(PATH.read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "subprocess"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[0].elts[0].value, "git")
        source = PATH.read_text(encoding="utf-8")
        self.assertNotIn("systemd-run", source)
        self.assertNotIn("eval(", source)


if __name__ == "__main__":
    unittest.main()
