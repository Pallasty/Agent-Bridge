#!/usr/bin/env python3
"""Tests for the object-only, independent P8-B selector audit."""

from __future__ import annotations

import ast
import copy
import importlib.util
import inspect
import json
import sys
import textwrap
import unittest
from pathlib import Path
from unittest import mock


BASE = Path(__file__).resolve().parent
MODULE_PATH = BASE / "majorana_certificate_p8_selector_equivalence_independent_audit.py"
SPEC = importlib.util.spec_from_file_location("majorana_p8_b_independent_audit", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
P8B = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = P8B
SPEC.loader.exec_module(P8B)


class MajoranaP8BIndependentAuditTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.audit_fixture = json.loads((BASE / P8B.AUDIT_FIXTURE_NAME).read_text(encoding="utf-8"))

    def test_audit_fixture_and_independent_schedule_are_closed(self) -> None:
        self.assertEqual(self.audit_fixture, P8B._expected_audit_fixture())
        P8B._validate_audit_fixture(self.audit_fixture)
        proof = P8B.build_independent_selector_proof(self.audit_fixture)
        self.assertEqual(proof["case_count"], 4026)
        self.assertEqual(proof["case_ids_sha256"], P8B.AUDIT_CASE_IDS_SHA256)
        self.assertNotEqual(
            proof["case_ids_sha256"],
            self.audit_fixture["target_object_manifest"]["P8_A_report_case_ids_sha256"],
        )
        self.assertEqual(
            proof["selector_semantics"], "membership_and_selected_cost_total_only",
        )
        self.assertTrue(
            proof["internal_rank_trace_is_not_P6_selected_costs_Dict_iteration_semantics"],
        )
        mutated = copy.deepcopy(self.audit_fixture)
        mutated["independent_differential_schedule"]["mask_stride"] = 17
        with self.assertRaises(P8B.AuditError):
            P8B._validate_audit_fixture(mutated)
        raw = P8B.canonical_bytes(self.audit_fixture)
        with mock.patch.object(P8B, "_read_current_regular", return_value=raw + b"\n"):
            with self.assertRaisesRegex(P8B.AuditError, "not canonical JSON"):
                P8B._load_current_audit_fixture()

    def test_hand_anchored_binary64_boundaries_and_selectors(self) -> None:
        self.assertEqual(P8B.independent_point_abs_ticks(0), 0)
        self.assertEqual(P8B.independent_point_abs_ticks(1), 1)
        self.assertEqual(P8B.independent_point_abs_ticks(P8B.FRACTION_MASK), 1)
        self.assertEqual(P8B.independent_point_abs_ticks(0x37EFFFFFFFFFFFFF), 1)
        self.assertEqual(P8B.independent_point_abs_ticks(0x37F0000000000000), 1)
        self.assertEqual(P8B.independent_point_abs_ticks(0x37F0000000000001), 2)
        self.assertEqual(P8B.independent_point_abs_ticks(P8B.P6_K37_ABS_BITS), 1 << 91)
        self.assertEqual(
            P8B.independent_point_abs_ticks(P8B.MAX_FINITE_ABS_BITS),
            (1 << 1152) - (1 << 1099),
        )
        rows = (
            P8B.AuditRow(0, 9),
            P8B.AuditRow(0, 1),
            P8B.AuditRow(1, 4),
            P8B.AuditRow(P8B.P6_K37_ABS_BITS, 2),
        )
        for budget in (0, 1, (1 << 91) + 1):
            expected = P8B.full_domain_selection(rows, budget)
            self.assertEqual(P8B.tiered_selection(rows, budget), expected)
            self.assertEqual(P8B.bit_order_selection(rows, budget), expected)

    def test_independent_schedule_detects_wrong_selectors(self) -> None:
        cases = P8B._independent_cases(self.audit_fixture)

        def reverse_bit_order(rows, budget):
            ranked = [
                P8B.AuditRankedRow(row, P8B.independent_point_abs_ticks(row.abs_bits))
                for row in P8B._validate_rows(rows)
            ]
            ranked.sort(key=lambda item: (-item.row.abs_bits, item.row.mask))
            return P8B._affordable_prefix(ranked, budget)

        def wrong_tie_order(rows, budget):
            ranked = [
                P8B.AuditRankedRow(row, P8B.independent_point_abs_ticks(row.abs_bits))
                for row in P8B._validate_rows(rows)
            ]
            ranked.sort(key=lambda item: (item.point_cost, item.row.abs_bits, -item.row.mask))
            return P8B._affordable_prefix(ranked, budget)

        def reordered_full_selection(rows, budget):
            selected = P8B.full_domain_selection(rows, budget)
            return P8B.AuditSelection(tuple(reversed(selected.ordered_rows)), selected.remaining_budget)

        with self.assertRaisesRegex(P8B.AuditError, "semantic mismatch"):
            P8B._prove_equivalence(
                P8B.full_domain_selection, reverse_bit_order, cases, require_rank_trace=False,
            )
        with self.assertRaisesRegex(P8B.AuditError, "rank trace mismatch"):
            P8B._prove_equivalence(
                P8B.full_domain_selection, wrong_tie_order, cases, require_rank_trace=True,
            )
        self.assertEqual(
            P8B._prove_equivalence(
                P8B.full_domain_selection, reordered_full_selection, cases, require_rank_trace=False,
            ),
            len(cases),
        )
        with self.assertRaisesRegex(P8B.AuditError, "rank trace mismatch"):
            P8B._prove_equivalence(
                P8B.full_domain_selection, reordered_full_selection, cases, require_rank_trace=True,
            )

    def test_invalid_selector_inputs_fail_closed(self) -> None:
        invalid = (
            (P8B.AuditRow(-1, 0),),
            (P8B.AuditRow(P8B.MAX_FINITE_ABS_BITS + 1, 0),),
            (P8B.AuditRow(0, -1),),
            (P8B.AuditRow(0, P8B.MASK_MAX + 1),),
            (P8B.AuditRow(0, 1), P8B.AuditRow(1, 1)),
        )
        for rows in invalid:
            with self.subTest(rows=rows), self.assertRaises(P8B.AuditError):
                P8B.full_domain_selection(rows, 0)
        with self.assertRaises(P8B.AuditError):
            P8B.full_domain_selection((P8B.AuditRow(0, 1),), -1)
        with self.assertRaises(P8B.AuditError):
            P8B._parse_u64_hex("0" * 15, "short")

    def test_target_is_read_from_frozen_git_objects_and_validated(self) -> None:
        fixture, policy, report = P8B._load_target_p8_objects()
        independent = P8B.build_independent_selector_proof(self.audit_fixture)
        P8B._validate_target_p8_report(report, policy, independent)
        self.assertEqual(fixture["fixture_id"], "MAJORANA-P8-A-FINITE-BINARY64-SELECTOR-EQUIVALENCE-V2")
        self.assertEqual(report["preprobe_commit"], P8B.P8_PREPROBE_COMMIT)
        self.assertEqual(report["scientific_authority"], "NONE")
        mutated = copy.deepcopy(report)
        mutated["scientific_authority"] = "SCIENCE"
        with self.assertRaises(P8B.AuditError):
            P8B._validate_target_p8_report(mutated, policy, independent)

    def test_object_only_independence_and_d4_firewall(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("majorana_certificate_p8_selector_equivalence" in name for name in imports))
        self.assertNotIn("importlib", source)
        self.assertNotIn("runpy", source)
        self.assertNotIn("validate_proof_report", source)
        target_loader = inspect.getsource(P8B._load_target_p8_objects)
        self.assertIn("_checked_blob", target_loader)
        self.assertNotIn("_read_current_regular", target_loader)
        self.assertNotIn("majorana_certificate_p7_d4", target_loader)
        self.assertIn("_git_blob", inspect.getsource(P8B._checked_blob))

        d4_source = textwrap.dedent(inspect.getsource(P8B._validate_d4_allowed_projection_from_git))
        accessed: set[tuple[str, str]] = set()
        for node in ast.walk(ast.parse(d4_source)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"report", "custody"}
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                accessed.add((node.func.value.id, node.args[0].value))
        self.assertEqual(accessed, {
            ("report", "report_type"),
            ("report", "scientific_authority"),
            ("report", "certificate_eligible"),
            ("report", "result_contract_eligible"),
            ("report", "instrumented_kernel_custody"),
            ("custody", "frozen_P6_runner_sha256"),
            ("custody", "frozen_P6_function_slice_sha256"),
        })

    def test_preprobe_requires_final_staged_additions(self) -> None:
        staged = "\n".join(f"A  {path}" for path in reversed(P8B.AUDIT_PREPROBE_CHANGED_PATHS))
        with mock.patch.object(P8B, "_git_text", return_value=staged):
            self.assertEqual(
                P8B._preprobe_staged_paths(),
                tuple(sorted(P8B.AUDIT_PREPROBE_CHANGED_PATHS)),
            )
        for invalid in (
            f"AM {P8B.AUDIT_PREPROBE_CHANGED_PATHS[0]}",
            f"?? {P8B.AUDIT_PREPROBE_CHANGED_PATHS[0]}",
        ):
            with self.subTest(invalid=invalid), mock.patch.object(P8B, "_git_text", return_value=invalid):
                with self.assertRaisesRegex(P8B.AuditError, "final staged additions"):
                    P8B._preprobe_staged_paths()

    def test_preprobe_index_entries_must_be_regular_stage_zero_blobs(self) -> None:
        path = P8B.AUDIT_RELATIVE_PATH
        object_id = "a" * 40
        valid = f"100644 {object_id} 0\t{path}\n".encode("ascii")
        with mock.patch.object(P8B, "_git_bytes", side_effect=(valid, b"payload")):
            self.assertEqual(P8B._index_regular_blob(path), b"payload")
        invalid = f"120000 {object_id} 0\t{path}\n".encode("ascii")
        with mock.patch.object(P8B, "_git_bytes", return_value=invalid):
            with self.assertRaisesRegex(P8B.AuditError, "regular stage-0 blob"):
                P8B._index_regular_blob(path)

    def test_preprobe_index_bytes_must_match_current_regular_files(self) -> None:
        with mock.patch.object(P8B, "_read_current_regular", return_value=b"current"), mock.patch.object(
            P8B, "_index_regular_blob", return_value=b"index",
        ):
            with self.assertRaisesRegex(P8B.AuditError, "staged index blob differs"):
                P8B._validate_preprobe_index_blobs()

    def test_current_audit_blob_rebinding_is_closed(self) -> None:
        with mock.patch.object(P8B, "_read_current_regular", return_value=b"current"), mock.patch.object(
            P8B, "_git_blob", return_value=b"frozen",
        ):
            with self.assertRaisesRegex(P8B.AuditError, "current P8-B audit blob drift"):
                P8B._assert_current_audit_blobs("a" * 40)
        with mock.patch.object(P8B, "_read_current_regular", return_value=b"same") as read, mock.patch.object(
            P8B, "_git_blob", return_value=b"same",
        ) as blob:
            P8B._assert_current_audit_blobs("a" * 40)
        self.assertEqual(read.call_count, len(P8B.AUDIT_PREPROBE_CHANGED_PATHS))
        self.assertEqual(blob.call_count, len(P8B.AUDIT_PREPROBE_CHANGED_PATHS))

    def test_target_report_schedule_receipt_is_not_replayed_as_audit_schedule(self) -> None:
        fixture, policy, report = P8B._load_target_p8_objects()
        independent = P8B.build_independent_selector_proof(self.audit_fixture)
        P8B._validate_target_p8_report(report, policy, independent)
        target_receipt = report["proof"]["differential_witness"]
        self.assertEqual(target_receipt["case_count"], independent["case_count"])
        self.assertNotEqual(target_receipt["case_ids_sha256"], independent["case_ids_sha256"])
        self.assertEqual(fixture["synthetic_differential_domain"]["maximum_snapshot_rows"], 3)


if __name__ == "__main__":
    unittest.main()
