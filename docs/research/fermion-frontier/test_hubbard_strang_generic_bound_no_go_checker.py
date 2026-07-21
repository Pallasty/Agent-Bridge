import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import pathlib
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
    "hubbard_strang_generic_bound_no_go_checker",
    "hubbard_strang_generic_bound_no_go_checker.py",
)


class HubbardStrangGenericBoundNoGoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = CHECKER.load_strict_json(
            HERE / "hubbard_strang_generic_bound_no_go_contract.json"
        )
        cls.certificate = CHECKER.load_strict_json(
            HERE / "hubbard_strang_generic_bound_no_go_template.json"
        )
        cls.positive = CHECKER.verify_certificate(cls.contract, cls.certificate)
        cls.witness = cls.positive["recomputed_witness"]

    def internal_verify(self, contract=None, certificate=None):
        with mock.patch.object(CHECKER, "recompute_witness", return_value=self.witness):
            return CHECKER._verify_certificate_impl(
                self.contract if contract is None else contract,
                self.certificate if certificate is None else certificate,
            )

    def test_01_positive_status_is_narrow(self):
        self.assertEqual(
            self.positive["status"],
            "VERIFIED_GENERIC_STRANG_BOUND_INFEASIBILITY_WITNESS",
        )
        self.assertTrue(self.positive["verified"])
        self.assertFalse(self.positive["ready_gate_eligible"])

    def test_02_scope_does_not_claim_actual_error_no_go(self):
        scope = self.positive["scope_claims"]
        self.assertFalse(scope["actual_product_formula_error_lower_bounded"])
        self.assertEqual(scope["observable_specific_or_locality_tightening"], "NOT_ASSESSED")
        self.assertEqual(scope["alternative_grouping_or_higher_order_formula"], "NOT_ASSESSED")
        self.assertFalse(scope["physical_reference_qualified"])

    def test_03_source_hash_matches_contract(self):
        self.assertEqual(
            self.contract["checker_source_sha256"],
            hashlib.sha256(
                (HERE / "hubbard_strang_generic_bound_no_go_checker.py").read_bytes()
            ).hexdigest(),
        )

    def test_04_witness_digest_matches_contract(self):
        self.assertEqual(
            self.contract["expected_witness_sha256"],
            CHECKER.canonical_sha256(self.witness),
        )

    def test_05_every_base_dependency_is_pinned(self):
        for pin in self.contract["source_pins"]:
            self.assertEqual(
                hashlib.sha256((HERE / pin["relative_path"]).read_bytes()).hexdigest(),
                pin["sha256"],
            )

    def test_06_selected_operator_identity(self):
        selected = self.witness["selected_operator"]
        self.assertEqual(selected["group"], "H1")
        self.assertEqual(selected["tail_groups"], ["H2", "HU", "H3", "H4"])
        self.assertEqual(selected["theorem_weight"], "1/12")

    def test_07_selected_operator_term_counts(self):
        selected = self.witness["selected_operator"]
        self.assertEqual(selected["inner_term_count"], 448)
        self.assertEqual(selected["nested_term_count"], 3072)
        self.assertEqual(selected["commutator_pair_products"], 294912)

    def test_08_selected_operator_digest(self):
        self.assertEqual(
            self.witness["selected_operator"]["nested_expansion_sha256"],
            "3904aeaf044dd8180daa7b4c91a7ac6473e830f2fbf3dcc26c0e1480c19c0224",
        )

    def test_09_neel_witness_hex_and_bit_length(self):
        witness = self.witness["normalized_basis_witness"]
        self.assertEqual(witness["basis_integer_hex"], "0x66669999666699996666999966669999")
        self.assertEqual(len(witness["bits_q0_first"]), 128)
        self.assertEqual(witness["normalization_squared"], "1/1")

    def test_10_neel_witness_is_half_filled_zero_spin(self):
        witness = self.witness["normalized_basis_witness"]
        self.assertEqual(witness["particle_count"], 64)
        self.assertEqual(witness["spin_up_particle_count"], 32)
        self.assertEqual(witness["spin_down_particle_count"], 32)
        self.assertTrue(witness["matches_half_filled_zero_spin_sector"])

    def test_11_exact_action_output_count_and_digest(self):
        action = self.witness["exact_action"]
        self.assertEqual(action["nonzero_output_count"], 416)
        self.assertEqual(
            action["action_records_sha256"],
            "7790cb0a068f03ef3c284174c9b36504857ff9da3de7416f94d3eaec226122d1",
        )

    def test_12_exact_action_remains_in_sector(self):
        self.assertTrue(
            self.witness["exact_action"]["all_outputs_remain_in_N_up32_N_down32_sector"]
        )

    def test_13_exact_action_amplitude_histogram(self):
        self.assertEqual(
            self.witness["exact_action"]["real_amplitude_histogram"],
            {
                "-66/1": 16,
                "-65/1": 16,
                "-8/1": 160,
                "-2/1": 16,
                "2/1": 16,
                "8/1": 160,
                "65/1": 16,
                "66/1": 16,
            },
        )

    def test_14_action_norm_squared_is_exact(self):
        self.assertEqual(self.witness["exact_action"]["action_norm_squared"], "295200/1")
        self.assertEqual(Fraction("295200/1"), 3600 * 82)

    def test_15_selected_contribution_lower_squared(self):
        proof = self.witness["infeasibility_proof"]
        self.assertEqual(proof["selected_single_contribution_lower_bound_squared"], "2050/1")
        self.assertEqual(Fraction("295200/1") / 144, Fraction("2050/1"))

    def test_16_R100_coefficient_ceiling(self):
        proof = self.witness["infeasibility_proof"]
        self.assertEqual(proof["required_total_coefficient_C_ceiling"], "5/4")
        self.assertEqual(proof["required_total_coefficient_C_ceiling_squared"], "25/16")

    def test_17_single_positive_term_exceeds_total_ceiling(self):
        proof = self.witness["infeasibility_proof"]
        self.assertGreater(Fraction("2050/1"), Fraction("25/16"))
        self.assertTrue(proof["selected_contribution_strictly_exceeds_total_ceiling"])

    def test_18_generic_bound_squared_lower_bound(self):
        proof = self.witness["infeasibility_proof"]
        self.assertEqual(proof["R100_generic_bound_lower_bound_squared"], "41/500000")
        self.assertEqual(Fraction("2050/1") * Fraction(4, 10000**2), Fraction("41/500000"))

    def test_19_allocation_squared_and_margin(self):
        proof = self.witness["infeasibility_proof"]
        self.assertEqual(proof["allocation_squared"], "1/16000000")
        self.assertEqual(proof["squared_margin_ratio"], "1312/1")
        self.assertEqual(Fraction("41/500000") / Fraction("1/16000000"), 1312)

    def test_20_R601_is_ruled_out_and_R602_not_ruled_out(self):
        proof = self.witness["infeasibility_proof"]
        threshold = proof["necessary_R_fourth_power_threshold"]
        self.assertEqual(threshold, 131200000000)
        self.assertLess(proof["R601_fourth_power"], threshold)
        self.assertGreaterEqual(proof["R602_fourth_power"], threshold)
        self.assertEqual(proof["minimum_R_not_ruled_out_by_single_witness"], 602)

    def test_21_exact_global_spectral_norm_cannot_rescue_bound(self):
        proof = self.witness["infeasibility_proof"]
        self.assertTrue(proof["globally_exact_cluster_spectral_norm_cannot_change_decision"])
        self.assertTrue(proof["sector_restricted_exact_spectral_norm_cannot_change_decision"])
        self.assertTrue(proof["fixed_generic_bound_cannot_qualify_at_R100"])

    def test_22_decision_routes_away_from_fixed_generic_cluster_norm(self):
        decision = self.witness["decision"]
        self.assertFalse(decision["continue_fixed_generic_cluster_spectral_tightening"])
        self.assertIn("observable_locality_specific", decision["next_required_route"])

    def test_23_upstream_context_is_pinned_but_not_imported(self):
        context = self.contract["upstream_cluster_context"]
        self.assertEqual(
            context["paper_time_commit"],
            "859bef092675957ae126e9d3b09dc3c63b213859",
        )
        self.assertEqual(context["maximum_dense_Fock_modes_in_upstream_code"], 14)
        self.assertFalse(context["executed_or_imported_by_this_checker"])
        self.assertIn("without_directed_rounding", context["upstream_spectral_numerics"])

    def test_24_internal_contract_validation_succeeds(self):
        with mock.patch.object(CHECKER, "recompute_witness", return_value=self.witness):
            self.assertEqual(CHECKER._validate_contract_impl(self.contract), [])

    def test_25_bad_checker_source_pin_is_invalid(self):
        bad = copy.deepcopy(self.contract)
        bad["checker_source_sha256"] = "0" * 64
        with mock.patch.object(CHECKER, "recompute_witness", return_value=self.witness):
            self.assertTrue(CHECKER._validate_contract_impl(bad))

    def test_26_bad_witness_digest_is_invalid(self):
        bad = copy.deepcopy(self.contract)
        bad["expected_witness_sha256"] = "0" * 64
        with mock.patch.object(CHECKER, "recompute_witness", return_value=self.witness):
            self.assertTrue(CHECKER._validate_contract_impl(bad))

    def test_27_certificate_extra_key_is_invalid_schema(self):
        bad = copy.deepcopy(self.certificate)
        bad["unexpected"] = None
        self.assertEqual(self.internal_verify(certificate=bad)["status"], "INVALID_SCHEMA")

    def test_28_float_schema_version_is_invalid_schema(self):
        bad = copy.deepcopy(self.certificate)
        bad["schema_version"] = 1.0
        self.assertEqual(self.internal_verify(certificate=bad)["status"], "INVALID_SCHEMA")

    def test_29_scope_overclaim_is_invalid_schema(self):
        bad = copy.deepcopy(self.certificate)
        bad["scope_claims"]["ready_gate_eligible"] = True
        self.assertEqual(self.internal_verify(certificate=bad)["status"], "INVALID_SCHEMA")

    def test_30_well_shaped_norm_tamper_is_verification_failed(self):
        bad = copy.deepcopy(self.certificate)
        bad["witness_claim"]["exact_action"]["action_norm_squared"] = "1/1"
        result = self.internal_verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertFalse(result["scope_claims"]["spectral_norm_lower_bound_from_basis_action_verified"])

    def test_31_well_shaped_digest_tamper_is_verification_failed(self):
        bad = copy.deepcopy(self.certificate)
        bad["witness_claim"]["exact_action"]["action_records_sha256"] = "0" * 64
        self.assertEqual(self.internal_verify(certificate=bad)["status"], "VERIFICATION_FAILED")

    def test_32_duplicate_JSON_key_is_rejected(self):
        with self.assertRaisesRegex(CHECKER.SchemaError, "duplicate JSON key"):
            CHECKER._strict_json_bytes(b'{"a":1,"a":2}', "probe")

    def test_33_nonfinite_JSON_is_rejected(self):
        with self.assertRaisesRegex(CHECKER.SchemaError, "non-finite"):
            CHECKER._strict_json_bytes(b'{"a":NaN}', "probe")

    def test_34_checker_source_OSError_fails_closed(self):
        with mock.patch.object(CHECKER, "_read_checker_source_bytes", side_effect=OSError("gone")):
            result = CHECKER.verify_certificate(self.contract, self.certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["ready_gate_eligible"])

    def test_35_source_mismatch_is_rejected_before_exec(self):
        with mock.patch.object(CHECKER, "_read_checker_source_bytes", return_value=b"drift"), mock.patch.object(
            CHECKER.types, "ModuleType", side_effect=AssertionError("must not execute")
        ) as constructor:
            result = CHECKER.verify_certificate(self.contract, self.certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertIn("before compile/exec", result["errors"][0])
        constructor.assert_not_called()

    def test_36_failure_clears_all_positive_scopes(self):
        bad = copy.deepcopy(self.certificate)
        bad["schema_version"] = 2
        result = self.internal_verify(certificate=bad)
        for key, expected in CHECKER.SCOPE_CLAIMS.items():
            if expected is True:
                self.assertFalse(result["scope_claims"][key])

    def test_37_cli_always_returns_one(self):
        fake = {"status": CHECKER.MAXIMUM_POSITIVE_STATUS, "verified": True, "ready_gate_eligible": False}
        stdout = io.StringIO()
        with mock.patch.object(CHECKER, "load_strict_json", return_value={}), mock.patch.object(
            CHECKER, "verify_certificate", return_value=fake
        ), contextlib.redirect_stdout(stdout):
            self.assertEqual(CHECKER.main(["contract.json", "certificate.json"]), 1)
        self.assertFalse(json.loads(stdout.getvalue())["ready_gate_eligible"])

    def test_38_loader_rejects_duplicate_file_keys(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as handle:
            handle.write('{"a":1,"a":2}')
            path = pathlib.Path(handle.name)
        try:
            with self.assertRaises(CHECKER.SchemaError):
                CHECKER.load_strict_json(path)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
