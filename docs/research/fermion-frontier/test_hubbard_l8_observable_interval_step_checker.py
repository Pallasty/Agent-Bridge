#!/usr/bin/env python3
"""Regression tests for the fail-closed L=8 observable interval checker."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import pathlib
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


CHECKER = load_module(
    "hubbard_l8_observable_interval_step_checker",
    "hubbard_l8_observable_interval_step_checker.py",
)


class HubbardL8ObservableIntervalStepCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = CHECKER.load_strict_json(
            HERE / "hubbard_l8_observable_interval_step_contract.json"
        )
        cls.certificate = CHECKER.load_strict_json(
            HERE / "hubbard_l8_observable_interval_step_template.json"
        )
        # This is the sole full L=8 recomputation in the test process.  Tamper
        # tests below call the internal verifier with this witness mocked.
        cls.positive = CHECKER.verify_certificate(cls.contract, cls.certificate)
        cls.witness = cls.positive["recomputed_witness"]
        cls.observables = {
            item["observable_id"]: item
            for item in cls.witness["observable_claims"]
        }

    def internal_verify(self, contract=None, certificate=None):
        with mock.patch.object(
            CHECKER, "recompute_witness", return_value=self.witness
        ):
            return CHECKER._verify_certificate_impl(
                self.contract if contract is None else contract,
                self.certificate if certificate is None else certificate,
            )

    def test_01_positive_status_is_narrow(self) -> None:
        self.assertEqual(
            self.positive["status"],
            "VERIFIED_L8_ONE_STEP_MAPPED_INTERVAL_TRUNCATION_SUBCERTIFICATE",
        )
        self.assertTrue(self.positive["verified"])
        self.assertFalse(self.positive["ready_gate_eligible"])
        self.assertEqual(self.positive["errors"], [])

    def test_02_scope_stops_before_R100_and_exact_Hubbard(self) -> None:
        scope = self.positive["scope_claims"]
        self.assertEqual(scope["product_formula_to_exact_Hubbard_error"], "NOT_ASSESSED")
        self.assertEqual(scope["full_R100_observable_propagation"], "NOT_ASSESSED")
        self.assertEqual(
            scope["MajoranaPropagation_runtime_or_Manifest_custody"], "NOT_ASSESSED"
        )
        self.assertFalse(scope["physical_reference_qualified"])
        self.assertFalse(scope["ready_gate_eligible"])

    def test_03_decision_routes_only_to_repeated_step_chain(self) -> None:
        decision = self.witness["decision"]
        self.assertTrue(decision["one_step_nonzero_truncation_ledger_closed"])
        self.assertTrue(decision["continue_to_repeated_step_parent_child_checkpoint_chain"])
        self.assertFalse(decision["full_R100_or_exact_Hubbard_error_certified"])

    def test_04_checker_and_every_dependency_are_hash_pinned(self) -> None:
        self.assertEqual(
            self.contract["checker_source_sha256"],
            hashlib.sha256(
                (HERE / "hubbard_l8_observable_interval_step_checker.py").read_bytes()
            ).hexdigest(),
        )
        for pin in self.contract["source_pins"]:
            self.assertEqual(
                pin["sha256"],
                hashlib.sha256((HERE / pin["relative_path"]).read_bytes()).hexdigest(),
            )

    def test_05_witness_digest_matches_contract(self) -> None:
        self.assertEqual(
            CHECKER.canonical_sha256(self.witness),
            self.contract["expected_witness_sha256"],
        )

    def test_06_source_pinned_base_is_positive(self) -> None:
        base = self.witness["source_pinned_base"]
        self.assertEqual(base["status"], CHECKER.BASE_POSITIVE_STATUS)
        self.assertTrue(base["verified"])
        self.assertEqual(base["checker_sha256"], CHECKER.SOURCE_PINS[0]["sha256"])

    def test_07_mapping_geometry_counts_are_exact(self) -> None:
        mapping = self.witness["mapping_oracles"]
        self.assertEqual(mapping["geometric_bond_count"], 112)
        self.assertEqual(mapping["spin_resolved_bond_count"], 224)
        self.assertEqual(
            mapping["group_spin_resolved_bond_counts"],
            {"H1": 64, "H2": 48, "H3": 48, "H4": 64},
        )
        self.assertTrue(mapping["all_groups_match_source_pinned_backend"])

    def test_08_group_term_counts_and_digests_are_fixed(self) -> None:
        expected = {
            "H1": (128, "0201714666b8a72db1ccb3423e142e778efb981dfa3dfddd5a46078d234a3183"),
            "H2": (96, "5cf03045c65b8ee7998332ae3e75af06c265b29da70b3cf76439bfa42f13c7d3"),
            "HU": (192, "846b118b5b927ec939efc8b6a837424c28847338ca6005afbf4aaea6090594be"),
            "H3": (96, "d123ddff88ed615c2c1df8ec1079a48627c6cf8fd79317f0cb2f8a268329b0b7"),
            "H4": (128, "ec39bc442a5e7a63864d31f85a19315be3635830650ab366dab8906b20a7edaa"),
        }
        records = {
            item["group"]: item for item in self.witness["mapping_oracles"]["group_records"]
        }
        self.assertEqual(set(records), set(CHECKER.GROUPS))
        for group, (count, digest) in expected.items():
            self.assertEqual(records[group]["term_count"], count)
            self.assertEqual(records[group]["expansion_sha256"], digest)

    def test_09_every_group_internal_pair_is_checked(self) -> None:
        mapping = self.witness["mapping_oracles"]
        self.assertEqual(
            mapping["group_internal_pair_counts"],
            {"H1": 8128, "H2": 4560, "HU": 18336, "H3": 4560, "H4": 8128},
        )
        self.assertTrue(mapping["all_group_generators_internally_commute"])

    def test_10_CAR_representative_equivalence_classes_are_fixed(self) -> None:
        mapping = self.witness["mapping_oracles"]
        self.assertEqual(mapping["CAR_representative_equivalence_classes_per_bond"], 16)
        self.assertEqual(mapping["CAR_action_witness_count"], 3584)
        self.assertTrue(
            mapping["all_representative_hopping_CAR_equivalence_classes_match_JW"]
        )
        self.assertRegex(mapping["CAR_action_witnesses_sha256"], r"^[0-9a-f]{64}$")

    def test_11_onsite_occupation_oracle_is_complete(self) -> None:
        mapping = self.witness["mapping_oracles"]
        self.assertEqual(mapping["onsite_occupation_witness_count"], 256)
        self.assertTrue(mapping["all_onsite_energies_match_unshifted_U_nup_ndown"])
        self.assertRegex(mapping["onsite_occupation_witnesses_sha256"], r"^[0-9a-f]{64}$")

    def test_12_fused_and_backprop_sequence_counts_and_hashes(self) -> None:
        sequence = self.witness["sequence_identity"]
        self.assertEqual(sequence["fused_stage_count"], 9)
        self.assertEqual(sequence["fused_forward_gate_count"], 1152)
        self.assertEqual(sequence["backprop_gate_count"], 1152)
        self.assertEqual(sequence["raw_nonidentity_gate_count"], 1280)
        for key in (
            "forward_stage_records_sha256",
            "forward_gate_records_sha256",
            "raw_forward_stage_records_sha256",
            "raw_forward_gate_records_sha256",
            "backprop_gate_records_sha256",
        ):
            self.assertRegex(sequence[key], r"^[0-9a-f]{64}$")

    def test_13_theta_histogram_is_exact(self) -> None:
        self.assertEqual(
            self.witness["sequence_identity"]["theta_histogram"],
            {"-1/200": 640, "-1/100": 128, "-1/50": 256, "1/50": 128},
        )

    def test_14_raw_to_fused_H4_equivalence_is_explicit(self) -> None:
        sequence = self.witness["sequence_identity"]
        self.assertTrue(sequence["central_H4_half_events_fused_before_truncation"])
        self.assertEqual(sequence["central_H4_fused_generator_count"], 128)
        self.assertEqual(sequence["central_H4_internal_commutation_pair_count"], 8128)
        self.assertTrue(sequence["raw_and_fused_exact_unitaries_equal_from_internal_commutation"])
        self.assertFalse(sequence["raw_and_fused_truncation_paths_identical"])

    def test_15_omitted_global_phase_ledger_is_derived(self) -> None:
        phase = self.witness["sequence_identity"]["omitted_global_phase"]
        self.assertEqual(phase["HU_identity_Hamiltonian_coefficient"], "128/1")
        self.assertEqual(phase["phase_exponent_per_HU_half_stage"], "16/25")
        self.assertEqual(phase["phase_exponent_per_step"], "32/25")
        self.assertEqual(phase["phase_exponent_R100"], "128/1")
        self.assertEqual(phase["identity_rotation_theta_sum_per_step"], "64/25")
        self.assertEqual(phase["identity_rotation_theta_sum_R100"], "256/1")
        self.assertTrue(phase["cancels_from_Heisenberg_observable_conjugation"])

    def test_16_trigonometric_tick_enclosures_are_exact(self) -> None:
        trig = self.witness["fixed_point_trigonometric_intervals"]
        self.assertEqual(trig["unique_theta_count"], 4)
        self.assertEqual(trig["maximum_trigonometric_tick_bits"], 64)
        self.assertLessEqual(
            trig["maximum_trigonometric_tick_bits"],
            CHECKER.RESOURCE_LIMITS["max_trigonometric_tick_bits"],
        )
        expected = {
            "-1/50": ((-368910286307334577, -368910286307334576), (18443054847871463831, 18443054847871463832)),
            "-1/100": ((-184464366295122149, -184464366295122148), (18445821744191983882, 18445821744191983883)),
            "-1/200": ((-92233336061859940, -92233336061859939), (18446513489889013806, 18446513489889013807)),
            "1/50": ((368910286307334576, 368910286307334577), (18443054847871463831, 18443054847871463832)),
        }
        records = {item["theta"]: item for item in trig["records"]}
        self.assertEqual(set(records), set(expected))
        for theta, (sine, cosine) in expected.items():
            record = records[theta]
            self.assertEqual(
                (int(record["sine_tick_interval"]["lower"]), int(record["sine_tick_interval"]["upper"])),
                sine,
            )
            self.assertEqual(
                (int(record["cosine_tick_interval"]["lower"]), int(record["cosine_tick_interval"]["upper"])),
                cosine,
            )

    def test_17_Taylor_policy_rejects_theta_outside_unit_interval(self) -> None:
        with self.assertRaisesRegex(CHECKER.SchemaError, "exceeds Taylor policy"):
            CHECKER._taylor_trig_record(Fraction(1001, 1000))

    def test_18_signed_tick_floor_and_ceil_are_outward(self) -> None:
        value = Fraction(-1, 3)
        lower = CHECKER._floor_tick(value)
        upper = CHECKER._ceil_tick(value)
        self.assertLessEqual(Fraction(lower, CHECKER.TICK_DENOMINATOR), value)
        self.assertGreaterEqual(Fraction(upper, CHECKER.TICK_DENOMINATOR), value)
        self.assertEqual(upper - lower, 1)

    def test_19_four_corner_tick_multiply_is_outward_and_counted(self) -> None:
        counter = CHECKER.PropagationCounter()
        left = (1, 2)
        right = (3, 5)
        result = CHECKER._multiply_ticks(left, right, counter)
        products = [Fraction(a * b, CHECKER.TICK_DENOMINATOR) for a in left for b in right]
        self.assertLessEqual(result[0], min(products))
        self.assertGreaterEqual(result[1], max(products))
        self.assertGreater(counter.multiplication_rounding_l1_scaled_ticks_squared, 0)

        signed_counter = CHECKER.PropagationCounter()
        self.assertEqual(
            CHECKER._multiply_ticks((-1, 1), (1, 1), signed_counter),
            (-1, 1),
        )
        self.assertEqual(
            signed_counter.multiplication_rounding_l1_scaled_ticks_squared,
            CHECKER.TICK_DENOMINATOR - 1,
        )

    def test_19a_single_expansion_peak_survives_later_cancellation(self) -> None:
        counter = CHECKER.PropagationCounter()
        output = {}
        counter.begin_window(output)
        CHECKER._add_tick_term(output, (1, 0), (7, 7), counter)
        CHECKER._add_tick_term(output, (1, 0), (-7, -7), counter)
        self.assertEqual(output, {})
        self.assertEqual(counter.window_peak_live_terms, 1)
        self.assertEqual(counter.peak_live_terms, 1)

    def test_20_anticommuting_branch_has_correct_iPQ_sign(self) -> None:
        self.assertEqual(CHECKER._anticommuting_branch((1, 0), (0, 1)), (1, (1, 1)))
        self.assertEqual(CHECKER._anticommuting_branch((1, 0), (1, 1)), (-1, (0, 1)))

    def test_21_Neel_basis_identity_and_sector_are_fixed(self) -> None:
        state = self.witness["initial_Neel_state"]
        self.assertEqual(state["basis_integer_hex"], "0x66669999666699996666999966669999")
        self.assertEqual(state["particle_count"], 64)
        self.assertEqual(state["spin_up_particle_count"], 32)
        self.assertEqual(state["spin_down_particle_count"], 32)

    def test_22_initial_observable_expansions_are_exact(self) -> None:
        expected = {
            "staggered_magnetization": (
                128,
                "587b4cf490877d0c72a7ca7da1e877c7784b8c1335d985dacbb8d04ea56e8eb0",
                str(CHECKER.TICK_DENOMINATOR),
            ),
            "double_occupancy": (
                193,
                "cdb036613c85cdfe38c37982bf0fba55687bba90292dd90aeffd912a7db64b4e",
                "0",
            ),
        }
        for observable_id, (count, digest, expectation) in expected.items():
            item = self.observables[observable_id]
            self.assertEqual(item["initial_term_count"], count)
            self.assertEqual(item["initial_tick_expansion_sha256"], digest)
            self.assertEqual(item["initial_coefficient_L1"], "1/1")
            self.assertEqual(
                item["initial_Neel_expectation_interval"]["lower_ticks"], expectation
            )
            self.assertEqual(
                item["initial_Neel_expectation_interval"]["upper_ticks"], expectation
            )

    def test_23_magnetization_exact_final_ticks(self) -> None:
        item = self.observables["staggered_magnetization"]
        retained = item["final_retained_Neel_expectation_interval"]
        declared = item["declared_untruncated_mapped_step_Neel_expectation_interval"]
        self.assertEqual(
            (retained["lower_ticks"], retained["upper_ticks"]),
            ("18433845192157367192", "18433845192157371232"),
        )
        self.assertEqual(
            (declared["lower_ticks"], declared["upper_ticks"]),
            ("18433840572171559446", "18433849812143178978"),
        )
        self.assertEqual(item["cumulative_dropped_l1_ticks"], "4619985807746")

    def test_24_double_occupancy_exact_final_ticks(self) -> None:
        item = self.observables["double_occupancy"]
        retained = item["final_retained_Neel_expectation_interval"]
        declared = item["declared_untruncated_mapped_step_Neel_expectation_interval"]
        self.assertEqual(
            (retained["lower_ticks"], retained["upper_ticks"]),
            ("6447487876967911", "6447487876983172"),
        )
        self.assertEqual(
            (declared["lower_ticks"], declared["upper_ticks"]),
            ("6316730869963049", "6578244883988034"),
        )
        self.assertEqual(item["cumulative_dropped_l1_ticks"], "130757007004862")

    def test_25_declared_intervals_expand_retained_by_exact_drop(self) -> None:
        for item in self.observables.values():
            drop = int(item["cumulative_dropped_l1_ticks"])
            retained = item["final_retained_Neel_expectation_interval"]
            declared = item["declared_untruncated_mapped_step_Neel_expectation_interval"]
            self.assertEqual(int(declared["lower_ticks"]), int(retained["lower_ticks"]) - drop)
            self.assertEqual(int(declared["upper_ticks"]), int(retained["upper_ticks"]) + drop)

    def test_26_nonzero_drop_and_final_term_cap_are_exercised(self) -> None:
        for item in self.observables.values():
            self.assertTrue(item["nonzero_truncation_exercised"])
            self.assertGreater(int(item["cumulative_dropped_l1_ticks"]), 0)
            self.assertEqual(item["final_retained_term_count"], CHECKER.RETAINED_TERM_CAP)
            self.assertRegex(item["final_retained_expansion_sha256"], r"^[0-9a-f]{64}$")

    def test_27_checkpoint_ledger_has_fixed_coverage(self) -> None:
        expected = {
            "staggered_magnetization": (79, "205359206310"),
            "double_occupancy": (94, "3974627844893"),
        }
        for observable_id, item in self.observables.items():
            self.assertEqual(item["checkpoint_count"], 144)
            self.assertEqual(item["nonzero_checkpoint_count"], expected[observable_id][0])
            self.assertEqual(
                item["maximum_checkpoint_dropped_l1_ticks"], expected[observable_id][1]
            )
            self.assertRegex(item["checkpoint_ledger_sha256"], r"^[0-9a-f]{64}$")

    def test_28_stage_ledger_has_reverse_palindrome_order(self) -> None:
        expected_groups = ["H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1"]
        for item in self.observables.values():
            stages = item["stage_records"]
            self.assertEqual(len(stages), 9)
            self.assertEqual([stage["group"] for stage in stages], expected_groups)
            self.assertEqual([stage["backprop_stage_index"] for stage in stages], list(range(9)))
            self.assertEqual([stage["forward_stage_index"] for stage in stages], list(reversed(range(9))))

    def test_29_stage_drop_ledger_sums_and_is_cumulative(self) -> None:
        for item in self.observables.values():
            stages = item["stage_records"]
            self.assertEqual(
                sum(int(stage["dropped_l1_ticks"]) for stage in stages),
                int(item["cumulative_dropped_l1_ticks"]),
            )
            cumulative = [Fraction(stage["cumulative_dropped_l1"]) for stage in stages]
            self.assertEqual(cumulative, sorted(cumulative))
            self.assertEqual(cumulative[-1], Fraction(item["cumulative_dropped_l1"]))

    def test_30_rounding_diagnostic_is_nonzero_and_not_additive_error(self) -> None:
        expected = {
            "staggered_magnetization": "71968102409893118297945482",
            "double_occupancy": "99262938124477471974036453",
        }
        for observable_id, item in self.observables.items():
            usage = item["resource_usage"]
            self.assertEqual(
                usage["multiplication_grid_rounding_L1_upper_scaled_ticks_squared"],
                expected[observable_id],
            )
            self.assertGreater(Fraction(usage["multiplication_grid_rounding_L1_upper"]), 0)
            self.assertTrue(
                usage["multiplication_grid_rounding_already_contained_not_additive_error"]
            )

    def test_31_resource_usage_is_within_every_dynamic_cap(self) -> None:
        expected = {
            "staggered_magnetization": (49_896_346, 115_492, 58, 121),
            "double_occupancy": (63_370_607, 199_528, 63, 120),
        }
        for observable_id, item in self.observables.items():
            usage = item["resource_usage"]
            self.assertEqual(
                (
                    usage["term_gate_visits"],
                    usage["peak_single_expansion_term_count"],
                    usage["maximum_expansion_coefficient_tick_bits"],
                    usage["maximum_product_bits"],
                ),
                expected[observable_id],
            )
            self.assertLessEqual(usage["term_gate_visits"], CHECKER.RESOURCE_LIMITS["max_term_gate_visits"])
            self.assertLessEqual(
                usage["peak_single_expansion_term_count"],
                CHECKER.RESOURCE_LIMITS["max_single_expansion_terms"],
            )
            self.assertLessEqual(
                usage["maximum_expansion_coefficient_tick_bits"],
                CHECKER.RESOURCE_LIMITS["max_expansion_coefficient_tick_bits"],
            )
            self.assertLessEqual(usage["maximum_product_bits"], CHECKER.RESOURCE_LIMITS["max_product_bits"])

    def test_32_truncation_tie_break_is_deterministic(self) -> None:
        expansion = {(3, 0): (5, 5), (1, 0): (-5, -5), (2, 0): (4, 4)}
        with mock.patch.object(CHECKER, "RETAINED_TERM_CAP", 2):
            retained, dropped = CHECKER._truncate(expansion)
        self.assertEqual(list(retained), [(1, 0), (3, 0)])
        self.assertEqual(dropped["dropped_l1_ticks"], 4)
        self.assertEqual(dropped["minimum_retained_abs_upper_ticks"], 5)
        self.assertEqual(dropped["maximum_dropped_abs_upper_ticks"], 4)

    def test_33_basis_expectation_uses_Z_sign_and_ignores_X(self) -> None:
        expansion = {(0, 0): (10, 11), (0, 1): (2, 4), (1, 0): (100, 200)}
        self.assertEqual(CHECKER._expectation_ticks(expansion, 0), (12, 15))
        self.assertEqual(CHECKER._expectation_ticks(expansion, 1), (6, 9))

    def test_34_internal_contract_validation_succeeds(self) -> None:
        self.assertEqual(CHECKER._validate_contract_impl(self.contract), [])

    def test_35_warm_cache_returns_fresh_copy_and_rechecks_pins(self) -> None:
        cached = json.dumps(
            self.witness, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("ascii")
        with mock.patch.object(CHECKER, "_WITNESS_CACHE_BYTES", cached):
            first = CHECKER.recompute_witness()
            second = CHECKER.recompute_witness()
            self.assertEqual(first, self.witness)
            self.assertEqual(second, self.witness)
            self.assertIsNot(first, second)
            with mock.patch.object(
                CHECKER, "_read_pinned_sources", side_effect=CHECKER.SchemaError("drift")
            ):
                with self.assertRaisesRegex(CHECKER.SchemaError, "drift"):
                    CHECKER.recompute_witness()

    def test_36_bad_checker_source_pin_is_invalid_schema(self) -> None:
        bad = copy.deepcopy(self.contract)
        bad["checker_source_sha256"] = "0" * 64
        result = CHECKER._validate_contract_impl(bad)
        self.assertTrue(result)
        self.assertIn("pin", result[0])

    def test_37_contract_source_pin_tamper_is_invalid_schema(self) -> None:
        bad = copy.deepcopy(self.contract)
        bad["source_pins"][0]["sha256"] = "0" * 64
        self.assertEqual(self.internal_verify(contract=bad)["status"], "INVALID_SCHEMA")

    def test_38_bad_expected_witness_digest_is_verification_failed(self) -> None:
        bad = copy.deepcopy(self.contract)
        bad["expected_witness_sha256"] = "0" * 64
        self.assertEqual(self.internal_verify(contract=bad)["status"], "VERIFICATION_FAILED")

    def test_39_certificate_exact_shape_and_types_are_enforced(self) -> None:
        extra = copy.deepcopy(self.certificate)
        extra["unexpected"] = None
        floating = copy.deepcopy(self.certificate)
        floating["schema_version"] = 1.0
        self.assertEqual(self.internal_verify(certificate=extra)["status"], "INVALID_SCHEMA")
        self.assertEqual(self.internal_verify(certificate=floating)["status"], "INVALID_SCHEMA")

    def test_40_scope_overclaim_is_invalid_schema(self) -> None:
        bad = copy.deepcopy(self.certificate)
        bad["scope_claims"]["full_R100_observable_propagation"] = True
        result = self.internal_verify(certificate=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["ready_gate_eligible"])

    def test_41_well_shaped_output_and_checkpoint_tampers_fail(self) -> None:
        paths = (
            ("staggered_magnetization", "cumulative_dropped_l1_ticks", "0"),
            ("double_occupancy", "checkpoint_ledger_sha256", "0" * 64),
        )
        for observable_id, field, value in paths:
            with self.subTest(observable_id=observable_id, field=field):
                bad = copy.deepcopy(self.certificate)
                item = next(
                    claim
                    for claim in bad["witness_claim"]["observable_claims"]
                    if claim["observable_id"] == observable_id
                )
                item[field] = value
                self.assertEqual(
                    self.internal_verify(certificate=bad)["status"],
                    "VERIFICATION_FAILED",
                )

    def test_42_strict_JSON_rejects_duplicate_nonfinite_and_oversize(self) -> None:
        probes = (
            (b'{"a":1,"a":2}', "duplicate JSON key"),
            (b'{"a":NaN}', "non-finite"),
            (b" " * (CHECKER.RESOURCE_LIMITS["max_json_bytes"] + 1), "byte cap"),
        )
        for payload, message in probes:
            with self.subTest(message=message):
                with self.assertRaisesRegex(CHECKER.SchemaError, message):
                    CHECKER._strict_json_bytes(payload, "probe")

    def test_43_source_drift_is_rejected_before_compile_or_exec(self) -> None:
        with mock.patch.object(
            CHECKER, "_read_checker_source_bytes", return_value=b"drift"
        ), mock.patch.object(
            CHECKER.types, "ModuleType", side_effect=AssertionError("must not execute")
        ) as constructor:
            result = CHECKER.verify_certificate(self.contract, self.certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertIn("before compile/exec", result["errors"][0])
        constructor.assert_not_called()

    def test_44_failure_clears_every_positive_scope_claim(self) -> None:
        bad = copy.deepcopy(self.certificate)
        bad["schema_version"] = 2
        result = self.internal_verify(certificate=bad)
        for key, expected in CHECKER.SCOPE_CLAIMS.items():
            if expected is True:
                self.assertFalse(result["scope_claims"][key])

    def test_45_CLI_always_returns_one_even_for_positive_result(self) -> None:
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
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["status"], CHECKER.MAXIMUM_POSITIVE_STATUS)
        self.assertFalse(output["ready_gate_eligible"])


if __name__ == "__main__":
    unittest.main()
