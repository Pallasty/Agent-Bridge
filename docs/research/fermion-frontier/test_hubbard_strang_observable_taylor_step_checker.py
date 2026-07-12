#!/usr/bin/env python3
"""Regression tests for the fixed observable Taylor one-step checker."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import unittest
from fractions import Fraction
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "hubbard_strang_observable_taylor_step_checker",
        HERE / "hubbard_strang_observable_taylor_step_checker.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


class ObservableTaylorStepCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = checker.recompute_evidence()
        cls.profiles = {
            profile["linear_size"]: profile for profile in cls.result["profiles"]
        }
        cls.records = {
            (linear_size, record["observable_identity"]["observable_id"]): record
            for linear_size, profile in cls.profiles.items()
            for record in profile["observables"]
        }

    def test_positive_narrow_status(self) -> None:
        self.assertEqual(
            self.result["status"],
            "VERIFIED_ONE_STEP_OBSERVABLE_TAYLOR_L1_SUBCERTIFICATE",
        )
        self.assertTrue(self.result["verified"])
        self.assertFalse(self.result["ready_gate_eligible"])

    def test_full_R100_error_is_not_assessed(self) -> None:
        scope = self.result["scope_claims"]
        self.assertEqual(
            scope["full_R100_observable_error_upper_bound"],
            "NOT_ASSESSED_EVOLVED_OBSERVABLE_UNIFORMITY_REQUIRED",
        )
        self.assertFalse(scope["actual_R100_observable_error_lower_bounded"])
        self.assertEqual(scope["per_step_evolved_observable_ledger"], "NOT_ASSESSED")

    def test_base_source_pins_match_bytes(self) -> None:
        for pin in checker.SOURCE_PINS:
            payload = (HERE / pin["relative_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), pin["sha256"])

    def test_bound_source_pdf_pin(self) -> None:
        self.assertEqual(
            checker.BOUND_SOURCE["audited_pdf_sha256"],
            "c1afaae4a944ba5c32bb5c86e421986bbcd89c14dae959d73560db979e668806",
        )

    def test_nine_stage_palindrome_and_coefficients(self) -> None:
        self.assertEqual(
            [group for group, _ in checker.STAGES],
            ["H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1"],
        )
        self.assertEqual(
            [coefficient for _, coefficient in checker.STAGES],
            [
                Fraction(1, 2), Fraction(1, 2), Fraction(1, 2), Fraction(1, 2),
                Fraction(1), Fraction(1, 2), Fraction(1, 2), Fraction(1, 2),
                Fraction(1, 2),
            ],
        )

    def test_runtime_stage_binding_and_deterministic_resource_payload(self) -> None:
        binding = self.result["stage_binding"]
        self.assertEqual(
            binding["pinned_raw_event_order"],
            ["H1", "H2", "HU", "H3", "H4", "H4", "H3", "HU", "H2", "H1"],
        )
        self.assertTrue(binding["consecutive_central_H4_half_steps_exactly_combined"])
        self.assertEqual(len(binding["collapsed_nine_stage_records_sha256"]), 64)
        self.assertNotIn("runtime_seconds", self.result["resource_usage"])

    def test_profile_sizes_and_observable_order(self) -> None:
        self.assertEqual(list(self.profiles), [2, 3, 8])
        for profile in self.profiles.values():
            self.assertEqual(
                [item["observable_identity"]["observable_id"] for item in profile["observables"]],
                ["staggered_magnetization", "double_occupancy"],
            )

    def test_observable_identity_ledgers(self) -> None:
        for linear_size in (2, 3, 8):
            magnetization = self.records[(linear_size, "staggered_magnetization")]
            occupancy = self.records[(linear_size, "double_occupancy")]
            self.assertEqual(
                magnetization["observable_identity"]["omitted_commuting_identity_coefficient"],
                "0/1",
            )
            self.assertEqual(
                occupancy["observable_identity"]["omitted_commuting_identity_coefficient"],
                "1/4",
            )
            self.assertEqual(
                magnetization["observable_identity"]["full_observable_Pauli_L1"], "1/1"
            )
            self.assertEqual(
                occupancy["observable_identity"]["full_observable_Pauli_L1"], "1/1"
            )

    def test_formal_residuals_zero_through_degree_two(self) -> None:
        for record in self.records.values():
            self.assertEqual(
                [(item["degree"], item["term_count"]) for item in record["formal_residuals"]],
                [(0, 0), (1, 0), (2, 0)],
            )

    def test_all_495_fourth_order_paths(self) -> None:
        for record in self.records.values():
            remainder = record["degree_four_remainder"]
            self.assertEqual(remainder["weak_composition_count"], 495)
            self.assertEqual(len(remainder["path_records_sha256"]), 64)

    def test_L2_exact_coefficients(self) -> None:
        expected = {
            "staggered_magnetization": ("88/3", "648/1", "1343/37500000"),
            "double_occupancy": ("10/1", "496/1", "187/12500000"),
        }
        for observable_id, values in expected.items():
            record = self.records[(2, observable_id)]
            self.assertEqual(
                record["degree_three_defect"]["coefficient_L1_operator_norm_upper_bound"],
                values[0],
            )
            self.assertEqual(
                record["degree_four_remainder"]["total_E4_plus_P4_L1"], values[1]
            )
            self.assertEqual(record["one_step_certificate"]["operator_error_upper_bound"], values[2])

    def test_L3_exact_coefficients(self) -> None:
        expected = {
            "staggered_magnetization": ("1264/27", "13115/9", "33149/540000000"),
            "double_occupancy": ("152/9", "36166/27", "40883/1350000000"),
        }
        for observable_id, values in expected.items():
            record = self.records[(3, observable_id)]
            self.assertEqual(
                record["degree_three_defect"]["coefficient_L1_operator_norm_upper_bound"],
                values[0],
            )
            self.assertEqual(
                record["degree_four_remainder"]["total_E4_plus_P4_L1"], values[1]
            )
            self.assertEqual(record["one_step_certificate"]["operator_error_upper_bound"], values[2])

    def test_L8_magnetization_exact_coefficients(self) -> None:
        record = self.records[(8, "staggered_magnetization")]
        self.assertEqual(
            record["degree_three_defect"]["coefficient_L1_operator_norm_upper_bound"],
            "1703/24",
        )
        remainder = record["degree_four_remainder"]
        self.assertEqual(remainder["ideal_E4_L1"], "15275/12")
        self.assertEqual(remainder["product_P4_L1"], "25287/16")
        self.assertEqual(remainder["total_E4_plus_P4_L1"], "136961/48")

    def test_L8_occupancy_exact_coefficients(self) -> None:
        record = self.records[(8, "double_occupancy")]
        self.assertEqual(
            record["degree_three_defect"]["coefficient_L1_operator_norm_upper_bound"],
            "423/16",
        )
        remainder = record["degree_four_remainder"]
        self.assertEqual(remainder["ideal_E4_L1"], "16633/12")
        self.assertEqual(remainder["product_P4_L1"], "37211/24")
        self.assertEqual(remainder["total_E4_plus_P4_L1"], "70477/24")

    def test_L8_strict_one_step_operator_bounds(self) -> None:
        self.assertEqual(
            self.records[(8, "staggered_magnetization")]["one_step_certificate"]["operator_error_upper_bound"],
            "159187/1600000000",
        )
        self.assertEqual(
            self.records[(8, "double_occupancy")]["one_step_certificate"]["operator_error_upper_bound"],
            "133927/2400000000",
        )
        for observable_id in checker.OBSERVABLES:
            self.assertTrue(
                self.records[(8, observable_id)]["one_step_certificate"][
                    "one_step_bound_below_full_time_allocation"
                ]
            )
            self.assertTrue(
                self.records[(8, observable_id)]["one_step_certificate"][
                    "does_not_certify_full_R100_error"
                ]
            )

    def test_initial_Neel_expectation_bounds_drop_D3(self) -> None:
        magnetization = self.records[(8, "staggered_magnetization")]
        occupancy = self.records[(8, "double_occupancy")]
        self.assertEqual(
            magnetization["Neel_sector_degree_three_action"]["basis_expectation"], "0/1"
        )
        self.assertEqual(
            occupancy["Neel_sector_degree_three_action"]["basis_expectation"], "0/1"
        )
        self.assertEqual(
            magnetization["one_step_certificate"]["initial_Neel_expectation_error_upper_bound"],
            "136961/4800000000",
        )
        self.assertEqual(
            occupancy["one_step_certificate"]["initial_Neel_expectation_error_upper_bound"],
            "70477/2400000000",
        )

    def test_uniform_supremum_floor_is_not_actual_error_bound(self) -> None:
        expected = {
            "staggered_magnetization": ("159187/16000000", "159187/4000"),
            "double_occupancy": ("133927/24000000", "133927/6000"),
        }
        for observable_id, values in expected.items():
            record = self.records[(8, observable_id)]["uniform_supremum_architecture"]
            self.assertEqual(record["initial_k0_floor_after_R_factor"], values[0])
            self.assertEqual(record["floor_to_allocation_ratio"], values[1])
            self.assertTrue(
                record["uniform_supremum_Pauli_L1_architecture_cannot_qualify_at_R100"]
            )
            self.assertFalse(record["used_as_actual_R100_error_bound"])

    def test_L8_magnetization_action_witness_exceeds_leading_ceiling(self) -> None:
        action = self.records[(8, "staggered_magnetization")][
            "Neel_sector_degree_three_action"
        ]
        self.assertEqual(action["nonzero_output_count"], 1080)
        self.assertEqual(action["action_norm_squared"], "135913/18432")
        self.assertEqual(action["action_norm_squared_to_ceiling_squared_ratio"], "135913/115200")
        self.assertTrue(action["exact_action_witness_exceeds_uniform_leading_ceiling"])

    def test_L8_occupancy_action_witness_does_not_exceed_leading_ceiling(self) -> None:
        action = self.records[(8, "double_occupancy")][
            "Neel_sector_degree_three_action"
        ]
        self.assertEqual(action["nonzero_output_count"], 968)
        self.assertEqual(action["action_norm_squared"], "79145/73728")
        self.assertEqual(action["action_norm_squared_to_ceiling_squared_ratio"], "15829/92160")
        self.assertFalse(action["exact_action_witness_exceeds_uniform_leading_ceiling"])

    def test_L8_D3_and_action_digests_are_pinned(self) -> None:
        expected = {
            "staggered_magnetization": (
                "3a1c0d3b190d4e1d7c98654a0f578aaf0d4e4809846280cc830ac10e163138d8",
                "aad2c8d93d5cf3775f2d23d74678e74cbf47ac68cbc5157f99af1aa1653e74c6",
            ),
            "double_occupancy": (
                "069f0d7d28804d2981081b84393e88696a55628814da625ff82df0beaa262aba",
                "f867aa8f76806531861e2b8084bff38331dd4349b9325b0a492fd9405e6e44b4",
            ),
        }
        for observable_id, (expansion_digest, action_digest) in expected.items():
            record = self.records[(8, observable_id)]
            self.assertEqual(
                record["degree_three_defect"]["expansion_sha256"], expansion_digest
            )
            self.assertEqual(
                record["Neel_sector_degree_three_action"]["action_records_sha256"],
                action_digest,
            )

    def test_L8_actions_preserve_sector(self) -> None:
        for observable_id in checker.OBSERVABLES:
            action = self.records[(8, observable_id)]["Neel_sector_degree_three_action"]
            self.assertEqual(action["spin_up_particle_count"], 32)
            self.assertEqual(action["spin_down_particle_count"], 32)
            self.assertTrue(action["all_outputs_remain_in_fixed_particle_spin_sector"])

    def test_expected_D3_term_counts(self) -> None:
        expected = {
            (2, "staggered_magnetization"): 128,
            (2, "double_occupancy"): 128,
            (3, "staggered_magnetization"): 544,
            (3, "double_occupancy"): 648,
            (8, "staggered_magnetization"): 6784,
            (8, "double_occupancy"): 8928,
        }
        for key, count in expected.items():
            self.assertEqual(self.records[key]["degree_three_defect"]["term_count"], count)

    def test_resource_ledger_within_caps(self) -> None:
        usage = self.result["resource_usage"]
        self.assertGreater(usage["commutator_pair_products"], 0)
        self.assertLessEqual(
            usage["commutator_pair_products"], checker.RESOURCE_LIMITS["max_pair_products"]
        )
        self.assertLessEqual(
            usage["peak_expansion_terms"], checker.RESOURCE_LIMITS["max_expansion_terms"]
        )

    def test_recompute_cache_returns_fresh_equal_copy(self) -> None:
        second = checker.recompute_evidence()
        self.assertEqual(second, self.result)
        self.assertIsNot(second, self.result)

    def test_warm_cache_still_rechecks_source_pins(self) -> None:
        with mock.patch.object(
            checker,
            "_verify_source_pins",
            side_effect=checker.VerificationError("warm source drift"),
        ):
            with self.assertRaisesRegex(checker.VerificationError, "warm source drift"):
                checker.recompute_evidence()

    def test_canonical_hash_is_order_independent(self) -> None:
        self.assertEqual(
            checker.canonical_sha256({"a": 1, "b": 2}),
            checker.canonical_sha256({"b": 2, "a": 1}),
        )

    def test_tiny_commutator_phase_and_L1(self) -> None:
        backend = checker._load_backend()
        counter = checker.ComputationCounter()
        expansion = checker._commutator(
            backend,
            {(1, 0): (Fraction(1), Fraction(0))},
            {(0, 1): (Fraction(1), Fraction(0))},
            counter,
        )
        self.assertEqual(expansion, {(1, 1): (Fraction(0), Fraction(-2))})
        self.assertEqual(checker._l1(expansion), 2)

    def test_source_pin_failure_is_closed(self) -> None:
        pin = checker.SOURCE_PINS[0]
        with self.assertRaisesRegex(checker.VerificationError, "source pin drift"):
            checker._read_pinned(HERE / pin["relative_path"], "0" * 64)

    def test_pair_resource_cap_is_enforced(self) -> None:
        original = checker.RESOURCE_LIMITS["max_pair_products"]
        checker.RESOURCE_LIMITS["max_pair_products"] = 0
        try:
            with self.assertRaisesRegex(checker.VerificationError, "pair-product cap"):
                checker.ComputationCounter().reserve_pairs(1)
        finally:
            checker.RESOURCE_LIMITS["max_pair_products"] = original

    def test_pair_cap_rejects_before_commutator_work(self) -> None:
        backend = mock.Mock()
        original = checker.RESOURCE_LIMITS["max_pair_products"]
        checker.RESOURCE_LIMITS["max_pair_products"] = 0
        try:
            with self.assertRaisesRegex(checker.VerificationError, "pair-product cap"):
                checker._commutator(
                    backend,
                    {(1, 0): (Fraction(1), Fraction(0))},
                    {(0, 1): (Fraction(1), Fraction(0))},
                    checker.ComputationCounter(),
                )
            backend._pauli_commutes.assert_not_called()
        finally:
            checker.RESOURCE_LIMITS["max_pair_products"] = original

    def test_main_failure_clears_positive_boolean_scope(self) -> None:
        stream = io.StringIO()
        with mock.patch.object(checker, "recompute_evidence", side_effect=ValueError("boom")):
            with contextlib.redirect_stdout(stream):
                status = checker.main([])
        payload = json.loads(stream.getvalue())
        self.assertEqual(status, 1)
        self.assertFalse(payload["verified"])
        self.assertFalse(payload["ready_gate_eligible"])
        self.assertEqual(payload["status"], "VERIFICATION_FAILED")
        self.assertIn("boom", payload["errors"])
        for key, value in checker.SCOPE_CLAIMS.items():
            if value is True:
                self.assertFalse(payload["scope_claims"][key])

    def test_main_positive_cli_boundary_is_nonzero(self) -> None:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            status = checker.main([])
        payload = json.loads(stream.getvalue())
        self.assertEqual(status, 1)
        self.assertEqual(payload["status"], checker.MAXIMUM_POSITIVE_STATUS)
        self.assertTrue(payload["verified"])
        self.assertFalse(payload["ready_gate_eligible"])


if __name__ == "__main__":
    unittest.main()
