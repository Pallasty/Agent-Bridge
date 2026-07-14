#!/usr/bin/env python3
"""Pre-result tests for the result-unpinned Majorana P0 certificate inputs."""

from __future__ import annotations

import copy
from fractions import Fraction
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest


BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "majorana_certificate_p0_checker",
    BASE / "majorana_certificate_p0_checker.py",
)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class MajoranaP0PrecommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = CHECKER.validate_fixture(
            CHECKER.load_json(BASE / CHECKER.FIXTURE_NAME)
        )
        cls.runtime_lock = CHECKER.validate_runtime_lock(
            CHECKER.load_json(BASE / CHECKER.RUNTIME_LOCK_NAME)
        )
        cls.expected = CHECKER.expected_witness(cls.fixture, cls.runtime_lock)

    def test_01_strict_json_rejects_duplicate_keys(self) -> None:
        with self.assertRaisesRegex(CHECKER.SchemaError, "duplicate JSON key"):
            CHECKER.strict_json_loads(b'{"a":1,"a":2}')

    def test_02_strict_json_rejects_float_and_nonfinite_tokens(self) -> None:
        for payload in (b'{"x":1.0}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.subTest(payload=payload), self.assertRaises(CHECKER.SchemaError):
                CHECKER.strict_json_loads(payload)

    def test_03_strict_json_rejects_negative_zero_and_huge_integers(self) -> None:
        with self.assertRaisesRegex(CHECKER.SchemaError, "negative-zero"):
            CHECKER.strict_json_loads(b'{"x":-0}')
        huge = b'{"x":1' + b"0" * 2000 + b'}'
        with self.assertRaisesRegex(CHECKER.SchemaError, "4096-bit"):
            CHECKER.strict_json_loads(huge)

    def test_04_rational_text_is_reduced_and_canonical(self) -> None:
        self.assertEqual(CHECKER.parse_q("-7/12"), Fraction(-7, 12))
        for text in ("+1", "01", "1/01", "2/4", "0/7", "-0"):
            with self.subTest(text=text), self.assertRaises(CHECKER.SchemaError):
                CHECKER.parse_q(text)

    def test_05_canonical_json_is_key_sorted_compact_utf8(self) -> None:
        self.assertEqual(
            CHECKER.canonical_bytes({"z": [True, None], "a": "μ"}),
            '{"a":"μ","z":[true,null]}'.encode(),
        )

    def test_06_majorana_product_identity_and_phase_examples(self) -> None:
        self.assertEqual(CHECKER.independent_multiply(0, 37, 3), ("1", 37))
        for generator in (1, 2, 4, 8, 16, 32):
            self.assertEqual(CHECKER.independent_multiply(generator, generator, 3), ("1", 0))
        left = CHECKER.independent_multiply(1, 2, 3)
        right = CHECKER.independent_multiply(2, 1, 3)
        self.assertEqual(left[1], right[1])
        self.assertEqual({left[0], right[0]}, {"i", "-i"})

    def test_07_majorana_commutation_parity_is_symmetric(self) -> None:
        for left in range(64):
            for right in range(64):
                self.assertEqual(
                    CHECKER.omega(left, right), CHECKER.omega(right, left)
                )

    def test_08_primitive_case_counts_follow_the_frozen_domains(self) -> None:
        algebra = CHECKER.primitive_algebra_oracle(self.fixture)
        rotations = CHECKER.primitive_rotations_oracle(self.fixture)
        self.assertEqual(algebra["pair_count"], 64 * 64)
        even_nonidentity = sum(
            mask != 0 and mask.bit_count() % 2 == 0 for mask in range(64)
        )
        self.assertEqual(rotations["case_count"], even_nonidentity * 64 * 9)

    def test_09_primitive_oracles_are_deterministic(self) -> None:
        self.assertEqual(
            CHECKER.primitive_algebra_oracle(self.fixture),
            CHECKER.primitive_algebra_oracle(self.fixture),
        )
        self.assertEqual(
            CHECKER.primitive_rotations_oracle(self.fixture),
            CHECKER.primitive_rotations_oracle(self.fixture),
        )

    def test_10_taylor_intervals_enclose_host_sine_and_cosine_diagnostics(self) -> None:
        policy = self.fixture["interval_policy"]
        denominator = int(policy["outward_quantization_denominator"])
        for text in self.fixture["primitive_conformance"]["angles_in_order"]:
            theta = CHECKER.parse_q(text)
            sine, cosine, _ = CHECKER.taylor_sin_cos(
                theta, policy["taylor_order"], denominator
            )
            self.assertLessEqual(float(sine[0]), math.sin(float(theta)))
            self.assertGreaterEqual(float(sine[1]), math.sin(float(theta)))
            self.assertLessEqual(float(cosine[0]), math.cos(float(theta)))
            self.assertGreaterEqual(float(cosine[1]), math.cos(float(theta)))

    def test_11_outward_quantization_handles_negative_endpoints(self) -> None:
        rounded, widening = CHECKER.quantize_outward(
            (Fraction(-3, 10), Fraction(-1, 10)), 8
        )
        self.assertEqual(rounded, (Fraction(-3, 8), Fraction(0)))
        self.assertGreaterEqual(widening, 0)

    def test_12_interval_multiply_uses_all_four_corners(self) -> None:
        self.assertEqual(
            CHECKER.interval_multiply(
                (Fraction(-2), Fraction(3)), (Fraction(-5), Fraction(7))
            ),
            (Fraction(-15), Fraction(21)),
        )

    def test_13_threshold_is_strict_and_keeps_equal_or_crossing_boxes(self) -> None:
        epsilon = Fraction(1, 100)
        expansion = {
            1: (Fraction(-9, 1000), Fraction(9, 1000)),
            2: (Fraction(-1, 100), Fraction(1, 100)),
            3: (Fraction(-2, 100), Fraction(1, 1000)),
        }
        retained, ledger, increment = CHECKER.drop_threshold_oracle(
            expansion, epsilon, Fraction(0), 1, 1, "synthetic", "test", None
        )
        self.assertEqual(set(retained), {2, 3})
        self.assertEqual([row["mask"] for row in ledger["dropped_terms"]], [1])
        self.assertEqual(increment, Fraction(9, 1000))

    def test_14_rotation_globally_merges_before_thresholding(self) -> None:
        rounding = {"widening": Fraction(0), "events": 0}
        expansion = {1: (Fraction(1, 2), Fraction(1, 2))}
        rotated, merge = CHECKER.apply_rotation_oracle(
            expansion, 3, Fraction(0), 2, 5, 2**64, rounding
        )
        self.assertEqual(merge["input_term_count"], 1)
        self.assertEqual(merge["postmerge_term_count"], len(rotated))
        self.assertEqual(merge["postmerge_sha256"], CHECKER.terms_sha256(rotated))

    def test_15_composite_boundary_and_ledger_recurrence(self) -> None:
        composite = self.expected["composite"]
        occurrences = composite["heisenberg_occurrences"]
        self.assertEqual(
            [row["truncate_after_each_constituent"] for row in occurrences],
            [False, True, False],
        )
        self.assertEqual(
            [row["boundary_kind"] for row in composite["ledger_events"]],
            [
                "after_complete_composite",
                "after_constituent",
                "after_constituent",
                "after_constituent",
                "after_complete_composite",
            ],
        )
        cumulative = Fraction(0)
        for event in composite["ledger_events"]:
            self.assertEqual(
                CHECKER.parse_q(event["cumulative_dropped_l1_before"]), cumulative
            )
            cumulative += CHECKER.parse_q(event["dropped_l1_increment"])
            self.assertEqual(
                CHECKER.parse_q(event["cumulative_dropped_l1_after"]), cumulative
            )
        self.assertEqual(
            CHECKER.parse_q(composite["cumulative_dropped_l1"]), cumulative
        )

    def test_16_dropped_l1_widens_retained_expectation_once(self) -> None:
        composite = self.expected["composite"]
        retained = composite["retained_expectation_interval"]
        declared = composite["declared_circuit_expectation_interval"]
        dropped = CHECKER.parse_q(composite["cumulative_dropped_l1"])
        self.assertLessEqual(
            CHECKER.parse_q(declared["lower"]),
            CHECKER.parse_q(retained["lower"]) - dropped,
        )
        self.assertGreaterEqual(
            CHECKER.parse_q(declared["upper"]),
            CHECKER.parse_q(retained["upper"]) + dropped,
        )
        self.assertEqual(
            composite["rounding_accounting"],
            "absorbed_in_coefficient_boxes_not_added_again_as_scalar",
        )

    def test_17_scope_is_fail_closed(self) -> None:
        scope = self.expected["scope"]
        self.assertEqual(scope["maximum_positive_status"], CHECKER.MAXIMUM_STATUS)
        self.assertEqual(scope["L8_full_propagation"], "NOT_ASSESSED")
        self.assertEqual(
            scope["product_formula_to_exact_Hubbard_error"], "NOT_ASSESSED"
        )
        self.assertFalse(scope["physical_reference_qualified"])
        self.assertFalse(scope["ready_gate_eligible"])

    def test_18_witness_mutation_is_rejected_by_independent_oracle(self) -> None:
        mutant = copy.deepcopy(self.expected)
        mutant["composite"]["ledger_events"][3]["dropped_l1_increment"] = "0"
        with self.assertRaisesRegex(CHECKER.VerificationError, "independent oracle"):
            CHECKER.validate_witness(mutant, self.fixture, self.runtime_lock)

    def test_19_fixture_mutation_is_rejected(self) -> None:
        mutant = copy.deepcopy(self.fixture)
        mutant["interval_policy"]["threshold_epsilon"] = "1/99"
        with self.assertRaises(CHECKER.SchemaError):
            CHECKER.validate_fixture(mutant)

    def test_20_project_manifest_and_runtime_lock_are_consistent(self) -> None:
        CHECKER.validate_project_environment(self.runtime_lock)

    def test_21_policy_is_result_unpinned_and_source_locked(self) -> None:
        policy = CHECKER.load_json(BASE / CHECKER.POLICY_NAME)
        CHECKER.validate_policy(policy, self.runtime_lock)
        self.assertFalse(
            policy["precommit_boundary"]["policy_contains_observed_replay_results"]
        )
        self.assertFalse(
            policy["precommit_boundary"]["policy_contains_witness_or_result_hashes"]
        )

    def test_22_package_closure_algorithm_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.jl").write_text("module X\nend\n", encoding="utf-8")
            closure = CHECKER.source_tree_closure(root)
            self.assertEqual(closure["file_count"], 1)
            (root / "alias.jl").symlink_to("source.jl")
            with self.assertRaisesRegex(CHECKER.VerificationError, "symlink"):
                CHECKER.source_tree_closure(root)

    def test_23_precommit_contract_and_result_absence_validate(self) -> None:
        contract = CHECKER.load_json(BASE / CHECKER.PRECOMMIT_CONTRACT_NAME)
        CHECKER.validate_precommit_contract(contract)
        for artifact in CHECKER.RESULT_ARTIFACTS:
            self.assertFalse((BASE / artifact).exists())

    def test_24_full_precommit_verifier_succeeds_without_a_result(self) -> None:
        summary = CHECKER.verify_precommit()
        self.assertEqual(
            summary["status"],
            "VERIFIED_MAJORANA_P0_RESULT_UNPINNED_PRECOMMIT_INPUTS",
        )
        self.assertEqual(summary["scope_ceiling"], CHECKER.MAXIMUM_STATUS)


if __name__ == "__main__":
    unittest.main()
