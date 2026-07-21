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
    "hubbard_d3_double_occupancy_cluster_no_go_checker",
    "hubbard_d3_double_occupancy_cluster_no_go_checker.py",
)


class HubbardD3DoubleOccupancyClusterNoGoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = CHECKER.load_strict_json(
            HERE / "hubbard_d3_double_occupancy_cluster_no_go_contract.json"
        )
        cls.certificate = CHECKER.load_strict_json(
            HERE / "hubbard_d3_double_occupancy_cluster_no_go_template.json"
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
            "VERIFIED_D3_DOUBLE_OCCUPANCY_CLUSTER_UNIFORM_SUP_NO_GO",
        )
        self.assertTrue(self.positive["verified"])
        self.assertFalse(self.positive["ready_gate_eligible"])

    def test_02_scope_does_not_claim_global_D3_or_actual_error_no_go(self):
        scope = self.positive["scope_claims"]
        self.assertFalse(scope["global_D3_norm_lower_bounded_by_cluster_sum"])
        self.assertFalse(scope["actual_R100_product_formula_error_lower_bounded"])
        self.assertEqual(scope["cross_cluster_cancellation"], "NOT_ASSESSED")
        self.assertEqual(
            scope["per_step_evolved_cluster_triangle_ledger"],
            "NOT_ASSESSED_STILL_OPEN",
        )
        self.assertFalse(scope["physical_reference_qualified"])

    def test_03_checker_source_hash_matches_contract(self):
        self.assertEqual(
            self.contract["checker_source_sha256"],
            hashlib.sha256(
                (HERE / "hubbard_d3_double_occupancy_cluster_no_go_checker.py").read_bytes()
            ).hexdigest(),
        )

    def test_04_every_local_dependency_is_hash_pinned(self):
        for pin in self.contract["source_pins"]:
            self.assertEqual(
                hashlib.sha256((HERE / pin["relative_path"]).read_bytes()).hexdigest(),
                pin["sha256"],
            )

    def test_05_witness_digest_matches_contract(self):
        self.assertEqual(
            CHECKER.canonical_sha256(self.witness),
            self.contract["expected_witness_sha256"],
        )

    def test_06_fixture_raw_hash_and_schema_are_recomputed(self):
        sources = CHECKER._read_pinned_sources()
        terms = CHECKER._validated_fixture(
            sources["hubbard_d3_double_occupancy_symbolic_terms.b85"]
        )
        self.assertEqual(len(terms), 2748)
        self.assertEqual(self.contract["fixture_raw_sha256"], CHECKER.FIXTURE_RAW_SHA256)

    def test_07_exact_D3_identity_counts(self):
        identity = self.witness["D3_identity"]
        self.assertEqual(identity["fixture_symbolic_term_count"], 2748)
        self.assertEqual(identity["fixture_expanded_field_term_count"], 18544)
        self.assertEqual(identity["exact_Pauli_term_count"], 8928)
        self.assertEqual(identity["exact_Pauli_coefficient_L1"], "423/16")

    def test_08_fixture_JW_equals_direct_Pauli_D3(self):
        identity = self.witness["D3_identity"]
        self.assertTrue(identity["physical_fermion_fixture_JW_equals_exact_Pauli_D3"])
        self.assertEqual(
            identity["fixture_JW_expansion_sha256"],
            identity["exact_Pauli_expansion_sha256"],
        )
        self.assertEqual(identity["exact_Pauli_expansion_sha256"], CHECKER.DIRECT_D3_SHA256)
        self.assertEqual(identity["fixture_support_mode_count"], 128)
        self.assertEqual(identity["fixture_support_component_count"], 1)

    def test_09_partition_has_43_clusters_and_preserves_all_terms(self):
        partition = self.witness["greedy_partition"]
        self.assertEqual(partition["cluster_count"], 43)
        self.assertEqual(sum(partition["cluster_symbolic_term_counts"]), 2748)
        self.assertEqual(len(partition["cluster_support_mode_counts"]), 43)

    def test_10_every_cluster_obeys_14_mode_cap(self):
        counts = self.witness["greedy_partition"]["cluster_support_mode_counts"]
        self.assertLessEqual(max(counts), 14)
        self.assertEqual(counts.count(14), 39)

    def test_11_partition_digest_is_fixed(self):
        self.assertEqual(
            self.witness["greedy_partition"]["partition_term_indices_sha256"],
            "ec09434b09490551df2cb917aa8eb6e5306aca99e93e050643e46c890f250be8",
        )

    def test_12_first_cluster_identity(self):
        first = self.witness["greedy_partition"]["first_30_cluster_witnesses"][0]
        self.assertEqual(first["symbolic_term_count"], 120)
        self.assertEqual(first["field_term_count"], 868)
        self.assertEqual(first["support_global_modes"], list(range(106, 112)) + list(range(120, 128)))
        self.assertEqual(first["maximum_absolute_matrix_element_lower_bound"], "11/128")

    def test_13_all_witnesses_use_direct_global_Neel_state(self):
        records = self.witness["greedy_partition"]["first_30_cluster_witnesses"]
        for record in records:
            self.assertEqual(
                record["global_Neel_state_hex"],
                "0x66669999666699996666999966669999",
            )
            self.assertEqual(record["global_spin_up_particle_count"], 32)
            self.assertEqual(record["global_spin_down_particle_count"], 32)
            self.assertTrue(record["witness_is_direct_global_Nup32_Ndown32_basis_state"])

    def test_14_all_cluster_actions_remain_in_global_sector(self):
        records = self.witness["greedy_partition"]["first_30_cluster_witnesses"]
        self.assertTrue(all(item["all_outputs_preserve_global_spin_numbers"] for item in records))
        self.assertTrue(all(item["nonzero_action_output_count"] > 0 for item in records))
        self.assertTrue(
            all(item["field_transition_equals_exact_JW_Pauli_action"] for item in records)
        )

    def test_15_partial_lower_bound_recomputes_from_records(self):
        records = self.witness["greedy_partition"]["first_30_cluster_witnesses"]
        total = sum(
            (Fraction(item["maximum_absolute_matrix_element_lower_bound"]) for item in records),
            Fraction(0),
        )
        self.assertEqual(total, Fraction(1945, 768))
        self.assertEqual(records[-1]["cumulative_cluster_norm_lower_bound"], "1945/768")

    def test_16_partial_lower_bound_strictly_exceeds_ceiling(self):
        proof = self.witness["uniform_supremum_architecture_infeasibility_proof"]
        self.assertEqual(proof["required_uniform_supremum_D3_coefficient_ceiling"], "5/2")
        self.assertEqual(proof["k0_partial_sum_of_cluster_norm_lower_bounds"], "1945/768")
        self.assertEqual(proof["strict_margin_over_ceiling"], "25/768")
        self.assertGreater(Fraction("1945/768"), Fraction("5/2"))

    def test_17_R100_ceiling_derivation(self):
        self.assertEqual(Fraction(100**2, 4000), Fraction(5, 2))

    def test_18_exact_cluster_norm_uniform_supremum_is_ruled_out(self):
        proof = self.witness["uniform_supremum_architecture_infeasibility_proof"]
        self.assertTrue(proof["k0_partial_lower_bound_exceeds_uniform_ceiling"])
        self.assertTrue(
            proof["even_exact_norms_for_fixed_43_clusters_cannot_seed_uniform_supremum_certificate"]
        )
        self.assertFalse(proof["per_step_evolved_cluster_triangle_ledger_ruled_out"])
        self.assertEqual(proof["k0_leading_contribution_at_R100_from_partial_floor"], "389/153600000")

    def test_19_cluster_sum_is_not_misused_as_global_norm_lower_bound(self):
        proof = self.witness["uniform_supremum_architecture_infeasibility_proof"]
        self.assertFalse(proof["used_as_lower_bound_on_globally_merged_D3_norm"])

    def test_20_decision_routes_to_direct_propagation_or_cancellation(self):
        decision = self.witness["decision"]
        self.assertFalse(decision["use_fixed_greedy14_cluster_triangle_as_uniform_supremum_bound"])
        self.assertEqual(
            decision["continue_per_step_evolved_cluster_triangle_ledger"],
            "NOT_ASSESSED_STILL_OPEN",
        )
        self.assertIn("dropped_L1", decision["next_required_route"])
        self.assertIn("cancellation", decision["next_required_route"])

    def test_21_upstream_context_is_audited_but_not_executed(self):
        context = self.contract["upstream_context"]
        self.assertEqual(context["audited_commit"], "859bef092675957ae126e9d3b09dc3c63b213859")
        self.assertFalse(context["upstream_code_executed_or_imported_by_checker"])
        self.assertFalse(context["upstream_binary64_spectral_norm_imported"])
        self.assertFalse(
            context["fixture_decomposition_and_order_recomputed_from_upstream_source_by_checker"]
        )

    def test_22_resource_ledger_records_exact_work(self):
        usage = self.witness["resource_usage"]
        self.assertEqual(usage["commutator_pair_products"], 11807232)
        self.assertEqual(usage["peak_expansion_terms"], 30920)
        self.assertEqual(usage["field_term_count"], 18544)
        self.assertEqual(usage["cluster_action_witness_count"], 30)
        self.assertEqual(usage["cluster_exact_JW_action_cross_check_count"], 30)

    def test_23_internal_contract_validation_succeeds(self):
        self.assertEqual(CHECKER._validate_contract_impl(self.contract), [])

    def test_24_bad_checker_source_pin_is_invalid(self):
        bad = copy.deepcopy(self.contract)
        bad["checker_source_sha256"] = "0" * 64
        self.assertTrue(CHECKER._validate_contract_impl(bad))

    def test_25_bad_witness_digest_is_verification_failed(self):
        bad = copy.deepcopy(self.contract)
        bad["expected_witness_sha256"] = "0" * 64
        result = self.internal_verify(contract=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")

    def test_26_certificate_extra_key_is_invalid_schema(self):
        bad = copy.deepcopy(self.certificate)
        bad["unexpected"] = None
        self.assertEqual(self.internal_verify(certificate=bad)["status"], "INVALID_SCHEMA")

    def test_27_float_schema_version_is_invalid_schema(self):
        bad = copy.deepcopy(self.certificate)
        bad["schema_version"] = 1.0
        self.assertEqual(self.internal_verify(certificate=bad)["status"], "INVALID_SCHEMA")

    def test_28_scope_overclaim_is_invalid_schema(self):
        bad = copy.deepcopy(self.certificate)
        bad["scope_claims"]["global_D3_norm_lower_bounded_by_cluster_sum"] = True
        self.assertEqual(self.internal_verify(certificate=bad)["status"], "INVALID_SCHEMA")

    def test_29_well_shaped_partial_sum_tamper_is_verification_failed(self):
        bad = copy.deepcopy(self.certificate)
        bad["witness_claim"]["uniform_supremum_architecture_infeasibility_proof"][
            "k0_partial_sum_of_cluster_norm_lower_bounds"
        ] = "5/2"
        result = self.internal_verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")

    def test_30_well_shaped_D3_digest_tamper_is_verification_failed(self):
        bad = copy.deepcopy(self.certificate)
        bad["witness_claim"]["D3_identity"]["exact_Pauli_expansion_sha256"] = "0" * 64
        self.assertEqual(self.internal_verify(certificate=bad)["status"], "VERIFICATION_FAILED")

    def test_31_duplicate_JSON_key_is_rejected(self):
        with self.assertRaisesRegex(CHECKER.SchemaError, "duplicate JSON key"):
            CHECKER._strict_json_bytes(b'{"a":1,"a":2}', "probe")

    def test_32_nonfinite_JSON_is_rejected(self):
        with self.assertRaisesRegex(CHECKER.SchemaError, "non-finite"):
            CHECKER._strict_json_bytes(b'{"a":NaN}', "probe")

    def test_33_corrupt_fixture_encoding_fails_closed(self):
        with self.assertRaises(CHECKER.SchemaError):
            CHECKER._decompress_fixture(b"not-a-valid-fixture")

    def test_34_fixture_node_extra_key_is_rejected(self):
        counter = [0]
        with self.assertRaises(CHECKER.SchemaError):
            CHECKER._validate_node(
                {"t": "n", "c": "1/1", "i": 0, "extra": None}, "node", counter
            )

    def test_35_checker_source_OSError_fails_closed(self):
        with mock.patch.object(CHECKER, "_read_checker_source_bytes", side_effect=OSError("gone")):
            result = CHECKER.verify_certificate(self.contract, self.certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["ready_gate_eligible"])

    def test_36_source_mismatch_is_rejected_before_exec(self):
        with mock.patch.object(CHECKER, "_read_checker_source_bytes", return_value=b"drift"), mock.patch.object(
            CHECKER.types, "ModuleType", side_effect=AssertionError("must not execute")
        ) as constructor:
            result = CHECKER.verify_certificate(self.contract, self.certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertIn("before compile/exec", result["errors"][0])
        constructor.assert_not_called()

    def test_37_failure_clears_every_positive_scope(self):
        bad = copy.deepcopy(self.certificate)
        bad["schema_version"] = 2
        result = self.internal_verify(certificate=bad)
        for key, expected in CHECKER.SCOPE_CLAIMS.items():
            if expected is True:
                self.assertFalse(result["scope_claims"][key])

    def test_38_cli_always_returns_one(self):
        fake = {
            "status": CHECKER.MAXIMUM_POSITIVE_STATUS,
            "verified": True,
            "ready_gate_eligible": False,
        }
        stdout = io.StringIO()
        with mock.patch.object(CHECKER, "load_strict_json", return_value={}), mock.patch.object(
            CHECKER, "verify_certificate", return_value=fake
        ), contextlib.redirect_stdout(stdout):
            self.assertEqual(CHECKER.main(["contract.json", "certificate.json"]), 1)
        self.assertFalse(json.loads(stdout.getvalue())["ready_gate_eligible"])

    def test_39_loader_rejects_duplicate_file_keys(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as handle:
            handle.write('{"a":1,"a":2}')
            path = pathlib.Path(handle.name)
        try:
            with self.assertRaises(CHECKER.SchemaError):
                CHECKER.load_strict_json(path)
        finally:
            path.unlink()

    def test_40_field_transition_has_exact_fermionic_sign(self):
        # a^dagger_0 a_2 acting on |110> annihilates mode 2 and crosses occupied mode 1.
        result = CHECKER._transition(Fraction(3, 5), ((0, 0), (1, 2)), 0b110)
        self.assertEqual(result, (0b011, Fraction(-3, 5)))


if __name__ == "__main__":
    unittest.main()
