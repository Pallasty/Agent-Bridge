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
    "hubbard_strang_grouping_screen", "hubbard_strang_grouping_screen.py"
)


class HubbardStrangGroupingScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = CHECKER.load_strict_json(
            HERE / "hubbard_strang_grouping_screen_contract.json"
        )
        cls.certificate = CHECKER.load_strict_json(
            HERE / "hubbard_strang_grouping_screen_template.json"
        )
        # The expensive 144-order exact screen runs once in the positive public API.
        cls.positive = CHECKER.verify_certificate(cls.contract, cls.certificate)
        cls.screen = cls.positive["recomputed_screen"]

    def internal_verify(self, contract=None, certificate=None):
        with mock.patch.object(CHECKER, "grouping_screen", return_value=self.screen):
            return CHECKER._verify_certificate_impl(
                self.contract if contract is None else contract,
                self.certificate if certificate is None else certificate,
            )

    def test_01_positive_status_is_narrow(self):
        self.assertEqual(
            self.positive["status"],
            "VERIFIED_STRANG_GROUPING_COEFFICIENT_L1_SCREEN",
        )
        self.assertTrue(self.positive["verified"])
        self.assertFalse(self.positive["ready_gate_eligible"])

    def test_02_positive_scope_does_not_overclaim(self):
        scope = self.positive["scope_claims"]
        self.assertFalse(scope["paper_periodic_plaquette_numerical_bound_imported"])
        self.assertFalse(scope["candidate_group_exponentials_matched_to_benchmark_circuit"])
        self.assertEqual(scope["observable_specific_or_locality_tightening"], "NOT_ASSESSED")
        self.assertFalse(scope["reference_error_budget_qualified"])

    def test_03_contract_source_hash_matches(self):
        self.assertEqual(
            self.contract["checker_source_sha256"],
            hashlib.sha256((HERE / "hubbard_strang_grouping_screen.py").read_bytes()).hexdigest(),
        )

    def test_04_contract_screen_digest_matches(self):
        self.assertEqual(
            self.contract["expected_screen_sha256"],
            CHECKER.canonical_sha256(self.screen),
        )

    def test_05_all_fixed_orders_are_screened(self):
        fixed = self.screen["fixed_five_group_screen"]
        self.assertEqual(fixed["permutation_count"], 120)
        self.assertRegex(fixed["all_order_records_sha256"], r"^[0-9a-f]{64}$")

    def test_06_declared_order_reproduces_base_result(self):
        fixed = self.screen["fixed_five_group_screen"]["fixed_declared_order"]
        self.assertEqual(fixed["order"], ["H1", "H2", "HU", "H3", "H4"])
        self.assertEqual(fixed["coefficient_C"], "7076/3")
        self.assertEqual(fixed["generic_norm_one_observable_R100_bound"], "1769/3750")
        self.assertEqual(fixed["minimum_R_for_allocation"], 4344)

    def test_07_fixed_best_order_and_value(self):
        fixed = self.screen["fixed_five_group_screen"]
        self.assertEqual(fixed["best_order_count"], 2)
        self.assertEqual(fixed["best_orders"][0]["order"], ["H1", "H2", "HU", "H4", "H3"])
        self.assertTrue(all(item["coefficient_C"] == "7072/3" for item in fixed["best_orders"]))
        self.assertTrue(all(item["generic_norm_one_observable_R100_bound"] == "884/1875" for item in fixed["best_orders"]))

    def test_08_fixed_order_improvement_is_not_material(self):
        fixed = self.screen["fixed_five_group_screen"]
        self.assertEqual(fixed["relative_C_reduction_from_declared_to_best"], "1/1769")
        self.assertFalse(fixed["material_relative_C_reduction_threshold_satisfied"])
        self.assertFalse(fixed["best_meets_R100_allocation"])

    def test_09_declared_order_rank_is_deterministic(self):
        self.assertEqual(self.screen["fixed_five_group_screen"]["fixed_declared_order_rank"], 4)

    def test_10_all_plaquette_orders_are_screened(self):
        candidate = self.screen["OBC_plaquette_boundary_screen"]
        self.assertEqual(candidate["permutation_count"], 24)
        self.assertRegex(candidate["all_order_records_sha256"], r"^[0-9a-f]{64}$")

    def test_11_plaquette_candidate_covers_exact_OBC_bond_count(self):
        structure = self.screen["OBC_plaquette_boundary_screen"]["structure"]
        self.assertEqual(structure["spatial_bond_counts"], {"P0": 64, "P1": 36, "B": 12})
        self.assertEqual(sum(structure["spatial_bond_counts"].values()), 112)
        self.assertTrue(structure["hamiltonian_equality_verified"])

    def test_12_plaquette_candidate_term_counts_sum_to_640(self):
        counts = self.screen["OBC_plaquette_boundary_screen"]["structure"]["pauli_term_counts"]
        self.assertEqual(counts, {"P0": 256, "P1": 144, "B": 48, "HU": 192})
        self.assertEqual(sum(counts.values()), 640)

    def test_13_bulk_plaquettes_are_disjoint_by_anchor_family(self):
        structure = self.screen["OBC_plaquette_boundary_screen"]["structure"]
        self.assertEqual(structure["P0_disjoint_plaquette_count"], 16)
        self.assertEqual(structure["P1_disjoint_plaquette_count"], 9)
        self.assertEqual(structure["boundary_residual_disjoint_bond_count"], 12)

    def test_14_bulk_group_edges_do_not_all_commute(self):
        structure = self.screen["OBC_plaquette_boundary_screen"]["structure"]
        self.assertEqual(
            structure["group_internal_pairwise_commutation"],
            {"P0": False, "P1": False, "B": True, "HU": True},
        )
        self.assertTrue(structure["bulk_group_exponentials_require_noncommuting_plaquette_cluster_evolution"])

    def test_15_plaquette_best_is_worse_than_declared_coefficient_L1(self):
        candidate = self.screen["OBC_plaquette_boundary_screen"]
        self.assertEqual(candidate["best_order_count"], 3)
        self.assertTrue(all(item["coefficient_C"] == "7232/3" for item in candidate["best_orders"]))
        self.assertGreater(Fraction("7232/3"), Fraction("7076/3"))
        self.assertFalse(candidate["best_meets_R100_allocation"])

    def test_16_plaquette_best_bound_and_minimum_R(self):
        best = self.screen["OBC_plaquette_boundary_screen"]["best_orders"]
        self.assertTrue(all(item["generic_norm_one_observable_R100_bound"] == "904/1875" for item in best))
        self.assertTrue(all(item["minimum_R_for_allocation"] == 4392 for item in best))

    def test_17_plaquette_candidate_is_not_benchmark_circuit(self):
        self.assertFalse(
            self.screen["OBC_plaquette_boundary_screen"]["matches_declared_individual_term_benchmark_circuit"]
        )

    def test_18_R100_allocation_implies_exact_C_ceiling(self):
        self.assertEqual(self.screen["allocation_coefficient_C_ceiling"], "5/4")
        self.assertGreater(Fraction("7072/3"), Fraction("5/4"))

    def test_19_decision_routes_to_norm_tightening(self):
        decision = self.screen["decision"]
        self.assertFalse(decision["permutation_materially_improves_fixed_coefficient_L1_bound"])
        self.assertFalse(decision["OBC_plaquette_regrouping_improves_fixed_declared_coefficient_L1_bound"])
        self.assertFalse(decision["coefficient_L1_grouping_search_qualifies_reference_at_R100"])
        self.assertEqual(
            decision["next_required_tightening"],
            "observable_or_locality_specific_norm_or_certified_cluster_spectral_norm",
        )

    def test_20_primary_source_scope_is_explicit(self):
        source = self.contract["primary_source"]
        self.assertEqual(source["formula"], "Proposition 2 Equation 13")
        self.assertEqual(source["plaquette_decomposition"], "Section III.B Equation 19")
        self.assertIn("periodic", source["source_scope"])
        self.assertIn("not used", source["use_in_this_checker"])

    def test_21_every_base_dependency_is_source_pinned(self):
        for pin in self.contract["source_pins"]:
            self.assertEqual(
                hashlib.sha256((HERE / pin["relative_path"]).read_bytes()).hexdigest(),
                pin["sha256"],
            )

    def test_22_internal_contract_validation_succeeds(self):
        with mock.patch.object(CHECKER, "grouping_screen", return_value=self.screen):
            self.assertEqual(CHECKER._validate_contract_impl(self.contract), [])

    def test_23_bad_checker_pin_is_invalid_schema(self):
        bad = copy.deepcopy(self.contract)
        bad["checker_source_sha256"] = "0" * 64
        with mock.patch.object(CHECKER, "grouping_screen", return_value=self.screen):
            self.assertTrue(CHECKER._validate_contract_impl(bad))

    def test_24_bad_screen_digest_is_invalid_schema(self):
        bad = copy.deepcopy(self.contract)
        bad["expected_screen_sha256"] = "0" * 64
        with mock.patch.object(CHECKER, "grouping_screen", return_value=self.screen):
            self.assertTrue(CHECKER._validate_contract_impl(bad))

    def test_25_certificate_extra_key_is_invalid_schema(self):
        bad = copy.deepcopy(self.certificate)
        bad["unexpected"] = None
        self.assertEqual(self.internal_verify(certificate=bad)["status"], "INVALID_SCHEMA")

    def test_26_float_schema_version_is_invalid_schema(self):
        bad = copy.deepcopy(self.certificate)
        bad["schema_version"] = 1.0
        self.assertEqual(self.internal_verify(certificate=bad)["status"], "INVALID_SCHEMA")

    def test_27_scope_overclaim_is_invalid_schema(self):
        bad = copy.deepcopy(self.certificate)
        bad["scope_claims"]["ready_gate_eligible"] = True
        self.assertEqual(self.internal_verify(certificate=bad)["status"], "INVALID_SCHEMA")

    def test_28_well_shaped_best_value_tamper_is_verification_failed(self):
        bad = copy.deepcopy(self.certificate)
        bad["screen_claim"]["fixed_five_group_screen"]["best_orders"][0]["coefficient_C"] = "1/1"
        result = self.internal_verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertFalse(result["scope_claims"]["fixed_five_group_all_120_orders_exactly_screened"])

    def test_29_well_shaped_digest_tamper_is_verification_failed(self):
        bad = copy.deepcopy(self.certificate)
        bad["screen_claim"]["OBC_plaquette_boundary_screen"]["all_order_records_sha256"] = "0" * 64
        self.assertEqual(self.internal_verify(certificate=bad)["status"], "VERIFICATION_FAILED")

    def test_30_duplicate_JSON_key_is_rejected(self):
        with self.assertRaisesRegex(CHECKER.SchemaError, "duplicate JSON key"):
            CHECKER._strict_json_bytes(b'{"a":1,"a":2}', "probe")

    def test_31_nonfinite_JSON_constant_is_rejected(self):
        with self.assertRaisesRegex(CHECKER.SchemaError, "strict JSON"):
            CHECKER._strict_json_bytes(b'{"a":NaN}', "probe")

    def test_32_JSON_byte_cap_is_rejected(self):
        with mock.patch.dict(CHECKER.RESOURCE_LIMITS, {"max_json_bytes": 3}):
            with self.assertRaisesRegex(CHECKER.SchemaError, "byte cap"):
                CHECKER._strict_json_bytes(b'{"a":1}', "probe")

    def test_33_checker_source_OSError_fails_closed(self):
        with mock.patch.object(CHECKER, "_read_checker_source_bytes", side_effect=OSError("gone")):
            result = CHECKER.verify_certificate(self.contract, self.certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["ready_gate_eligible"])

    def test_34_source_pin_mismatch_is_rejected_before_exec(self):
        with mock.patch.object(CHECKER, "_read_checker_source_bytes", return_value=b"drift"), mock.patch.object(
            CHECKER.types, "ModuleType", side_effect=AssertionError("must not execute")
        ) as constructor:
            result = CHECKER.verify_certificate(self.contract, self.certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertIn("before compile/exec", result["errors"][0])
        constructor.assert_not_called()

    def test_35_loaded_impl_monkeypatch_cannot_bypass_source_preflight(self):
        with mock.patch.object(CHECKER, "_verify_certificate_impl", return_value={"status": "FORGED"}), mock.patch.object(
            CHECKER, "_read_checker_source_bytes", return_value=b"not pinned"
        ):
            result = CHECKER.verify_certificate(self.contract, self.certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertNotEqual(result["status"], "FORGED")

    def test_36_failure_clears_every_positive_scope(self):
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

    def test_38_strict_loader_rejects_duplicate_file_keys(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as handle:
            handle.write('{"a":1,"a":2}')
            path = pathlib.Path(handle.name)
        try:
            with self.assertRaises(CHECKER.SchemaError):
                CHECKER.load_strict_json(path)
        finally:
            path.unlink()

    def test_39_every_candidate_stays_below_pair_product_cap(self):
        cap = self.contract["resource_limits"]["max_commutator_pair_products_per_candidate"]
        self.assertEqual(
            self.screen["fixed_five_group_screen"]["maximum_candidate_commutator_pair_products"],
            887808,
        )
        self.assertEqual(
            self.screen["OBC_plaquette_boundary_screen"]["maximum_candidate_commutator_pair_products"],
            955136,
        )
        self.assertLess(955136, cap)


if __name__ == "__main__":
    unittest.main()
