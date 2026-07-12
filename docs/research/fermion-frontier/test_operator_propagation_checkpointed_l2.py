import contextlib
import copy
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
    "operator_propagation_checkpointed_l2",
    "operator_propagation_checkpointed_l2.py",
)


class CheckpointedL2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_path = HERE / "operator_propagation_checkpointed_l2_contract.json"
        cls.certificate_path = HERE / "operator_propagation_checkpointed_l2_template.json"
        cls.contract = CHECKER.load_strict_json(cls.contract_path)
        cls.certificate = CHECKER.load_strict_json(cls.certificate_path)
        # The expensive full-space 112-gate replay runs exactly once here.
        cls.positive = CHECKER.verify_certificate(cls.contract, cls.certificate)

    def mutated_certificate(self):
        return copy.deepcopy(self.certificate)

    def mutated_contract(self):
        return copy.deepcopy(self.contract)

    def test_fixed_status_is_narrow_subcertificate(self):
        self.assertEqual(
            CHECKER.MAXIMUM_POSITIVE_STATUS,
            "VERIFIED_L2_MAPPED_CIRCUIT_TRUNCATION_SUBCERTIFICATE",
        )

    def test_contract_validates(self):
        self.assertEqual(CHECKER.validate_contract(self.contract), [])

    def test_positive_template_verifies(self):
        self.assertTrue(self.positive["verified"])
        self.assertEqual(self.positive["errors"], [])
        self.assertTrue(
            self.positive["checker_executed_source_bytes_sha256_verified"]
        )

    def test_positive_template_has_maximum_status(self):
        self.assertEqual(
            self.positive["status"], CHECKER.MAXIMUM_POSITIVE_STATUS
        )

    def test_positive_template_never_sets_ready(self):
        self.assertFalse(self.positive["ready_gate_eligible"])
        self.assertFalse(self.positive["scope_claims"]["ready_gate_eligible"])

    def test_scope_keeps_product_formula_L8_and_budget_unassessed(self):
        scope = self.positive["scope_claims"]
        self.assertEqual(scope["product_formula_to_exact_hamiltonian"], "NOT_ASSESSED")
        self.assertEqual(scope["physical_L8_instance_identity"], "NOT_ASSESSED")
        self.assertEqual(scope["reference_error_budget"], "NOT_ASSESSED")

    def test_all_required_sources_are_pinned(self):
        paths = [pin["relative_path"] for pin in CHECKER.SOURCE_PINS]
        self.assertEqual(
            paths,
            [
                "hubbard_jw_mapping_validator.py",
                "hubbard_jw_mapping_contract.json",
                "hubbard_jw_mapping_template.json",
                "pauli_bitset_backend.py",
                "operator_propagation_certificate_checker.py",
                "operator_propagation_l2_witness.py",
            ],
        )

    def test_mapping_positive_status_is_bound(self):
        claim = self.certificate["source_pinned_mapping"]
        self.assertEqual(claim["status"], CHECKER.MAPPING_POSITIVE_STATUS)
        self.assertTrue(claim["verified"])

    def test_forward_gate_count_and_digest_are_pinned(self):
        self.assertEqual(self.certificate["forward_gate_count"], 112)
        self.assertEqual(
            self.certificate["forward_gate_sequence_sha256"],
            CHECKER.EXPECTED_FORWARD_GATE_SEQUENCE_SHA256,
        )

    def test_exactly_twenty_raw_event_checkpoints_per_observable(self):
        for observable in self.certificate["observable_claims"]:
            self.assertEqual(observable["checkpoint_count"], 20)
            self.assertEqual(len(observable["checkpoints"]), 20)

    def test_checkpoint_slice_indices_are_ascending(self):
        for observable in self.certificate["observable_claims"]:
            self.assertEqual(
                [item["slice_index"] for item in observable["checkpoints"]],
                list(range(20)),
            )

    def test_forward_event_indices_are_reversed(self):
        for observable in self.certificate["observable_claims"]:
            self.assertEqual(
                [item["forward_event_index"] for item in observable["checkpoints"]],
                list(reversed(range(20))),
            )

    def test_checkpoint_gate_counts_sum_to_112(self):
        for observable in self.certificate["observable_claims"]:
            self.assertEqual(
                sum(item["gate_count"] for item in observable["checkpoints"]),
                112,
            )

    def test_l2_empty_H2_H3_events_remain_checkpointed(self):
        checkpoints = self.certificate["observable_claims"][0]["checkpoints"]
        empty = [item for item in checkpoints if item["gate_count"] == 0]
        self.assertEqual(len(empty), 8)
        self.assertTrue(all(item["group"] in {"H2", "H3"} for item in empty))

    def test_full_space_policy_drops_no_terms(self):
        for observable in self.certificate["observable_claims"]:
            self.assertEqual(observable["cumulative_dropped_l1"], "0/1")
            self.assertTrue(
                all(item["dropped_term_count"] == 0 for item in observable["checkpoints"])
            )
            self.assertTrue(
                all(item["dropped_l1_increment"] == "0/1" for item in observable["checkpoints"])
            )

    def test_final_full_space_term_counts_match_oracle(self):
        claims = {item["observable_id"]: item for item in self.certificate["observable_claims"]}
        self.assertEqual(claims["staggered_magnetization"]["final_retained_term_count"], 16380)
        self.assertEqual(claims["double_occupancy"]["final_retained_term_count"], 16381)

    def test_final_magnetization_interval_matches_oracle(self):
        claim = self.certificate["observable_claims"][0]
        self.assertEqual(
            claim["final_retained_expectation_interval"],
            {"lower": "104895467/134217728", "upper": "209888553/268435456"},
        )

    def test_final_double_occupancy_interval_matches_oracle(self):
        claim = self.certificate["observable_claims"][1]
        self.assertEqual(
            claim["final_retained_expectation_interval"],
            {"lower": "8238201/268435456", "upper": "33458587/1073741824"},
        )

    def test_final_checkpoint_digests_match_oracle(self):
        claims = self.certificate["observable_claims"]
        self.assertEqual(
            claims[0]["final_checkpoint_sha256"],
            "f4cc999309758eb020101100637f30a5b4ee0e73ddfc6920f3d4b28508aab3c7",
        )
        self.assertEqual(
            claims[1]["final_checkpoint_sha256"],
            "b1bcb4dd7be2d05e84019b7f1515c10b9ce4078ba97d9188da5ea56b0ef5b52c",
        )

    def test_float_diagnostics_are_contained_but_not_proof(self):
        for observable in self.certificate["observable_claims"]:
            diagnostic = observable["statevector_product_formula_diagnostic"]
            self.assertTrue(diagnostic["contained_in_declared_interval"])
            self.assertFalse(diagnostic["used_as_proof"])
            self.assertEqual(diagnostic["status"], CHECKER.DIAGNOSTIC_STATUS)

    def test_parse_fraction_accepts_reduced_canonical_values(self):
        self.assertEqual(CHECKER.parse_fraction("-7/11"), Fraction(-7, 11))
        self.assertEqual(CHECKER.parse_fraction("0/1"), Fraction(0))

    def test_parse_fraction_rejects_noncanonical_values(self):
        for value in ("2/4", "00/1", "+1/2", "1/-2", "1", 1, True):
            with self.subTest(value=value):
                with self.assertRaises(CHECKER.SchemaError):
                    CHECKER.parse_fraction(value)

    def test_integer_rejects_bool(self):
        with self.assertRaises(CHECKER.SchemaError):
            CHECKER._integer(True, "value", 0, 1)

    def test_outward_quantization_contains_positive_interval(self):
        source = (Fraction(1, 3), Fraction(2, 3))
        rounded = CHECKER.quantize_interval_outward(source, 16)
        self.assertEqual(rounded, (Fraction(5, 16), Fraction(11, 16)))
        self.assertLessEqual(rounded[0], source[0])
        self.assertGreaterEqual(rounded[1], source[1])

    def test_outward_quantization_contains_negative_interval(self):
        source = (Fraction(-2, 3), Fraction(-1, 3))
        rounded = CHECKER.quantize_interval_outward(source, 16)
        self.assertEqual(rounded, (Fraction(-11, 16), Fraction(-5, 16)))

    def test_outward_quantization_leaves_grid_values_exact(self):
        source = (Fraction(-3, 16), Fraction(7, 16))
        self.assertEqual(CHECKER.quantize_interval_outward(source, 16), source)

    def test_quantization_widening_is_nonnegative_and_exact(self):
        expansion = {(0, 1): (Fraction(1, 3), Fraction(2, 3))}
        with mock.patch.object(CHECKER, "QUANTIZATION_DENOMINATOR", 16):
            rounded, widening = CHECKER.quantize_expansion_outward(expansion)
        self.assertEqual(rounded[(0, 1)], (Fraction(5, 16), Fraction(11, 16)))
        self.assertEqual(widening, Fraction(1, 48))

    def test_truncation_under_cap_is_identity_with_zero_ledger(self):
        expansion = {(0, index): (Fraction(index + 1), Fraction(index + 1)) for index in range(4)}
        retained, dropped, count = CHECKER.truncate_deterministically(expansion)
        self.assertEqual(retained, expansion)
        self.assertEqual((dropped, count), (Fraction(0), 0))

    def test_truncation_order_uses_score_then_numeric_key(self):
        expansion = {
            (2, 0): (Fraction(-3), Fraction(3)),
            (1, 0): (Fraction(-3), Fraction(3)),
            (0, 1): (Fraction(-2), Fraction(2)),
        }
        with mock.patch.object(CHECKER, "RETAINED_TERM_CAP", 2):
            retained, dropped, count = CHECKER.truncate_deterministically(expansion)
        self.assertEqual(list(retained), [(1, 0), (2, 0)])
        self.assertEqual((dropped, count), (Fraction(2), 1))

    def test_computational_basis_expectation_uses_q0_first_bits(self):
        # Neel q0 is occupied, so Z0 has expectation -1; X terms vanish.
        expansion = {
            (0, 1): (Fraction(2), Fraction(3)),
            (1, 0): (Fraction(100), Fraction(100)),
        }
        self.assertEqual(
            CHECKER.computational_basis_expectation(expansion),
            (Fraction(-3), Fraction(-2)),
        )

    def test_initial_observable_counts_are_fixed(self):
        profiles = CHECKER.expected_observable_profiles()
        self.assertEqual([item["initial_term_count"] for item in profiles], [8, 13])

    def test_initial_observable_order_is_fixed(self):
        profiles = CHECKER.expected_observable_profiles()
        self.assertEqual(
            [item["observable_id"] for item in profiles],
            ["staggered_magnetization", "double_occupancy"],
        )

    def test_independent_float_statevector_matches_known_values(self):
        runtime = CHECKER._runtime_dependencies()
        forward, _, _ = CHECKER._forward_and_backprop_slices(runtime[0])
        values = CHECKER._mapped_statevector_observables(forward, runtime[2])
        self.assertAlmostEqual(values["staggered_magnetization"], 0.781713978559467, places=12)
        self.assertAlmostEqual(values["double_occupancy"], 0.0309252063024724, places=12)

    def test_verified_byte_execution_does_not_read_named_disk_source(self):
        module = CHECKER._module_from_verified_bytes(
            "drift_probe", "this_file_does_not_exist.py", b"VALUE = 7\n"
        )
        self.assertEqual(module.VALUE, 7)

    def test_missing_source_fails_closed(self):
        with mock.patch.object(pathlib.Path, "open", side_effect=OSError("gone")):
            with self.assertRaisesRegex(CHECKER.SchemaError, "cannot be read"):
                CHECKER._verified_source_bytes()

    def test_strict_json_rejects_duplicate_keys(self):
        with self.assertRaisesRegex(CHECKER.SchemaError, "duplicate JSON key"):
            CHECKER._strict_json_bytes(b'{"a":1,"a":2}', "probe", 100)

    def test_strict_json_rejects_nonfinite_constant(self):
        with self.assertRaisesRegex(CHECKER.SchemaError, "non-finite"):
            CHECKER._strict_json_bytes(b'{"a":NaN}', "probe", 100)

    def test_strict_json_enforces_byte_cap(self):
        with self.assertRaisesRegex(CHECKER.SchemaError, "byte cap"):
            CHECKER._strict_json_bytes(b'{"a":1}', "probe", 3)

    def test_bad_checker_source_pin_invalidates_contract(self):
        contract = self.mutated_contract()
        contract["checker_source_sha256"] = "0" * 64
        self.assertTrue(CHECKER.validate_contract(contract))

    def test_float_schema_version_is_rejected_as_non_integer(self):
        certificate = self.mutated_certificate()
        certificate["schema_version"] = 1.0
        result = CHECKER.verify_certificate(self.contract, certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["verified"])

    def test_certificate_extra_key_is_invalid_schema(self):
        certificate = self.mutated_certificate()
        certificate["unexpected"] = None
        result = CHECKER.verify_certificate(self.contract, certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["verified"])

    def test_certificate_scope_escalation_is_invalid_schema(self):
        certificate = self.mutated_certificate()
        certificate["scope_claims"]["ready_gate_eligible"] = True
        result = CHECKER.verify_certificate(self.contract, certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")

    def test_bool_gate_count_is_invalid_schema(self):
        certificate = self.mutated_certificate()
        certificate["observable_claims"][0]["checkpoints"][0]["gate_count"] = True
        result = CHECKER.verify_certificate(self.contract, certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")

    def test_negative_dropped_l1_is_invalid_schema(self):
        certificate = self.mutated_certificate()
        certificate["observable_claims"][0]["checkpoints"][0]["dropped_l1_increment"] = "-1/1"
        result = CHECKER.verify_certificate(self.contract, certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")

    def test_nonfinite_diagnostic_is_invalid_schema(self):
        certificate = self.mutated_certificate()
        certificate["observable_claims"][0]["statevector_product_formula_diagnostic"]["decimal_value"] = "NaN"
        result = CHECKER.verify_certificate(self.contract, certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")

    def test_failure_clears_all_positive_scope_bits(self):
        certificate = self.mutated_certificate()
        certificate["schema_version"] = 2
        result = CHECKER.verify_certificate(self.contract, certificate)
        for key, expected in CHECKER.SCOPE_CLAIMS.items():
            if expected is True:
                self.assertFalse(result["scope_claims"][key])
        self.assertFalse(result["ready_gate_eligible"])

    def test_well_shaped_checkpoint_tamper_is_verification_failure_and_clears_scope(self):
        certificate = self.mutated_certificate()
        certificate["observable_claims"][0]["final_checkpoint_sha256"] = "0" * 64
        with mock.patch.object(
            CHECKER,
            "recompute_certificate_claims",
            return_value=copy.deepcopy(self.positive["recomputed_claims"]),
        ):
            result = CHECKER._verify_certificate_impl(self.contract, certificate)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertFalse(result["verified"])
        for key, expected in CHECKER.SCOPE_CLAIMS.items():
            if expected is True:
                self.assertFalse(result["scope_claims"][key])
        self.assertFalse(result["ready_gate_eligible"])

    def test_checker_source_hash_OSError_fails_closed_at_API_boundary(self):
        with mock.patch.object(
            CHECKER, "_read_checker_source_bytes", side_effect=OSError("source vanished")
        ):
            result = CHECKER.verify_certificate(self.contract, self.certificate)
        self.assertFalse(result["verified"])
        self.assertFalse(result["ready_gate_eligible"])
        self.assertIn(result["status"], {"INVALID_SCHEMA", "VERIFICATION_FAILED"})

    def test_outer_source_pin_mismatch_is_rejected_before_compile_or_exec(self):
        with mock.patch.object(
            CHECKER, "_read_checker_source_bytes", return_value=b"drifted source"
        ), mock.patch.object(
            CHECKER.types,
            "ModuleType",
            side_effect=AssertionError("must not execute drifted source"),
        ) as module_constructor:
            result = CHECKER.verify_certificate(self.contract, self.certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertIn("before compile/exec", result["errors"][0])
        module_constructor.assert_not_called()

    def test_public_validate_ignores_loaded_module_impl_monkeypatch(self):
        with mock.patch.object(
            CHECKER, "_validate_contract_impl", return_value=["forged"]
        ):
            self.assertEqual(CHECKER.validate_contract(self.contract), [])

    def test_cli_return_code_is_one_even_for_verified_subcertificate(self):
        fake_result = {
            "status": CHECKER.MAXIMUM_POSITIVE_STATUS,
            "verified": True,
            "ready_gate_eligible": False,
        }
        stdout = io.StringIO()
        with (
            mock.patch.object(CHECKER, "load_strict_json", return_value={}),
            mock.patch.object(CHECKER, "verify_certificate", return_value=fake_result),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(CHECKER.main(["contract.json", "certificate.json"]), 1)
        self.assertEqual(json.loads(stdout.getvalue())["verified"], True)


if __name__ == "__main__":
    unittest.main()
