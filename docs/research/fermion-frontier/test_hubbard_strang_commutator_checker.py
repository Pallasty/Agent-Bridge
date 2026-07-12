import copy
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECKER = load_module(
    "hubbard_strang_commutator_checker", "hubbard_strang_commutator_checker.py"
)


def load_json(name):
    with (HERE / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class HubbardStrangCommutatorCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_json("hubbard_strang_commutator_contract.json")
        cls.certificate = load_json("hubbard_strang_commutator_template.json")
        cls.positive = CHECKER.verify_certificate(cls.contract, cls.certificate)

    def verify(self, contract=None, certificate=None):
        return CHECKER.verify_certificate(
            self.contract if contract is None else contract,
            self.certificate if certificate is None else certificate,
        )

    def profile(self, linear_size):
        return next(
            item
            for item in self.positive["recomputed_profiles"]
            if item["linear_size"] == linear_size
        )

    def test_01_positive_template_has_only_narrow_status(self):
        self.assertEqual(
            self.positive["status"],
            "VERIFIED_STRANG_COMMUTATOR_L1_SUBCERTIFICATE",
        )
        self.assertTrue(self.positive["verified"])
        self.assertFalse(self.positive["ready_gate_eligible"])

    def test_02_positive_scope_does_not_compose_mapping_or_truncation(self):
        scope = self.positive["scope_claims"]
        self.assertFalse(scope["mapping_certificate_composed"])
        self.assertFalse(scope["truncation_certificate_composed"])
        self.assertEqual(scope["physical_L8_instance_identity"], "NOT_ASSESSED")
        self.assertEqual(scope["observable_specific_tightening"], "NOT_ASSESSED")

    def test_03_contract_verifies(self):
        self.assertEqual(CHECKER.validate_contract(self.contract), [])

    def test_04_L2_exact_coefficient_and_bounds(self):
        profile = self.profile(2)
        self.assertEqual(profile["one_step_commutator_coefficient_C"], "176/3")
        self.assertEqual(profile["R_step_unitary_error_bound"], "11/1875")
        self.assertEqual(profile["generic_norm_one_observable_error_bound"], "22/1875")

    def test_05_L3_exact_coefficient_and_bounds(self):
        profile = self.profile(3)
        self.assertEqual(profile["one_step_commutator_coefficient_C"], "1297/6")
        self.assertEqual(profile["R_step_unitary_error_bound"], "1297/60000")
        self.assertEqual(profile["generic_norm_one_observable_error_bound"], "1297/30000")

    def test_06_L8_exact_coefficient_and_bounds(self):
        profile = self.profile(8)
        self.assertEqual(profile["tail_nested_l1_sum"], "22752/1")
        self.assertEqual(profile["self_nested_l1_sum"], "11104/1")
        self.assertEqual(profile["one_step_commutator_coefficient_C"], "7076/3")
        self.assertEqual(profile["R_step_unitary_error_bound"], "1769/7500")
        self.assertEqual(profile["generic_norm_one_observable_error_bound"], "1769/3750")

    def test_07_L8_per_group_nested_L1_values(self):
        records = self.profile(8)["commutator_records"]
        self.assertEqual(
            [(x["tail_nested_l1"], x["self_nested_l1"]) for x in records],
            [
                ("10144/1", "2240/1"),
                ("5760/1", "1536/1"),
                ("6656/1", "7168/1"),
                ("192/1", "160/1"),
                ("0/1", "0/1"),
            ],
        )

    def test_08_L8_group_term_counts(self):
        records = self.profile(8)["group_records"]
        self.assertEqual(
            [records[group]["term_count"] for group in CHECKER.GROUPS],
            [128, 96, 192, 96, 128],
        )
        self.assertEqual(self.profile(8)["total_nonidentity_term_count"], 640)

    def test_09_L2_and_L3_group_term_counts(self):
        expected = {
            2: [8, 0, 12, 0, 8],
            3: [12, 12, 27, 12, 12],
        }
        for linear_size, counts in expected.items():
            records = self.profile(linear_size)["group_records"]
            self.assertEqual(
                [records[group]["term_count"] for group in CHECKER.GROUPS], counts
            )

    def test_10_all_group_terms_pairwise_commute(self):
        for linear_size in CHECKER.PROFILE_SIZES:
            groups = CHECKER.canonical_group_expansions(linear_size)
            pair_counts = CHECKER._verify_internal_commutation(groups)
            self.assertEqual(
                pair_counts,
                {
                    group: len(groups[group]) * (len(groups[group]) - 1) // 2
                    for group in CHECKER.GROUPS
                },
            )

    def test_11_noncommuting_group_tamper_is_rejected(self):
        groups = {group: {} for group in CHECKER.GROUPS}
        groups["H1"] = {
            CHECKER._string_to_masks("X"): (Fraction(1), Fraction(0)),
            CHECKER._string_to_masks("Z"): (Fraction(1), Fraction(0)),
        }
        with self.assertRaisesRegex(CHECKER.VerificationError, "noncommuting"):
            CHECKER._verify_internal_commutation(groups)

    def test_12_raw_S2_order_is_exact_palindrome(self):
        self.assertEqual(
            CHECKER.RAW_S2_ORDER,
            ("H1", "H2", "HU", "H3", "H4", "H4", "H3", "HU", "H2", "H1"),
        )
        self.assertEqual(CHECKER.RAW_S2_ORDER, tuple(reversed(CHECKER.RAW_S2_ORDER)))

    def test_13_raw_S2_binding_counts_every_nonidentity_term_twice(self):
        for linear_size in CHECKER.PROFILE_SIZES:
            profile = self.profile(linear_size)
            binding = profile["raw_s2_binding"]
            self.assertEqual(binding["raw_group_event_count_per_step"], 10)
            self.assertEqual(
                binding["raw_nonidentity_term_event_count_per_step"],
                2 * profile["total_nonidentity_term_count"],
            )

    def test_14_raw_S2_hashes_are_canonical_sha256(self):
        for linear_size in CHECKER.PROFILE_SIZES:
            binding = self.profile(linear_size)["raw_s2_binding"]
            self.assertRegex(binding["raw_group_events_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(binding["raw_nonidentity_term_events_sha256"], r"^[0-9a-f]{64}$")

    def test_15_identity_phase_ledger_scales_as_two_L_squared(self):
        for linear_size in CHECKER.PROFILE_SIZES:
            ledger = self.profile(linear_size)["identity_phase_ledger"]
            expected = f"{2 * linear_size * linear_size}/1"
            self.assertEqual(ledger["omitted_HU_identity_coefficient"], expected)
            self.assertEqual(ledger["full_time_common_phase_exponent"], expected)
            self.assertIn("OPERATOR_NORM_DIFFERENCE_IS_UNCHANGED", ledger["status"])

    def test_16_L2_sparse_action_oracle_is_full_basis(self):
        oracle = self.profile(2)["action_oracle"]
        self.assertEqual(oracle["coverage"], "ALL_COMPUTATIONAL_BASIS_STATES")
        self.assertEqual(oracle["basis_state_count"], 256)
        self.assertEqual(oracle["operator_action_comparison_count"], 3840)

    def test_17_L3_sparse_action_oracle_has_fixed_nonempty_coverage(self):
        oracle = self.profile(3)["action_oracle"]
        self.assertEqual(oracle["coverage"], "FIXED_16_COMPUTATIONAL_BASIS_STATES")
        self.assertEqual(oracle["basis_state_count"], 16)
        self.assertEqual(oracle["operator_action_comparison_count"], 240)

    def test_18_L8_action_oracle_is_explicitly_not_run(self):
        oracle = self.profile(8)["action_oracle"]
        self.assertEqual(oracle["status"], "NOT_RUN_L8_ACTION_ORACLE_RESOURCE_LIMIT")
        self.assertEqual(oracle["basis_state_count"], 0)

    def test_19_direct_two_by_two_numerical_formula_oracle(self):
        oracle = CHECKER.numerical_formula_oracle()
        self.assertEqual(oracle["theorem_bound"], "1/2000")
        self.assertTrue(oracle["direct_error_strictly_below_bound"])
        self.assertLess(float(oracle["direct_spectral_error_decimal"]), 0.0005)
        self.assertIn("NOT_USED", oracle["floating_point_role"])

    def test_20_primary_formula_source_is_version_and_result_pinned(self):
        source = self.contract["bound_source"]
        self.assertEqual(source["arxiv_version"], "2306.10603v2")
        self.assertEqual(source["doi"], "10.1103/PhysRevB.108.195105")
        self.assertIn("Proposition 2", source["result"])
        self.assertIn("/12", source["formula"])
        self.assertIn("/24", source["formula"])

    def test_21_R_step_telescoping_is_R_times_single_step(self):
        for linear_size in CHECKER.PROFILE_SIZES:
            profile = self.profile(linear_size)
            one_step = CHECKER.parse_fraction(profile["single_step_unitary_error_bound"])
            total = CHECKER.parse_fraction(profile["R_step_unitary_error_bound"])
            self.assertEqual(total, CHECKER.TROTTER_STEPS * one_step)

    def test_22_generic_observable_bound_is_twice_unitary_bound(self):
        for linear_size in CHECKER.PROFILE_SIZES:
            profile = self.profile(linear_size)
            unitary = CHECKER.parse_fraction(profile["R_step_unitary_error_bound"])
            observable = CHECKER.parse_fraction(
                profile["generic_norm_one_observable_error_bound"]
            )
            self.assertEqual(observable, 2 * unitary)

    def test_23_R100_fails_every_fixed_observable_allocation(self):
        for linear_size in CHECKER.PROFILE_SIZES:
            profile = self.profile(linear_size)
            self.assertFalse(profile["per_observable_allocation_satisfied_at_R100"])
            self.assertGreater(
                CHECKER.parse_fraction(profile["generic_norm_one_observable_error_bound"]),
                Fraction(1, 4000),
            )

    def test_24_L8_minimum_generic_observable_R_boundary(self):
        coefficient = Fraction(7076, 3)
        self.assertGreater(Fraction(2) * coefficient / 4343**2, Fraction(1, 4000))
        self.assertLessEqual(Fraction(2) * coefficient / 4344**2, Fraction(1, 4000))
        self.assertEqual(
            self.profile(8)["minimum_R_for_generic_norm_one_observable_allocation"],
            4344,
        )

    def test_25_checker_and_every_dependency_are_source_pinned(self):
        self.assertEqual(
            self.contract["checker_source_sha256"],
            hashlib.sha256((HERE / "hubbard_strang_commutator_checker.py").read_bytes()).hexdigest(),
        )
        for pin in self.contract["source_pins"]:
            self.assertEqual(
                pin["sha256"],
                hashlib.sha256((HERE / pin["relative_path"]).read_bytes()).hexdigest(),
            )

    def test_26_cross_source_positive_path_reports_mapping_and_bitset_checks(self):
        cross = self.positive["cross_source_conformance"]
        self.assertTrue(
            self.positive["checker_executed_source_bytes_sha256_verified"]
        )
        self.assertEqual(cross["status"], "VERIFIED_HASHED_CROSS_SOURCE_CONFORMANCE")
        self.assertEqual(
            cross["mapping_template_status"],
            "VERIFIED_CANONICAL_JW_MAPPING_SUBCERTIFICATE",
        )
        self.assertEqual(cross["bitset_single_qubit_product_checks"], 16)

    def test_27_cli_positive_subcertificate_still_exits_one(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(HERE / "hubbard_strang_commutator_checker.py"),
                str(HERE / "hubbard_strang_commutator_contract.json"),
                str(HERE / "hubbard_strang_commutator_template.json"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("VERIFIED_STRANG_COMMUTATOR_L1_SUBCERTIFICATE", completed.stdout)
        self.assertIn('"ready_gate_eligible": false', completed.stdout)

    def test_28_checker_source_hash_tamper_is_invalid_schema(self):
        bad = copy.deepcopy(self.contract)
        bad["checker_source_sha256"] = "0" * 64
        result = self.verify(contract=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["scope_claims"]["nested_commutators_exactly_aggregated"])

    def test_29_source_pin_tamper_is_invalid_schema(self):
        bad = copy.deepcopy(self.contract)
        bad["source_pins"][0]["sha256"] = "0" * 64
        result = self.verify(contract=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["scope_claims"]["source_pins_verified"])

    def test_30_contract_float_schema_version_is_rejected(self):
        bad = copy.deepcopy(self.contract)
        bad["schema_version"] = 1.0
        result = self.verify(contract=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")

    def test_31_contract_extra_key_is_rejected(self):
        bad = copy.deepcopy(self.contract)
        bad["unexpected"] = False
        self.assertEqual(self.verify(contract=bad)["status"], "INVALID_SCHEMA")

    def test_32_certificate_extra_key_is_rejected(self):
        bad = copy.deepcopy(self.certificate)
        bad["unexpected"] = False
        self.assertEqual(self.verify(certificate=bad)["status"], "INVALID_SCHEMA")

    def test_33_certificate_policy_overclaim_is_invalid_schema(self):
        bad = copy.deepcopy(self.certificate)
        bad["scope_claims"]["ready_gate_eligible"] = True
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["ready_gate_eligible"])

    def test_34_well_shaped_bound_tamper_is_verification_failed(self):
        bad = copy.deepcopy(self.certificate)
        bad["profile_claims"][2]["R_step_unitary_error_bound"] = "1/1"
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertFalse(result["scope_claims"]["pinned_strang_bound_and_R_step_telescoping_verified"])

    def test_35_well_shaped_digest_tamper_is_verification_failed(self):
        bad = copy.deepcopy(self.certificate)
        bad["profile_claims"][2]["commutator_records"][0]["tail_nested_sha256"] = "0" * 64
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")

    def test_36_numerical_oracle_tamper_is_verification_failed(self):
        bad = copy.deepcopy(self.certificate)
        bad["numerical_formula_oracle"]["theorem_bound"] = "1/1000"
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")

    def test_37_contract_formula_constant_tamper_is_invalid_schema(self):
        bad = copy.deepcopy(self.contract)
        bad["bound_source"]["formula"] = bad["bound_source"]["formula"].replace("/12", "/6")
        result = self.verify(contract=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")

    def test_38_duplicate_JSON_key_is_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write('{"schema_version":1,"schema_version":1}')
            path = pathlib.Path(handle.name)
        try:
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                CHECKER.load_strict_json(path)
        finally:
            path.unlink()

    def test_39_nonfinite_JSON_constant_is_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write('{"value":NaN}')
            path = pathlib.Path(handle.name)
        try:
            with self.assertRaisesRegex(ValueError, "non-finite"):
                CHECKER.load_strict_json(path)
        finally:
            path.unlink()

    def test_40_bounded_read_uses_max_plus_one_even_for_dev_zero(self):
        zero = pathlib.Path("/dev/zero")
        if not zero.exists():
            self.skipTest("/dev/zero unavailable")
        with self.assertRaisesRegex(ValueError, "exceeds byte cap"):
            CHECKER.load_strict_json(zero, 64)

    def test_41_fraction_parser_requires_reduced_canonical_strings(self):
        self.assertEqual(CHECKER.parse_fraction("-7/9"), Fraction(-7, 9))
        for bad in ("1", "2/4", "+1/2", "01/2", "1/0", 1, True):
            with self.subTest(bad=bad):
                with self.assertRaises((CHECKER.SchemaError, ZeroDivisionError)):
                    CHECKER.parse_fraction(bad)

    def test_42_unknown_linear_size_is_rejected(self):
        for value in (1, 4, 8.0, True):
            with self.subTest(value=value):
                with self.assertRaises(CHECKER.SchemaError):
                    CHECKER.canonical_group_expansions(value)

    def test_43_single_qubit_commutator_signs_are_exact(self):
        x = {CHECKER._string_to_masks("X"): (Fraction(1), Fraction(0))}
        z = {CHECKER._string_to_masks("Z"): (Fraction(1), Fraction(0))}
        counter = CHECKER.ComputationCounter()
        result = CHECKER.exact_commutator(z, x, counter)
        y = CHECKER._string_to_masks("Y")
        self.assertEqual(result, {y: (Fraction(0), Fraction(2))})
        self.assertEqual(counter.commutator_pair_products, 1)

    def test_44_exact_commutator_merges_cancellation_before_L1(self):
        x = CHECKER._string_to_masks("XI")
        z1 = CHECKER._string_to_masks("ZI")
        z2 = CHECKER._string_to_masks("ZZ")
        left = {z1: (Fraction(1), Fraction(0)), z2: (Fraction(-1), Fraction(0))}
        right = {x: (Fraction(1), Fraction(0))}
        result = CHECKER.exact_commutator(left, right, CHECKER.ComputationCounter())
        self.assertEqual(len(result), 2)
        self.assertEqual(CHECKER._pure_axis_l1(result, "imag"), Fraction(4))

    def test_45_commutator_pair_resource_cap_fails_closed(self):
        expansion = {
            CHECKER._string_to_masks("X"): (Fraction(1), Fraction(0)),
            CHECKER._string_to_masks("Z"): (Fraction(1), Fraction(0)),
        }
        counter = CHECKER.ComputationCounter()
        with mock.patch.dict(
            CHECKER.RESOURCE_LIMITS, {"max_commutator_pair_products": 3}
        ):
            with self.assertRaises(CHECKER.ResourceLimitError):
                CHECKER.exact_commutator(expansion, expansion, counter)

    def test_46_direct_source_read_OSError_clears_all_positive_scopes(self):
        with mock.patch.object(
            CHECKER, "_verified_source_bytes", side_effect=OSError("source unavailable")
        ):
            result = CHECKER._verify_certificate_impl(
                self.contract, self.certificate
            )
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["verified"])
        self.assertFalse(result["ready_gate_eligible"])
        self.assertTrue(
            all(
                value is not True
                for value in result["scope_claims"].values()
            )
        )

    def test_47_checker_source_read_OSError_is_invalid_schema(self):
        with mock.patch.object(
            CHECKER, "_read_checker_source_bytes", side_effect=OSError("checker missing")
        ):
            result = self.verify()
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["scope_claims"]["source_pins_verified"])

    def test_48_late_recomputation_failure_clears_scopes(self):
        expected = copy.deepcopy(self.contract["expected_profiles"])
        with mock.patch.object(
            CHECKER,
            "expected_profile_summaries",
            side_effect=[expected, CHECKER.VerificationError("late failure")],
        ):
            result = CHECKER._verify_certificate_impl(
                self.contract, self.certificate
            )
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertFalse(result["scope_claims"]["nested_commutators_exactly_aggregated"])

    def test_49_public_API_ignores_loaded_module_monkeypatch_and_reexecutes_source(self):
        forged = {
            "status": "FORGED_READY",
            "verified": True,
            "ready_gate_eligible": True,
        }
        with mock.patch.object(
            CHECKER, "_verify_certificate_impl", return_value=forged
        ):
            result = self.verify()
        self.assertEqual(
            result["status"], "VERIFIED_STRANG_COMMUTATOR_L1_SUBCERTIFICATE"
        )
        self.assertFalse(result["ready_gate_eligible"])
        self.assertTrue(result["checker_executed_source_bytes_sha256_verified"])

    def test_50_source_pin_mismatch_is_rejected_before_compile_or_exec(self):
        with mock.patch.object(
            CHECKER, "_read_checker_source_bytes", return_value=b"drifted source"
        ), mock.patch.object(
            CHECKER.types,
            "ModuleType",
            side_effect=AssertionError("must not execute drifted source"),
        ) as module_constructor:
            result = self.verify()
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertIn("before compile/exec", result["errors"][0])
        module_constructor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
