import copy
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "operator_propagation_certificate_checker",
    HERE / "operator_propagation_certificate_checker.py",
)
CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CHECKER)


def load_json(name):
    with (HERE / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class OperatorPropagationCertificateCheckerTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_json("operator_propagation_certificate_contract.json")
        self.certificate = load_json("operator_propagation_certificate_template.json")

    def verify(self, contract=None, certificate=None):
        return CHECKER.verify_certificate(
            self.contract if contract is None else contract,
            self.certificate if certificate is None else certificate,
        )

    def repin_sequence(self, contract, certificate):
        digest = CHECKER.canonical_generator_sequence_sha256(certificate)
        contract["expected_generator_sequence_sha256"] = digest
        certificate["generator_sequence_sha256"] = digest

    def repin_initial_terms(self, contract, certificate):
        digest = CHECKER.canonical_initial_terms_sha256(certificate)
        contract["expected_initial_terms_sha256"] = digest
        certificate["initial_terms_sha256"] = digest

    def test_template_verifies_only_the_bounded_subcertificate_scope(self):
        result = self.verify()
        self.assertEqual(
            result["status"], "VERIFIED_CIRCUIT_TRUNCATION_SUBCERTIFICATE"
        )
        self.assertTrue(result["verified"])
        self.assertFalse(result["ready_gate_eligible"])
        self.assertEqual(result["recomputed_cumulative_dropped_l1"], "1/10")
        self.assertEqual(
            result["recomputed_final_retained_expectation_interval"],
            {"lower": "335/384", "upper": "337/384"},
        )
        self.assertEqual(
            result["recomputed_declared_circuit_expectation_interval"],
            {"lower": "1483/1920", "upper": "1877/1920"},
        )
        self.assertEqual(
            result["truncation_error_budget_adequacy"], "NOT_ASSESSED"
        )
        self.assertEqual(
            result["scope_claims"]["product_formula_to_exact_hamiltonian"],
            "NOT_ASSESSED",
        )
        self.assertEqual(
            result["scope_claims"]["fermion_to_qubit_mapping_identity"],
            "NOT_ASSESSED",
        )

    def test_cli_subcertificate_still_exits_nonzero(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(HERE / "operator_propagation_certificate_checker.py"),
                str(HERE / "operator_propagation_certificate_contract.json"),
                str(HERE / "operator_propagation_certificate_template.json"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("VERIFIED_CIRCUIT_TRUNCATION_SUBCERTIFICATE", completed.stdout)
        self.assertIn('"ready_gate_eligible": false', completed.stdout)

    def test_fraction_parser_is_exact_and_fail_closed(self):
        self.assertEqual(CHECKER.parse_fraction("-3/7"), Fraction(-3, 7))
        for value in (True, 0, 0.5, "2/2", "1/-2", "1/0", "0/2", "1"):
            with self.subTest(value=value):
                with self.assertRaises(CHECKER.SchemaError):
                    CHECKER.parse_fraction(value)

    def test_taylor_zero_is_exact(self):
        sine, cosine = CHECKER.taylor_sin_cos_interval(Fraction(0), 0)
        self.assertEqual(sine, (Fraction(0), Fraction(0)))
        self.assertEqual(cosine, (Fraction(1), Fraction(1)))

    def test_taylor_remainders_at_one_and_half(self):
        sine, cosine = CHECKER.taylor_sin_cos_interval(Fraction(1), 0)
        self.assertEqual(sine, (Fraction(5, 6), Fraction(7, 6)))
        self.assertEqual(cosine, (Fraction(1, 2), Fraction(3, 2)))
        negative_sine, negative_cosine = CHECKER.taylor_sin_cos_interval(
            Fraction(-1), 0
        )
        self.assertEqual(negative_sine, (Fraction(-7, 6), Fraction(-5, 6)))
        self.assertEqual(negative_cosine, cosine)

        sine, cosine = CHECKER.taylor_sin_cos_interval(Fraction(1, 2), 1)
        self.assertEqual(
            sine, (Fraction(23, 48) - Fraction(1, 3840), Fraction(23, 48) + Fraction(1, 3840))
        )
        self.assertEqual(
            cosine, (Fraction(7, 8) - Fraction(1, 384), Fraction(7, 8) + Fraction(1, 384))
        )

    def test_taylor_rejects_wrong_types_and_out_of_domain(self):
        for theta, order in (
            (True, 0),
            (0.0, 0),
            (Fraction(0), True),
            (Fraction(0), -1),
            (Fraction(2), 0),
        ):
            with self.subTest(theta=theta, order=order):
                with self.assertRaises(CHECKER.SchemaError):
                    CHECKER.taylor_sin_cos_interval(theta, order)

    def test_interval_multiplication_uses_all_four_corners(self):
        self.assertEqual(
            CHECKER.interval_multiply(
                (Fraction(-1), Fraction(1)), (Fraction(-1), Fraction(1))
            ),
            (Fraction(-1), Fraction(1)),
        )
        self.assertEqual(
            CHECKER.interval_multiply(
                (Fraction(-1), Fraction(2)), (Fraction(-3), Fraction(4))
            ),
            (Fraction(-6), Fraction(8)),
        )

    def test_pauli_rotation_signs_and_global_commutation(self):
        self.assertEqual(CHECKER.anticommuting_branch("X", "Z"), (1, "Y"))
        self.assertEqual(CHECKER.anticommuting_branch("Z", "X"), (-1, "Y"))
        self.assertEqual(CHECKER.anticommuting_branch("XI", "ZZ"), (1, "YZ"))
        self.assertTrue(CHECKER.pauli_commutes("XX", "ZZ"))
        with self.assertRaises(CHECKER.SchemaError):
            CHECKER.anticommuting_branch("XX", "ZZ")

    def test_nontrivial_rotation_propagates_cosine_and_signed_sine_intervals(self):
        sine, cosine = CHECKER.taylor_sin_cos_interval(Fraction(1, 2), 1)
        result = CHECKER._propagate_gate(
            {"Z": (Fraction(1), Fraction(1))}, "X", sine, cosine, 8
        )
        self.assertEqual(result, {"Z": cosine, "Y": sine})
        negative_sine, negative_cosine = CHECKER.taylor_sin_cos_interval(
            Fraction(-1, 2), 1
        )
        negative = CHECKER._propagate_gate(
            {"Z": (Fraction(1), Fraction(1))},
            "X",
            negative_sine,
            negative_cosine,
            8,
        )
        self.assertEqual(negative["Z"], cosine)
        self.assertEqual(negative["Y"], (-sine[1], -sine[0]))

    def test_computational_basis_expectations_are_recomputed(self):
        self.assertEqual(
            CHECKER.computational_basis_pauli_expectation("ZI", "10"), -1
        )
        self.assertEqual(
            CHECKER.computational_basis_pauli_expectation("IZ", "01"), -1
        )
        self.assertEqual(
            CHECKER.computational_basis_pauli_expectation("XI", "00"), 0
        )

    def test_initial_duplicates_must_be_merged_before_propagation(self):
        bad = copy.deepcopy(self.certificate)
        bad["initial_merged_terms"][1]["coefficient_interval"] = {
            "lower": "1/2",
            "upper": "1/2",
        }
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertTrue(any("initial_merged_terms" in error for error in result["errors"]))

    def test_dropped_l1_uses_interval_upper_absolute_value_not_midpoint(self):
        self.assertEqual(
            CHECKER.interval_abs_upper((Fraction(-3, 5), Fraction(3, 5))),
            Fraction(3, 5),
        )
        bad = copy.deepcopy(self.certificate)
        bad["backprop_slices"][0]["claimed_dropped_l1_increment"] = "0/1"
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertTrue(any("ledger mismatch" in error for error in result["errors"]))

    def test_generator_sequence_tamper_is_detected_even_with_rehash(self):
        bad = copy.deepcopy(self.certificate)
        bad["backprop_slices"][0]["gates"][0]["pauli"] = "YI"
        bad["generator_sequence_sha256"] = CHECKER.canonical_generator_sequence_sha256(
            bad
        )
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertTrue(any("contract pin" in error for error in result["errors"]))

    def test_initial_observable_tamper_is_detected_even_with_rehash(self):
        contract = copy.deepcopy(self.contract)
        bad = copy.deepcopy(self.certificate)
        bad["initial_terms"][0]["coefficient"] = "1/9"
        bad["initial_terms_sha256"] = CHECKER.canonical_initial_terms_sha256(bad)
        result = self.verify(contract=contract, certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertTrue(any("contract pin" in error for error in result["errors"]))

    def test_basis_bitstring_is_contract_pinned(self):
        bad = copy.deepcopy(self.certificate)
        bad["computational_basis_bits"] = "10"
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertTrue(any("bitstring" in error for error in result["errors"]))

        contract = copy.deepcopy(self.contract)
        certificate = copy.deepcopy(self.certificate)
        contract["expected_computational_basis_bits"] = "11"
        certificate["computational_basis_bits"] = "11"
        certificate["claimed_final_retained_expectation_interval"] = {
            "lower": "-1/1",
            "upper": "-1/1",
        }
        result = self.verify(contract=contract, certificate=certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")

    def test_scope_overclaim_is_invalid_schema(self):
        bad = copy.deepcopy(self.certificate)
        bad["scope_claims"]["ready_gate_eligible"] = True
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")

    def test_bool_schema_and_contract_policy_drift_are_invalid(self):
        bad = copy.deepcopy(self.contract)
        bad["schema_version"] = True
        self.assertTrue(CHECKER.validate_contract(bad))
        bad = copy.deepcopy(self.contract)
        bad["workload_identity"]["reference_target"] = "ideal_exact_time_evolution"
        self.assertTrue(CHECKER.validate_contract(bad))
        bad = copy.deepcopy(self.contract)
        bad["checker_source_sha256"] = "0" * 64
        self.assertTrue(CHECKER.validate_contract(bad))
        bad = copy.deepcopy(self.contract)
        bad["n_qubits"] = 1
        bad["expected_computational_basis_bits"] = "0"
        self.assertTrue(CHECKER.validate_contract(bad))

    def test_failed_results_never_emit_positive_scope_claims(self):
        bad = copy.deepcopy(self.certificate)
        bad["claimed_final_retained_expectation_interval"] = {
            "lower": "0/1",
            "upper": "0/1",
        }
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertFalse(result["verified"])
        self.assertFalse(
            result["scope_claims"]["declared_pauli_sequence_arithmetic_verified"]
        )
        self.assertFalse(
            result["scope_claims"]["declared_sequence_truncation_l1_verified"]
        )

    def test_noncanonical_or_out_of_domain_gate_angle_fails_closed(self):
        for theta in ("2/2", "2/1"):
            with self.subTest(theta=theta):
                contract = copy.deepcopy(self.contract)
                bad = copy.deepcopy(self.certificate)
                bad["backprop_slices"][0]["gates"][0]["theta"] = theta
                self.repin_sequence(contract, bad)
                result = self.verify(contract=contract, certificate=bad)
                self.assertEqual(result["status"], "INVALID_SCHEMA")

    def test_absent_drop_and_claimed_expansion_drift_fail(self):
        bad = copy.deepcopy(self.certificate)
        bad["backprop_slices"][0]["dropped_strings"] = ["II"]
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertTrue(any("absent" in error for error in result["errors"]))

        bad = copy.deepcopy(self.certificate)
        bad["backprop_slices"][0]["claimed_post_merge_terms"][0][
            "coefficient_interval"
        ]["upper"] = "1/9"
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertTrue(any("post-merge" in error for error in result["errors"]))

    def test_final_expectation_claim_cannot_be_self_declared(self):
        bad = copy.deepcopy(self.certificate)
        bad["claimed_final_retained_expectation_interval"] = {
            "lower": "0/1",
            "upper": "0/1",
        }
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertTrue(any("expectation interval" in error for error in result["errors"]))

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_constants(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            duplicate = pathlib.Path(temporary_directory) / "duplicate.json"
            duplicate.write_text('{"x":1,"x":2}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                CHECKER.load_strict_json(duplicate)
            nonfinite = pathlib.Path(temporary_directory) / "nonfinite.json"
            nonfinite.write_text('{"x":NaN}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-finite"):
                CHECKER.load_strict_json(nonfinite)

            oversized = pathlib.Path(temporary_directory) / "oversized.json"
            oversized.write_bytes(b"{" + b" " * 64 + b"}")
            with self.assertRaisesRegex(ValueError, "exceeds byte cap"):
                CHECKER.load_strict_json(oversized, 8)
        zero_device = pathlib.Path("/dev/zero")
        if zero_device.exists():
            with self.assertRaisesRegex(ValueError, "exceeds byte cap"):
                CHECKER.load_strict_json(zero_device, 8)

    def test_public_api_nonfinite_gate_fails_closed(self):
        bad = copy.deepcopy(self.certificate)
        bad["backprop_slices"][0]["gates"][0]["theta"] = float("nan")
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["verified"])

    def test_resource_caps_fail_closed(self):
        contract = copy.deepcopy(self.contract)
        bad = copy.deepcopy(self.certificate)
        bad["backprop_slices"][0]["gates"][0]["taylor_order"] = 33
        result = self.verify(contract=contract, certificate=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        with self.assertRaises(CHECKER.SchemaError):
            CHECKER.taylor_sin_cos_interval(Fraction(1, 2), 33)

        contract = copy.deepcopy(self.contract)
        contract["resource_limits"]["max_taylor_order"] = 1000000
        result = self.verify(contract=contract)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("hard checker caps" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
