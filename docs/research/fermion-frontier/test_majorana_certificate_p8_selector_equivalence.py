#!/usr/bin/env python3
"""Static and mathematical tests for the P8-A selector-equivalence preprobe."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import sys
import textwrap
import unittest
from unittest import mock
from pathlib import Path


BASE = Path(__file__).resolve().parent
MODULE_PATH = BASE / "majorana_certificate_p8_selector_equivalence.py"
SPEC = importlib.util.spec_from_file_location("majorana_p8_selector_equivalence", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
P8 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = P8
SPEC.loader.exec_module(P8)


class MajoranaP8SelectorEquivalenceTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads((BASE / P8.FIXTURE_NAME).read_text(encoding="utf-8"))
        cls.policy = json.loads((BASE / P8.POLICY_NAME).read_text(encoding="utf-8"))

    def test_closed_fixture_policy_and_source_contract(self) -> None:
        self.assertEqual(self.fixture, P8._expected_fixture())
        self.assertEqual(self.policy["source_files"], sorted(
            self.policy["source_files"], key=lambda row: P8.SOURCE_PATHS.index(row["relative_path"]),
        ))
        P8._validate_fixture(self.fixture)
        P8._validate_policy(self.policy)
        P8._validate_source_contract(self.fixture)
        self.assertEqual(
            P8.canonical_sha256(self.fixture),
            P8.FIXTURE_CANONICAL_SHA256,
        )
        self.assertEqual(
            P8.canonical_sha256(P8._policy_semantic(self.policy)),
            P8.POLICY_SEMANTIC_SHA256,
        )
        for section, key in (
            ("selector_contract", "P6_rank_key"),
            ("selector_contract", "tier2_inclusion"),
            ("proof_scope", "P8_A_proves_only_successful_selector_membership_and_selected_cost_total"),
        ):
            mutated = copy.deepcopy(self.fixture)
            mutated[section][key] = False
            with self.subTest(section=section, key=key), self.assertRaises(P8.ProofError):
                P8._validate_fixture(mutated)

    def test_hand_anchored_binary64_boundary_vectors(self) -> None:
        self.assertEqual(P8.point_abs_ticks_from_bits(0), 0)
        self.assertEqual(P8.point_abs_ticks_from_bits(1), 1)
        self.assertEqual(P8.point_abs_ticks_from_bits(P8.FRACTION_MASK), 1)
        self.assertEqual(P8.point_abs_ticks_from_bits(0x37EFFFFFFFFFFFFF), 1)
        self.assertEqual(P8.point_abs_ticks_from_bits(0x37F0000000000000), 1)
        self.assertEqual(P8.point_abs_ticks_from_bits(0x37F0000000000001), 2)
        self.assertEqual(P8.point_abs_ticks_from_bits(P8.P6_K37_ABS_BITS), 1 << 91)
        self.assertLess(
            P8.point_abs_ticks_from_bits(P8.P6_K37_ABS_BITS - 1),
            P8.point_abs_ticks_from_bits(P8.P6_K37_ABS_BITS),
        )
        self.assertEqual(
            P8.point_abs_ticks_from_bits(P8.MAX_FINITE_ABS_BITS),
            (1 << 1152) - (1 << 1099),
        )
        rows = (
            P8.SelectorRow(0, 9),
            P8.SelectorRow(0, 1),
            P8.SelectorRow(1, 4),
            P8.SelectorRow(P8.P6_K37_ABS_BITS, 2),
        )
        zero_budget = P8.full_domain_selector(rows, 0)
        self.assertEqual([item.row.mask for item in zero_budget.ordered_rows], [1, 9])
        self.assertEqual(zero_budget.selected_cost_total, 0)
        self.assertEqual(zero_budget.remaining_budget, 0)
        one_budget = P8.full_domain_selector(rows, 1)
        self.assertEqual([item.row.mask for item in one_budget.ordered_rows], [1, 9, 4])
        self.assertEqual(one_budget.selected_cost_total, 1)
        exact_k37 = P8.full_domain_selector(rows, (1 << 91) + 1)
        self.assertEqual([item.row.mask for item in exact_k37.ordered_rows], [1, 9, 4, 2])
        for available in (0, 1, (1 << 91) + 1):
            expected = P8.full_domain_selector(rows, available)
            self.assertEqual(P8.p6_tiered_selector(rows, available), expected)
            self.assertEqual(P8.bit_order_selector(rows, available), expected)

    def test_exhaustive_declared_differential_domain(self) -> None:
        cases = P8._differential_cases(self.fixture)
        self.assertGreater(len(cases), 100)
        self.assertEqual(
            P8._prove_equivalence(P8.full_domain_selector, P8.p6_tiered_selector, cases),
            len(cases),
        )
        self.assertEqual(
            P8._prove_equivalence(P8.full_domain_selector, P8.bit_order_selector, cases),
            len(cases),
        )
        self.assertEqual(
            P8._prove_internal_rank_trace_equivalence(
                P8.full_domain_selector, P8.p6_tiered_selector, cases,
            ),
            len(cases),
        )
        proof = P8.build_selector_proof(self.fixture)
        self.assertEqual(proof["differential_witness"]["case_count"], len(cases))
        self.assertEqual(proof["proof_status"], P8.REPORT_STATUS)
        self.assertIn("no_resource_consumption_equivalence", proof["nonclaims"])

    def test_wrong_order_and_wrong_boundary_counterexamples_are_detected(self) -> None:
        cases = P8._differential_cases(self.fixture)

        def reverse_bit_selector(rows, available):
            materialized = P8._validate_rows(rows)
            ranked = [P8.RankedRow(row, P8.point_abs_ticks_from_bits(row.abs_bits)) for row in materialized]
            ranked.sort(key=lambda item: (-item.row.abs_bits, item.row.mask))
            return P8._affordable_prefix(ranked, available)

        def wrong_tie_selector(rows, available):
            materialized = P8._validate_rows(rows)
            ranked = [P8.RankedRow(row, P8.point_abs_ticks_from_bits(row.abs_bits)) for row in materialized]
            ranked.sort(key=lambda item: (item.point_cost, item.row.abs_bits, -item.row.mask))
            return P8._affordable_prefix(ranked, available)

        with self.assertRaisesRegex(P8.ProofError, "selector equivalence mismatch"):
            P8._prove_equivalence(P8.full_domain_selector, reverse_bit_selector, cases)
        with self.assertRaisesRegex(P8.ProofError, "internal rank-trace mismatch"):
            P8._prove_internal_rank_trace_equivalence(
                P8.full_domain_selector, wrong_tie_selector, cases,
            )

    def test_invalid_inputs_fail_closed(self) -> None:
        invalid_rows = (
            (P8.SelectorRow(-1, 0),),
            (P8.SelectorRow(P8.MAX_FINITE_ABS_BITS + 1, 0),),
            (P8.SelectorRow(0, -1),),
            (P8.SelectorRow(0, P8.MASK_MAX + 1),),
            (P8.SelectorRow(0, 1), P8.SelectorRow(1, 1)),
        )
        for rows in invalid_rows:
            with self.subTest(rows=rows), self.assertRaises(P8.ProofError):
                P8.full_domain_selector(rows, 0)
        with self.assertRaises(P8.ProofError):
            P8.full_domain_selector((P8.SelectorRow(0, 1),), -1)
        with self.assertRaises(P8.ProofError):
            P8._parse_hex_u64("0" * 15, "short")
        with self.assertRaises(P8.ProofError):
            P8._parse_hex_u64("G" * 16, "nonhex")

    def test_implementations_are_not_aliases_or_cross_calls(self) -> None:
        self.assertIsNot(P8.full_domain_selector, P8.bit_order_selector)
        self.assertIsNot(P8.p6_tiered_selector, P8.bit_order_selector)
        for function, forbidden in (
            (P8.full_domain_selector, "bit_order_selector"),
            (P8.bit_order_selector, "full_domain_selector"),
            (P8.p6_tiered_selector, "full_domain_selector"),
        ):
            source = inspect.getsource(function)
            with self.subTest(function=function.__name__):
                self.assertNotIn(forbidden, source)
        self.assertIn("point_abs_ticks_from_bits", inspect.getsource(P8.full_domain_selector))
        self.assertIn("point_abs_ticks_from_bits", inspect.getsource(P8.bit_order_selector))

    def test_d4_parent_firewall_is_a_closed_provenance_leaf(self) -> None:
        projection = P8._validate_d4_parent(self.fixture)
        self.assertEqual(projection, P8._expected_d4_parent_projection())
        self.assertEqual(P8.canonical_sha256(projection), P8.D4_PROJECTION_SHA256)
        source = textwrap.dedent(inspect.getsource(P8._validate_d4_parent))
        tree = ast.parse(source)
        accessed: set[tuple[str, str]] = set()
        for node in ast.walk(tree):
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
        module_source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import majorana_certificate_p7_d4", module_source)
        self.assertNotIn("validate_report", module_source)
        self.assertNotIn("D4._", module_source)

    def test_result_verification_rebinds_every_current_preprobe_blob(self) -> None:
        self.assertEqual(P8.PREPROBE_BLOB_NAMES, (
            P8.FIXTURE_NAME,
            P8.POLICY_NAME,
            MODULE_PATH.name,
            P8.TEST_NAME,
        ))
        with mock.patch.object(P8, "_read_regular", return_value=b"current"), mock.patch.object(
            P8, "_git_bytes", return_value=b"frozen",
        ):
            with self.assertRaisesRegex(P8.ProofError, "current preprobe blob drift"):
                P8._assert_current_preprobe_blobs("a" * 40)
        with mock.patch.object(P8, "_read_regular", return_value=b"same") as read, mock.patch.object(
            P8, "_git_bytes", return_value=b"same",
        ) as show:
            P8._assert_current_preprobe_blobs("a" * 40)
        self.assertEqual(read.call_count, len(P8.PREPROBE_BLOB_NAMES))
        self.assertEqual(show.call_count, len(P8.PREPROBE_BLOB_NAMES))
        self.assertIn("_assert_current_preprobe_blobs(preprobe_commit)", inspect.getsource(P8.prove))
        self.assertIn(
            "_assert_current_preprobe_blobs(preprobe_commit)",
            inspect.getsource(P8.validate_proof_report),
        )

    def test_preprobe_verification_covers_staged_and_frozen_lifecycles(self) -> None:
        expected = {
            "direct_parent_commit": P8.DIRECT_PARENT,
            "fixture_id": P8.FIXTURE_ID,
            "policy_id": P8.POLICY_ID,
            "status": "VERIFIED_P8_A_SELECTOR_EQUIVALENCE_PREPROBE",
        }
        with mock.patch.object(
            P8, "_validate_current_preprobe_inputs", return_value=(self.policy, self.fixture),
        ), mock.patch.object(P8, "_git", return_value=f"{'a' * 40}\n"), mock.patch.object(
            P8, "_validate_frozen_preprobe_worktree",
        ) as frozen:
            self.assertEqual(P8.verify_preprobe(), expected)
            frozen.assert_called_once_with("a" * 40)
        with mock.patch.object(
            P8, "_validate_current_preprobe_inputs", return_value=(self.policy, self.fixture),
        ), mock.patch.object(P8, "_git", return_value=f"{P8.DIRECT_PARENT}\n"), mock.patch.object(
            P8, "_validate_preprobe_worktree",
        ) as staged:
            self.assertEqual(P8.verify_preprobe(), expected)
            staged.assert_called_once_with()

    def test_preprobe_requires_final_staged_additions(self) -> None:
        staged = "\n".join(
            f"A  {path}" for path in reversed(P8.PREPROBE_CHANGED_PATHS)
        )
        with mock.patch.object(P8, "_git", return_value=staged):
            self.assertEqual(
                P8._parse_preprobe_staged_paths(),
                tuple(sorted(P8.PREPROBE_CHANGED_PATHS)),
            )
        for invalid in (
            f"AM {P8.PREPROBE_CHANGED_PATHS[0]}",
            f"?? {P8.PREPROBE_CHANGED_PATHS[0]}",
        ):
            with self.subTest(invalid=invalid), mock.patch.object(P8, "_git", return_value=invalid):
                with self.assertRaisesRegex(P8.ProofError, "final staged additions"):
                    P8._parse_preprobe_staged_paths()

    def test_source_pins_are_exact_and_report_is_absent(self) -> None:
        expected_paths = list(P8.SOURCE_PATHS)
        self.assertEqual([row["relative_path"] for row in self.policy["source_files"]], expected_paths)
        for row in self.policy["source_files"]:
            path = BASE / row["relative_path"]
            self.assertTrue(path.is_file())
            self.assertFalse(path.is_symlink())
            self.assertEqual(path.stat().st_size, row["size_bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])
        report = BASE / P8.REPORT_NAME
        self.assertFalse(report.exists())
        self.assertFalse(report.exists())


if __name__ == "__main__":
    unittest.main()
