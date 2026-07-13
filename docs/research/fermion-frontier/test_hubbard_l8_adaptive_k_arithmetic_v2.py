#!/usr/bin/env python3
"""Parity, resource, and selection tests for adaptive-K arithmetic v2."""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import pathlib
import random
import unittest
from fractions import Fraction
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


KERNEL = load_module(
    "hubbard_l8_adaptive_k_arithmetic_v2",
    "hubbard_l8_adaptive_k_arithmetic_v2.py",
)
ROOT = load_module(
    "hubbard_l8_root_for_adaptive_k_v2_tests",
    "hubbard_l8_observable_interval_step_checker.py",
)


class AdaptiveKArithmeticV2Tests(unittest.TestCase):
    def test_01_kernel_has_no_certificate_authority(self):
        self.assertEqual(KERNEL.CERTIFICATE_AUTHORITY, "NONE")
        self.assertFalse(hasattr(KERNEL, "verify_certificate"))
        self.assertFalse(hasattr(KERNEL, "main"))

    def test_02_root_source_pin_matches_same_bytes(self):
        payload = (HERE / KERNEL.ROOT_SOURCE_PIN["relative_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), KERNEL.ROOT_SOURCE_PIN["sha256"])
        oracle = KERNEL.compile_root_oracle(payload)
        self.assertEqual(oracle.TICK_DENOMINATOR, 1 << 64)

    def test_03_root_source_drift_is_rejected(self):
        payload = KERNEL.read_root_source_bytes()
        with self.assertRaises(KERNEL.SchemaError):
            KERNEL.compile_root_oracle(payload + b"\n")

    def test_04_kernel_caps_exceed_v1_without_mutating_root(self):
        before = KERNEL.root_global_snapshot(ROOT)
        self.assertGreater(KERNEL.RESOURCE_LIMITS["max_retained_K"], ROOT.RETAINED_TERM_CAP)
        self.assertGreater(
            KERNEL.RESOURCE_LIMITS["max_single_expansion_terms"],
            ROOT.RESOURCE_LIMITS["max_single_expansion_terms"],
        )
        self.assertGreater(
            KERNEL.RESOURCE_LIMITS["max_term_gate_visits"],
            ROOT.RESOURCE_LIMITS["max_term_gate_visits"],
        )
        self.assertEqual(before, KERNEL.root_global_snapshot(ROOT))

    def test_05_multiply_ticks_matches_root_exactly(self):
        rng = random.Random(20260712)
        fixtures = [((-5, 7), (11, 13)), ((-2**64, 2**64), (1, 1))]
        for _ in range(100):
            a = sorted((rng.randint(-10**7, 10**7), rng.randint(-10**7, 10**7)))
            b = sorted((rng.randint(-10**7, 10**7), rng.randint(-10**7, 10**7)))
            fixtures.append((tuple(a), tuple(b)))
        for left, right in fixtures:
            v2 = KERNEL.PropagationCounterV2()
            v1 = ROOT.PropagationCounter()
            self.assertEqual(
                KERNEL.multiply_ticks(left, right, v2),
                ROOT._multiply_ticks(left, right, v1),
            )
            self.assertEqual(v2.maximum_product_bits, v1.maximum_product_bits)
            self.assertEqual(
                v2.multiplication_rounding_l1_scaled_ticks_squared,
                v1.multiplication_rounding_l1_scaled_ticks_squared,
            )

    def test_06_negative_floor_and_ceil_are_outward(self):
        counter = KERNEL.PropagationCounterV2()
        value = KERNEL.multiply_ticks((-3, -2), (1, 1), counter)
        self.assertLessEqual(value[0] * KERNEL.TICK_DENOMINATOR, -3)
        self.assertGreaterEqual(value[1] * KERNEL.TICK_DENOMINATOR, -2)

    def test_07_anticommuting_branch_matches_root_exhaustively(self):
        for gx, gz, ox, oz in itertools.product(range(8), repeat=4):
            if ((gx & oz).bit_count() + (gz & ox).bit_count()) & 1:
                self.assertEqual(
                    KERNEL.anticommuting_branch((gx, gz), (ox, oz)),
                    ROOT._anticommuting_branch((gx, gz), (ox, oz)),
                )

    def test_08_gate_propagation_matches_root_on_old_domain(self):
        groups = ROOT._independent_groups(ROOT._independent_bonds())
        _forward, _gates, stages, _claim = ROOT._sequence_records(groups)
        generator, theta = stages[0]["gates"][0]
        sine, cosine, _record = ROOT._taylor_trig_record(theta)
        expansion = {
            (0, 0): (2**63, 2**63),
            (0, 1): (-17, 19),
            (1, 0): (31, 37),
        }
        v2 = KERNEL.PropagationCounterV2()
        v1 = ROOT.PropagationCounter()
        observed = KERNEL.propagate_gate(expansion, generator, sine, cosine, v2)
        expected = ROOT._propagate_gate(expansion, generator, sine, cosine, v1)
        self.assertEqual(observed, expected)
        self.assertEqual(v2.term_gate_visits, v1.term_gate_visits)
        self.assertEqual(v2.maximum_product_bits, v1.maximum_product_bits)
        self.assertEqual(
            v2.multiplication_rounding_l1_scaled_ticks_squared,
            v1.multiplication_rounding_l1_scaled_ticks_squared,
        )

    def test_09_formal_arithmetic_does_not_call_root_helpers(self):
        before = KERNEL.root_global_snapshot(ROOT)
        expansion = {(0, 1): (11, 13), (1, 0): (17, 19)}
        with mock.patch.object(ROOT, "_propagate_gate", side_effect=AssertionError), mock.patch.object(
            ROOT, "_tick_digest", side_effect=AssertionError
        ), mock.patch.object(ROOT, "_truncate", side_effect=AssertionError), mock.patch.object(
            ROOT, "PropagationCounter", side_effect=AssertionError
        ):
            counter = KERNEL.PropagationCounterV2()
            KERNEL.propagate_gate(
                expansion, (0, 1), (1, 2), (2**64 - 1, 2**64), counter
            )
            KERNEL.tick_digest(expansion)
            KERNEL.select_and_truncate(expansion, [1, 2], 0, 100)
        self.assertEqual(before, KERNEL.root_global_snapshot(ROOT))

    def test_10_digest_and_expectation_match_root(self):
        expansion = {(0, 0): (5, 7), (0, 3): (-11, -9), (1, 0): (13, 17)}
        self.assertEqual(KERNEL.tick_digest(expansion), ROOT._tick_digest(expansion))
        for basis in (0, 1, 2, 3):
            self.assertEqual(
                KERNEL.expectation_ticks(expansion, basis),
                ROOT._expectation_ticks(expansion, basis),
            )

    def test_11_counter_enforces_visits_live_and_coefficient_caps(self):
        counter = KERNEL.PropagationCounterV2()
        with mock.patch.dict(
            KERNEL.RESOURCE_LIMITS,
            {
                "max_term_gate_visits": 3,
                "max_single_expansion_terms": 2,
                "max_expansion_coefficient_tick_bits": 4,
            },
        ):
            counter.visit(3)
            with self.assertRaises(KERNEL.SchemaError):
                counter.visit(1)
            with self.assertRaises(KERNEL.SchemaError):
                counter.observe_count(3)
            with self.assertRaises(KERNEL.SchemaError):
                counter.observe_interval((16, 16))

    def test_12_gate_checks_input_caps_and_transient_growth(self):
        with mock.patch.dict(KERNEL.RESOURCE_LIMITS, {"max_single_expansion_terms": 1}):
            with self.assertRaises(KERNEL.SchemaError):
                KERNEL.propagate_gate(
                    {(0, 0): (1, 1), (0, 1): (1, 1)},
                    (1, 0),
                    (1, 1),
                    (2**64, 2**64),
                    KERNEL.PropagationCounterV2(),
                )
            with self.assertRaises(KERNEL.SchemaError):
                KERNEL.add_tick_term(
                    {(0, 0): (1, 1)},
                    (0, 1),
                    (1, 1),
                    KERNEL.PropagationCounterV2(),
                )

    def test_13_digest_checks_cap_before_sorting(self):
        expansion = {(0, 0): (1, 1), (0, 1): (1, 1)}
        with mock.patch.dict(KERNEL.RESOURCE_LIMITS, {"max_digest_terms": 1}):
            with mock.patch("builtins.sorted", side_effect=AssertionError("sorted too early")):
                with self.assertRaises(KERNEL.SchemaError):
                    KERNEL.tick_digest(expansion)

    def test_14_rank_checks_coeff_cap_zero_and_numeric_ties(self):
        expansion = {
            (0, 9): (5, 5),
            (0, 2): (-5, -5),
            (1, 0): (3, 3),
        }
        ranked, suffix = KERNEL.rank_with_suffix(expansion)
        self.assertEqual(ranked[:2], [(0, 2), (0, 9)])
        self.assertEqual(suffix[0], 13)
        with self.assertRaises(KERNEL.SchemaError):
            KERNEL.rank_with_suffix({(0, 0): (0, 0)})
        with mock.patch.dict(
            KERNEL.RESOURCE_LIMITS, {"max_expansion_coefficient_tick_bits": 3}
        ):
            with self.assertRaises(KERNEL.SchemaError):
                KERNEL.rank_with_suffix({(0, 0): (8, 8)})

    def test_15_candidate_schema_is_strict_and_bounded(self):
        for bad in ([], [2, 2], [3, 2], [True], [0], "1,2"):
            with self.assertRaises(KERNEL.SchemaError):
                KERNEL.validate_candidates(bad)
        with self.assertRaises(KERNEL.SchemaError):
            KERNEL.validate_candidates([KERNEL.RESOURCE_LIMITS["max_retained_K"] + 1])
        self.assertEqual(KERNEL.validate_candidates([1, 2, 3]), (1, 2, 3))

    def test_16_first_feasible_selection_and_all_records(self):
        records, selected = KERNEL.evaluate_candidates(
            4, [10, 6, 3, 1, 0], [1, 2, 4], 100, 104
        )
        self.assertEqual(selected, 1)
        self.assertEqual(len(records), 3)
        self.assertFalse(records[0]["feasible_under_current_prefix_cap"])
        self.assertTrue(records[1]["feasible_under_current_prefix_cap"])

    def test_17_no_feasible_candidate_commits_nothing(self):
        expansion = {(0, i): (i + 1, i + 1) for i in range(4)}
        result = KERNEL.select_and_truncate(expansion, [1, 2], 100, 100)
        self.assertFalse(result["committed"])
        self.assertNotIn("expansion", result)
        self.assertIsNone(result["selected_candidate_index"])

    def test_18_K_above_live_count_has_zero_drop(self):
        records, selected = KERNEL.evaluate_candidates(2, [7, 3, 0], [1, 4], 5, 5)
        self.assertEqual(selected, 1)
        self.assertEqual(records[1]["effective_retained_count"], 2)
        self.assertEqual(records[1]["drop_ticks"], "0")

    def test_19_commit_requires_complete_ranked_permutation(self):
        expansion = {(0, 0): (5, 5), (0, 1): (3, 3)}
        ranked, suffix = KERNEL.rank_with_suffix(expansion)
        records, selected = KERNEL.evaluate_candidates(2, suffix, [1, 2], 0, 3)
        self.assertEqual(selected, 0)
        with self.assertRaises(KERNEL.SchemaError):
            KERNEL.commit_candidate(expansion, ranked[:1], suffix, [1, 2], 0, 3, selected)

    def test_19b_split_commit_revalidates_order_suffix_and_first_feasible(self):
        expansion = {(0, 1): (5, 5), (0, 2): (5, 5), (0, 3): (1, 1)}
        ranked, suffix = KERNEL.rank_with_suffix(expansion)
        self.assertEqual(ranked, [(0, 1), (0, 2), (0, 3)])
        with self.assertRaises(KERNEL.SchemaError):
            KERNEL.commit_candidate(
                expansion,
                [ranked[1], ranked[0], ranked[2]],
                suffix,
                [1, 2],
                0,
                6,
                0,
            )
        with self.assertRaises(KERNEL.SchemaError):
            KERNEL.commit_candidate(
                expansion, ranked, [11, 7, 1, 0], [1, 2], 0, 6, 1
            )
        with self.assertRaises(KERNEL.VerificationError):
            KERNEL.commit_candidate(expansion, ranked, suffix, [1, 2], 0, 6, 1)

    def test_19c_candidate_evaluation_enforces_suffix_resource_schema(self):
        too_wide = 1 << KERNEL.RESOURCE_LIMITS["max_suffix_accumulator_bits"]
        with self.assertRaises(KERNEL.SchemaError):
            KERNEL.evaluate_candidates(1, [too_wide, 0], [1], 0, 1)
        with self.assertRaises(KERNEL.SchemaError):
            KERNEL.evaluate_candidates(1, [1, 1], [1], 0, 1)

    def test_20_commit_binds_drop_and_digests(self):
        expansion = {(0, 0): (7, 7), (0, 1): (5, 5), (0, 2): (3, 3)}
        result = KERNEL.select_and_truncate(expansion, [1, 2, 3], 0, 5)
        self.assertTrue(result["committed"])
        self.assertEqual(result["truncation"]["configured_K"], 2)
        self.assertEqual(result["truncation"]["dropped_l1_ticks"], 3)
        self.assertEqual(
            result["truncation"]["retained_expansion_sha256"],
            KERNEL.tick_digest(result["expansion"]),
        )

    def test_21_K65536_selection_matches_root_truncate(self):
        expansion = {(0, index): (index + 1, index + 1) for index in range(65_537)}
        expected, expected_drop = ROOT._truncate(expansion)
        observed = KERNEL.select_and_truncate(expansion, [65_536], 0, 10**30)
        self.assertTrue(observed["committed"])
        self.assertEqual(observed["expansion"], expected)
        self.assertEqual(
            observed["truncation"]["dropped_l1_ticks"],
            expected_drop["dropped_l1_ticks"],
        )
        self.assertEqual(
            observed["truncation"]["dropped_terms_sha256"],
            expected_drop["dropped_terms_sha256"],
        )

    def test_22_extended_domain_caps_cover_frozen_diagnostics(self):
        self.assertGreaterEqual(KERNEL.RESOURCE_LIMITS["max_retained_K"], 327_680)
        self.assertGreaterEqual(
            KERNEL.RESOURCE_LIMITS["max_single_expansion_terms"], 446_188
        )
        self.assertGreaterEqual(
            KERNEL.RESOURCE_LIMITS["max_term_gate_visits"], 337_691_387
        )
        counter = KERNEL.PropagationCounterV2()
        counter.observe_count(446_188)
        counter.visit(337_691_387)
        self.assertEqual(counter.peak_live_terms, 446_188)

    def test_23_bool_masks_intervals_and_candidates_are_rejected(self):
        with self.assertRaises(KERNEL.SchemaError):
            KERNEL.anticommuting_branch((True, 0), (0, 1))
        with self.assertRaises(KERNEL.SchemaError):
            KERNEL.multiply_ticks((True, 1), (1, 1), KERNEL.PropagationCounterV2())
        with self.assertRaises(KERNEL.SchemaError):
            KERNEL.evaluate_candidates(1, [1, 0], [True], 0, 1)


if __name__ == "__main__":
    unittest.main()
