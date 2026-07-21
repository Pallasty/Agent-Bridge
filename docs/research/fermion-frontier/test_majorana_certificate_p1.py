#!/usr/bin/env python3
"""Pre-result tests for the result-unpinned Majorana P1 certificate inputs."""

from __future__ import annotations

from collections import Counter
from contextlib import redirect_stdout
import copy
from fractions import Fraction
import importlib.util
import io
from pathlib import Path
import subprocess
import unittest


BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "majorana_certificate_p1_checker",
    BASE / "majorana_certificate_p1_checker.py",
)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class MajoranaP1PrecommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = CHECKER.validate_fixture(
            CHECKER.load_json(BASE / CHECKER.FIXTURE_NAME)
        )
        cls.runtime_lock = CHECKER.validate_runtime_lock(
            CHECKER.load_json(BASE / CHECKER.RUNTIME_LOCK_NAME)
        )
        # This is the only full L2/L3 oracle construction in this process.  The
        # checker caches the profiles, so later validation and CLI tests are cheap.
        cls.expected = CHECKER.expected_witness(cls.fixture, cls.runtime_lock)
        cls.profiles = {
            profile["profile_id"]: profile for profile in cls.expected["profiles"]
        }
        cls.records = {
            profile_id: {
                record["operator_id"]: record
                for record in profile["operator_records"]
            }
            for profile_id, profile in cls.profiles.items()
        }
        cls.specs = {
            linear_size: {
                spec["operator_id"]: spec
                for spec in CHECKER._operator_specs(linear_size)
            }
            for linear_size in (2, 3)
        }

    def assert_witness_rejected(self, mutant: object) -> None:
        with self.assertRaisesRegex(CHECKER.VerificationError, "independent CAR oracle"):
            CHECKER.validate_witness(mutant, self.fixture, self.runtime_lock)

    @staticmethod
    def refresh_profile_digests(mutant: dict[str, object], profile_index: int) -> None:
        profiles = mutant["profiles"]
        assert isinstance(profiles, list)
        profile = profiles[profile_index]
        assert isinstance(profile, dict)
        profile["operator_records_sha256"] = CHECKER.canonical_sha256(
            profile["operator_records"]
        )
        aggregate = mutant["aggregate"]
        assert isinstance(aggregate, dict)
        aggregate["profiles_sha256"] = CHECKER.canonical_sha256(profiles)

    def test_01_strict_json_rejects_duplicate_keys(self) -> None:
        with self.assertRaisesRegex(CHECKER.SchemaError, "duplicate JSON key"):
            CHECKER.strict_json_loads(b'{"a":1,"a":2}')

    def test_02_strict_json_rejects_float_nonfinite_and_negative_zero(self) -> None:
        for payload in (
            b'{"x":1.0}',
            b'{"x":NaN}',
            b'{"x":Infinity}',
            b'{"x":-0}',
        ):
            with self.subTest(payload=payload), self.assertRaises(CHECKER.SchemaError):
                CHECKER.strict_json_loads(payload)

    def test_03_canonical_json_is_sorted_compact_utf8(self) -> None:
        self.assertEqual(
            CHECKER.canonical_bytes({"z": [True, None], "a": "μ"}),
            '{"a":"μ","z":[true,null]}'.encode(),
        )

    def test_04_fraction_text_is_reduced_and_canonical(self) -> None:
        self.assertEqual(CHECKER.parse_q("-7/12"), Fraction(-7, 12))
        self.assertEqual(CHECKER.format_q(Fraction(2, 4)), "1/2")
        self.assertEqual(CHECKER.format_q(Fraction(3)), "3")
        for text in ("+1", "01", "1/01", "2/4", "0/7", "-0"):
            with self.subTest(text=text), self.assertRaises(CHECKER.SchemaError):
                CHECKER.parse_q(text)

    def test_05_fixture_identity_profile_order_and_digest_are_frozen(self) -> None:
        self.assertEqual(
            CHECKER.canonical_sha256(self.fixture), CHECKER.FIXTURE_CANONICAL_SHA256
        )
        self.assertEqual(
            [profile["profile_id"] for profile in self.fixture["profiles"]],
            ["L2_OBC", "L3_OBC"],
        )
        self.assertEqual(
            self.fixture["fixture_id"],
            "MAJORANA-P1-L2-L3-HUBBARD-ACTION-CADENCE-V1",
        )

    def test_06_L2_fixture_counts_match_the_2_by_2_workload(self) -> None:
        profile = self.fixture["profiles"][0]
        self.assertEqual(
            {key: profile[key] for key in (
                "n_sites", "n_modes", "basis_dimension",
                "spin_resolved_hopping_instance_count", "onsite_instance_count",
                "local_Sz_observable_count", "campaign_observable_count",
                "operator_instance_count", "occupation_action_column_count",
                "dense_matrix_entry_count",
            )},
            {
                "n_sites": 4,
                "n_modes": 8,
                "basis_dimension": 256,
                "spin_resolved_hopping_instance_count": 8,
                "onsite_instance_count": 4,
                "local_Sz_observable_count": 4,
                "campaign_observable_count": 2,
                "operator_instance_count": 18,
                "occupation_action_column_count": 4608,
                "dense_matrix_entry_count": 1179648,
            },
        )

    def test_07_L3_fixture_counts_match_the_3_by_3_workload(self) -> None:
        profile = self.fixture["profiles"][1]
        self.assertEqual(
            {key: profile[key] for key in (
                "n_sites", "n_modes", "basis_dimension",
                "spin_resolved_hopping_instance_count", "onsite_instance_count",
                "local_Sz_observable_count", "campaign_observable_count",
                "operator_instance_count", "occupation_action_column_count",
                "dense_matrix_entry_count",
            )},
            {
                "n_sites": 9,
                "n_modes": 18,
                "basis_dimension": 262144,
                "spin_resolved_hopping_instance_count": 24,
                "onsite_instance_count": 9,
                "local_Sz_observable_count": 9,
                "campaign_observable_count": 2,
                "operator_instance_count": 44,
                "occupation_action_column_count": 11534336,
                "dense_matrix_entry_count": 3023656976384,
            },
        )

    def test_08_square_site_mode_and_basis_dimensions_are_consistent(self) -> None:
        for profile in self.fixture["profiles"]:
            linear_size = profile["linear_size"]
            self.assertEqual(profile["n_sites"], linear_size**2)
            self.assertEqual(profile["n_modes"], 2 * linear_size**2)
            self.assertEqual(profile["basis_dimension"], 1 << profile["n_modes"])
        convention = self.fixture["lattice_and_mode_convention"]
        self.assertEqual(convention["boundary_condition"], "square_open_boundary_no_wrap")
        self.assertIn("site_major_spin_minor", convention["mode_order"])

    def test_09_open_boundary_bond_counts_have_no_wrap_terms(self) -> None:
        counts_L2 = Counter(row["group"] for row in CHECKER._canonical_bonds(2))
        counts_L3 = Counter(row["group"] for row in CHECKER._canonical_bonds(3))
        self.assertEqual(counts_L2, Counter({"H1": 4, "H4": 4}))
        self.assertEqual(
            counts_L3, Counter({"H1": 6, "H2": 6, "H3": 6, "H4": 6})
        )
        for linear_size in (2, 3):
            for bond in CHECKER._canonical_bonds(linear_size):
                distance = abs(bond["row_a"] - bond["row_b"]) + abs(
                    bond["col_a"] - bond["col_b"]
                )
                self.assertEqual(distance, 1)

    def test_10_odd_L3_H2_and_H3_cover_the_second_disjoint_layers(self) -> None:
        bonds = CHECKER._canonical_bonds(3)
        H2 = [row for row in bonds if row["group"] == "H2"]
        H3 = [row for row in bonds if row["group"] == "H3"]
        self.assertEqual(len(H2), 6)
        self.assertTrue(all(row["col_a"] == 1 and row["col_b"] == 2 for row in H2))
        self.assertTrue(all(row["row_a"] == row["row_b"] for row in H2))
        self.assertEqual(len(H3), 6)
        self.assertTrue(all(row["row_a"] == 1 and row["row_b"] == 2 for row in H3))
        self.assertTrue(all(row["col_a"] == row["col_b"] for row in H3))

    def test_11_local_constructor_terms_preserve_spin_and_quartic_signs(self) -> None:
        self.assertEqual(
            CHECKER._constructor_terms("nup", [1]),
            {0: Fraction(1, 2), 3: Fraction(1, 2)},
        )
        self.assertEqual(
            CHECKER._constructor_terms("ndn", [1]),
            {0: Fraction(1, 2), 12: Fraction(1, 2)},
        )
        self.assertEqual(
            CHECKER._constructor_terms("nupndn", [1]),
            {
                0: Fraction(1, 4),
                3: Fraction(1, 4),
                12: Fraction(1, 4),
                15: Fraction(-1, 4),
            },
        )
        self.assertEqual(
            CHECKER._constructor_terms("Sz", [1]),
            {3: Fraction(1, 4), 12: Fraction(-1, 4)},
        )

    def test_12_hopping_constructor_and_generator_signs_are_distinct(self) -> None:
        self.assertEqual(
            CHECKER._constructor_terms("hopup", [1, 2]),
            {33: Fraction(1, 2), 18: Fraction(-1, 2)},
        )
        self.assertEqual(
            CHECKER._constructor_terms("hopdn", [1, 2]),
            {132: Fraction(1, 2), 72: Fraction(-1, 2)},
        )
        self.assertEqual(
            self.specs[2]["H1_r0_c0_up"]["expansion"],
            {33: Fraction(-1, 2), 18: Fraction(1, 2)},
        )

    def test_13_ladder_action_uses_lower_mode_prefix_parity(self) -> None:
        self.assertEqual(CHECKER._apply_ladder(0b001, 2, True), (0b101, -1))
        self.assertEqual(CHECKER._apply_ladder(0b011, 2, True), (0b111, 1))
        self.assertEqual(CHECKER._apply_ladder(0b101, 2, False), (0b001, -1))
        self.assertIsNone(CHECKER._apply_ladder(0b100, 2, True))

    def test_14_hopping_action_has_negative_Hubbard_sign_and_is_bidirectional(self) -> None:
        self.assertEqual(CHECKER._hopping_action(0b001, 0, 2), {0b100: Fraction(-1)})
        self.assertEqual(CHECKER._hopping_action(0b100, 0, 2), {0b001: Fraction(-1)})
        self.assertEqual(CHECKER._hopping_action(0b011, 0, 2), {0b110: Fraction(1)})
        self.assertEqual(CHECKER._hopping_action(0b000, 0, 2), {})

    def test_15_spin_up_and_down_hopping_use_separate_interleaved_modes(self) -> None:
        up = self.specs[2]["H1_r0_c0_up"]
        down = self.specs[2]["H1_r0_c0_down"]
        self.assertEqual((up["left_mode"], up["right_mode"]), (0, 2))
        self.assertEqual((down["left_mode"], down["right_mode"]), (1, 3))
        self.assertEqual(
            CHECKER._car_action(up, 0b0001, 2),
            {0b0100: (Fraction(-1), Fraction(0))},
        )
        self.assertEqual(CHECKER._car_action(down, 0b0001, 2), {})
        self.assertEqual(
            CHECKER._car_action(down, 0b0010, 2),
            {0b1000: (Fraction(-1), Fraction(0))},
        )

    def test_16_local_Sz_and_onsite_actions_probe_diagonal_signs(self) -> None:
        Sz = self.specs[2]["OBS_Sz_r0_c0"]
        onsite = self.specs[2]["HU_r0_c0"]
        self.assertEqual(
            CHECKER._car_action(Sz, 0b01, 2),
            {0b01: (Fraction(1, 2), Fraction(0))},
        )
        self.assertEqual(
            CHECKER._car_action(Sz, 0b10, 2),
            {0b10: (Fraction(-1, 2), Fraction(0))},
        )
        self.assertEqual(CHECKER._car_action(Sz, 0b11, 2), {})
        self.assertEqual(
            CHECKER._car_action(onsite, 0b11, 2),
            {0b11: (Fraction(8), Fraction(0))},
        )

    def test_17_operator_partition_and_aggregate_counts_are_exact(self) -> None:
        aggregate = self.expected["aggregate"]
        self.assertEqual(aggregate["profile_count"], 2)
        self.assertEqual(aggregate["operator_instance_count"], 62)
        self.assertEqual(aggregate["hubbard_generator_instance_count"], 45)
        self.assertEqual(aggregate["local_Sz_observable_instance_count"], 13)
        self.assertEqual(aggregate["campaign_observable_instance_count"], 4)
        self.assertEqual(aggregate["occupation_action_column_count"], 11538944)

    def test_18_selected_independent_action_digests_are_stable(self) -> None:
        self.assertEqual(
            self.records["L2_OBC"]["H1_r0_c0_up"]["action_stream_sha256"],
            "428fd65767f250938ee2b7ace73fcfb8786f4b40ef49a9c81e47e7a6b46fb2df",
        )
        self.assertEqual(
            self.records["L2_OBC"]["H1_r0_c0_down"]["dense_matrix_stream_sha256"],
            "01b33f48edf9f9d0cbe261f49b67389e20e2068e56fc86c8cf17b5ee4b760ef8",
        )
        self.assertEqual(
            self.records["L3_OBC"]["OBS_double_occupancy"]["action_stream_sha256"],
            "65d212071e71610e74e9c022519fa2bc3505d3c3c9c91530e8cd63554ef3e027",
        )

    def test_19_action_counts_and_digest_shapes_are_sane(self) -> None:
        self.assertEqual(self.profiles["L2_OBC"]["action_nonzero_output_count"], 2153)
        self.assertEqual(self.profiles["L3_OBC"]["action_nonzero_output_count"], 5371185)
        for profile in self.expected["profiles"]:
            self.assertEqual(
                profile["support_candidate_entry_count"],
                profile["occupation_action_column_count"],
            )
            for record in profile["operator_records"]:
                self.assertRegex(record["action_stream_sha256"], r"^[0-9a-f]{64}$")
                self.assertGreaterEqual(record["support_candidate_entry_count"], 1)

    def test_20_L2_enumerates_every_dense_bra_ket_entry(self) -> None:
        profile = self.profiles["L2_OBC"]
        expected_entries = 18 * 256 * 256
        self.assertTrue(profile["dense_matrix_enumeration"])
        self.assertEqual(profile["explicit_dense_matrix_entry_count"], expected_entries)
        self.assertEqual(profile["logical_dense_matrix_entry_count"], expected_entries)
        self.assertEqual(
            profile["algebraically_implied_outside_support_zero_entry_count"], 0
        )
        for record in profile["operator_records"]:
            self.assertEqual(record["explicit_dense_matrix_entry_count"], 256 * 256)
            self.assertRegex(record["dense_matrix_stream_sha256"], r"^[0-9a-f]{64}$")

    def test_21_L3_executes_candidate_actions_with_algebraic_zero_accounting(self) -> None:
        profile = self.profiles["L3_OBC"]
        dimension = 262144
        logical = 44 * dimension * dimension
        candidates = 44 * dimension
        self.assertFalse(profile["dense_matrix_enumeration"])
        self.assertEqual(profile["explicit_dense_matrix_entry_count"], 0)
        self.assertEqual(profile["logical_dense_matrix_entry_count"], logical)
        self.assertEqual(profile["support_candidate_entry_count"], candidates)
        self.assertEqual(
            profile["algebraically_implied_outside_support_zero_entry_count"],
            logical - candidates,
        )
        self.assertTrue(
            self.expected["scope"]["L3_all_ket_sparse_candidate_actions_verified"]
        )
        self.assertFalse(
            self.expected["scope"][
                "L3_outside_support_entries_individually_executed"
            ]
        )
        self.assertTrue(all(
            record["dense_matrix_stream_sha256"] == "NOT_ENUMERATED_BY_POLICY"
            for record in profile["operator_records"]
        ))

    def test_22_unique_composite_constituent_and_boundary_counts_match(self) -> None:
        expected = {
            "L2_OBC": (12, 28, 20),
            "L3_OBC": (33, 75, 51),
        }
        for profile_id, counts in expected.items():
            profile = self.profiles[profile_id]
            self.assertEqual(
                (
                    profile["unique_composite_count"],
                    profile["unique_constituent_count"],
                    profile["unique_truncation_boundary_count"],
                ),
                counts,
            )
            generators = [
                record for record in profile["operator_records"]
                if record["cadence"] is not None
            ]
            for record in generators:
                cadence = record["cadence"]
                constituent_masks = [
                    constituent["mask"] for constituent in cadence["constituents"]
                ]
                probe = cadence["execution_probe"]
                applied_masks = probe["applied_masks"]
                boundaries = probe["observed_boundaries"]

                self.assertEqual(
                    probe["wrapper_id"],
                    "sorted_zero_angle_identity_truncation_callback_v1",
                )
                self.assertEqual(applied_masks, sorted(constituent_masks))
                self.assertEqual(
                    probe["applied_masks_sha256"],
                    CHECKER.canonical_sha256(applied_masks),
                )
                self.assertEqual(
                    probe["observed_truncation_call_count"], len(boundaries)
                )
                self.assertEqual(
                    probe["observed_truncation_call_count"],
                    cadence["truncation_boundary_count"],
                )
                self.assertEqual(
                    [boundary["boundary_index"] for boundary in boundaries],
                    list(range(len(boundaries))),
                )
                self.assertTrue(
                    all(
                        boundary["identity_callback_delta"] == 1
                        for boundary in boundaries
                    )
                )
                self.assertEqual(
                    sum(
                        boundary["identity_callback_delta"]
                        for boundary in boundaries
                    ),
                    probe["observed_truncation_call_count"],
                )
                self.assertEqual(
                    probe["observed_boundaries_sha256"],
                    CHECKER.canonical_sha256(boundaries),
                )
                self.assertEqual(probe["final_identity_coefficient"], "1")
                self.assertEqual(
                    cadence["execution_probe_sha256"],
                    CHECKER.canonical_sha256(probe),
                )
                if record["symbol"] in ("hopup", "hopdn"):
                    self.assertFalse(cadence["truncate_after_each_constituent"])
                    self.assertEqual(cadence["truncation_boundary_count"], 1)
                    self.assertEqual(
                        [boundary["boundary_kind"] for boundary in boundaries],
                        ["after_complete_composite"],
                    )
                    self.assertEqual(
                        [
                            boundary["after_constituent_index"]
                            for boundary in boundaries
                        ],
                        [None],
                    )
                else:
                    self.assertTrue(cadence["truncate_after_each_constituent"])
                    self.assertEqual(cadence["truncation_boundary_count"], 3)
                    self.assertEqual(
                        [boundary["boundary_kind"] for boundary in boundaries],
                        ["after_constituent"] * cadence["constituent_count"],
                    )
                    self.assertEqual(
                        [
                            boundary["after_constituent_index"]
                            for boundary in boundaries
                        ],
                        list(range(cadence["constituent_count"])),
                    )

    def test_23_R2_occurrence_counts_and_identity_phases_are_exact(self) -> None:
        expected = {
            "L2_OBC": (48, 112, 80, "8"),
            "L3_OBC": (132, 300, 204, "18"),
        }
        for profile_id, values in expected.items():
            cadence = self.profiles[profile_id]["r2_cadence"]
            self.assertEqual(
                (
                    cadence["composite_occurrence_count"],
                    cadence["constituent_occurrence_count"],
                    cadence["truncation_boundary_count"],
                    cadence["omitted_identity_phase_exponent_in_exp_minus_i_x"],
                ),
                values,
            )

    def test_24_R2_keeps_raw_adjacent_H4_events_and_two_HU_phases(self) -> None:
        self.assertEqual(
            CHECKER.GROUP_ORDER,
            ("H1", "H2", "HU", "H3", "H4", "H4", "H3", "HU", "H2", "H1"),
        )
        self.assertEqual(CHECKER.GROUP_ORDER.count("HU"), 2)
        self.assertEqual(CHECKER.GROUP_ORDER[4:6], ("H4", "H4"))
        for linear_size, phase in ((2, "8"), (3, "18")):
            self.assertEqual(
                CHECKER._r2_cadence(CHECKER._operator_specs(linear_size))[
                    "omitted_identity_phase_exponent_in_exp_minus_i_x"
                ],
                phase,
            )

    def test_25_swapped_up_down_action_streams_are_rejected(self) -> None:
        mutant = copy.deepcopy(self.expected)
        records = mutant["profiles"][0]["operator_records"]
        up = next(row for row in records if row["operator_id"] == "H1_r0_c0_up")
        down = next(row for row in records if row["operator_id"] == "H1_r0_c0_down")
        for field in ("action_stream_sha256", "dense_matrix_stream_sha256"):
            up[field], down[field] = down[field], up[field]
        self.refresh_profile_digests(mutant, 0)
        self.assert_witness_rejected(mutant)

    def test_26_hopping_generator_sign_mutation_is_rejected(self) -> None:
        mutant = copy.deepcopy(self.expected)
        record = next(
            row for row in mutant["profiles"][0]["operator_records"]
            if row["operator_id"] == "H1_r0_c0_up"
        )
        record["physical_theta_multiplier"] = "1"
        for term in record["terms"]:
            term["coefficient"] = CHECKER.format_q(-CHECKER.parse_q(term["coefficient"]))
        record["terms_sha256"] = CHECKER.canonical_sha256(record["terms"])
        for constituent in record["cadence"]["constituents"]:
            constituent["physical_theta_multiplier"] = "1"
            constituent["effective_coefficient"] = CHECKER.format_q(
                -CHECKER.parse_q(constituent["effective_coefficient"])
            )
        record["cadence"]["constituents_sha256"] = CHECKER.canonical_sha256(
            record["cadence"]["constituents"]
        )
        self.refresh_profile_digests(mutant, 0)
        self.assert_witness_rejected(mutant)

    def test_27_nupndn_quartic_sign_mutation_is_rejected(self) -> None:
        mutant = copy.deepcopy(self.expected)
        record = next(
            row for row in mutant["profiles"][0]["operator_records"]
            if row["operator_id"] == "HU_r0_c0"
        )
        quartic = next(term for term in record["terms"] if term["mask"] == 15)
        self.assertEqual(quartic["coefficient"], "-2")
        quartic["coefficient"] = "2"
        record["terms_sha256"] = CHECKER.canonical_sha256(record["terms"])
        constituent = next(
            row for row in record["cadence"]["constituents"] if row["mask"] == 15
        )
        constituent["constructor_coefficient"] = "1/4"
        constituent["effective_coefficient"] = "2"
        record["cadence"]["constituents_sha256"] = CHECKER.canonical_sha256(
            record["cadence"]["constituents"]
        )
        self.refresh_profile_digests(mutant, 0)
        self.assert_witness_rejected(mutant)

    def test_28_hopping_per_constituent_cadence_mutation_is_rejected(self) -> None:
        mutant = copy.deepcopy(self.expected)
        record = next(
            row for row in mutant["profiles"][0]["operator_records"]
            if row["operator_id"] == "H1_r0_c0_up"
        )
        cadence = record["cadence"]
        cadence["truncate_after_each_constituent"] = True
        cadence["boundary_kind"] = "after_constituent"
        cadence["truncation_boundary_count"] = cadence["constituent_count"]
        self.refresh_profile_digests(mutant, 0)
        self.assert_witness_rejected(mutant)

    def test_29_omitted_zero_action_column_mutation_is_rejected(self) -> None:
        mutant = copy.deepcopy(self.expected)
        profile = mutant["profiles"][1]
        record = profile["operator_records"][0]
        record["action_column_count"] -= 1
        profile["occupation_action_column_count"] -= 1
        mutant["aggregate"]["occupation_action_column_count"] -= 1
        self.refresh_profile_digests(mutant, 1)
        self.assert_witness_rejected(mutant)

    def test_30_integer_boolean_type_confusion_is_rejected(self) -> None:
        mutant = copy.deepcopy(self.expected)
        self.assertEqual(mutant["schema_version"], 1)
        mutant["schema_version"] = True
        self.assert_witness_rejected(mutant)

    def test_31_fixture_mutation_is_rejected_before_oracle_use(self) -> None:
        mutant = copy.deepcopy(self.fixture)
        mutant["profiles"][1]["dense_matrix_enumeration"] = True
        with self.assertRaisesRegex(CHECKER.SchemaError, "frozen semantic object"):
            CHECKER.validate_fixture(mutant)

    def test_32_scope_is_fail_closed(self) -> None:
        scope = self.expected["scope"]
        self.assertEqual(scope["maximum_positive_status"], CHECKER.MAXIMUM_STATUS)
        self.assertTrue(scope["fixed_L2_L3_square_OBC_Hubbard_workload_only"])
        self.assertEqual(
            scope["arbitrary_MajoranaPropagation_constructors_or_circuits"],
            "NOT_CLAIMED",
        )
        self.assertEqual(scope["L8_full_propagation"], "NOT_ASSESSED")
        self.assertEqual(
            scope["product_formula_to_exact_Hubbard_error"], "NOT_ASSESSED"
        )
        self.assertEqual(scope["exact_time_evolution"], "NOT_ASSESSED")
        self.assertFalse(scope["physical_reference_qualified"])
        self.assertFalse(scope["ready_gate_eligible"])

    def test_33_policy_is_result_unpinned_and_stable_sources_are_locked(self) -> None:
        policy = CHECKER.load_json(BASE / CHECKER.POLICY_NAME)
        CHECKER.validate_policy(policy, self.runtime_lock, BASE)
        boundary = policy["precommit_boundary"]
        self.assertFalse(boundary["policy_contains_observed_replay_results"])
        self.assertFalse(boundary["policy_contains_witness_or_result_hashes"])
        self.assertFalse(boundary["policy_promises_a_terminal_branch"])
        self.assertEqual(tuple(policy["precommit_forbidden_paths"]), CHECKER.RESULT_ARTIFACTS)
        self.assertEqual(
            {row["relative_path"] for row in policy["source_pins"]},
            {
                CHECKER.FIXTURE_NAME,
                CHECKER.RUNTIME_LOCK_NAME,
                f"{CHECKER.PROJECT_DIRECTORY_NAME}/Project.toml",
                f"{CHECKER.PROJECT_DIRECTORY_NAME}/Manifest.toml",
            },
        )

    def test_34_policy_and_contract_semantic_mutations_fail_closed(self) -> None:
        policy = CHECKER.load_json(BASE / CHECKER.POLICY_NAME)
        policy_mutant = copy.deepcopy(policy)
        policy_mutant["maximum_positive_authority"]["claim"] = "expanded_authority"
        with self.assertRaisesRegex(CHECKER.SchemaError, "frozen semantic object"):
            CHECKER.validate_policy(policy_mutant, self.runtime_lock, BASE)

        contract = CHECKER.load_json(BASE / CHECKER.PRECOMMIT_CONTRACT_NAME)
        contract_mutant = copy.deepcopy(contract)
        contract_mutant["formal_replay"]["process_count"] = True
        with self.assertRaisesRegex(CHECKER.SchemaError, "formal replay contract"):
            CHECKER.validate_precommit_contract(contract_mutant, BASE)

    def test_35_precommit_contract_excludes_results_even_after_finalization(self) -> None:
        contract = CHECKER.load_json(BASE / CHECKER.PRECOMMIT_CONTRACT_NAME)
        CHECKER.validate_precommit_contract(contract, BASE)
        present = [
            artifact for artifact in CHECKER.RESULT_ARTIFACTS
            if (BASE / artifact).exists()
        ]
        if not present:
            self.assertTrue(all(not (BASE / artifact).exists() for artifact in CHECKER.RESULT_ARTIFACTS))
            return
        self.assertEqual(set(present), set(CHECKER.RESULT_ARTIFACTS))
        result = CHECKER.load_json(BASE / CHECKER.RESULT_CONTRACT_NAME)
        repo, base_relative = CHECKER._repo_and_base_relative(BASE)
        for artifact in CHECKER.RESULT_ARTIFACTS:
            precommit_path = (base_relative / artifact).as_posix()
            check = subprocess.run(
                [
                    "git", "cat-file", "-e",
                    f"{result['precommit_commit_sha']}:{precommit_path}",
                ],
                cwd=repo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(check.returncode, 0)

    def test_36_cli_selects_the_valid_precommit_or_final_branch(self) -> None:
        final = (BASE / CHECKER.RESULT_CONTRACT_NAME).exists()
        arguments = ["--verify-final"] if final else []
        output = io.StringIO()
        with redirect_stdout(output):
            returncode = CHECKER.main(arguments)
        self.assertEqual(returncode, 0)
        summary = CHECKER.strict_json_loads(output.getvalue().encode(), source="P1 CLI")
        if final:
            self.assertEqual(summary["status"], CHECKER.MAXIMUM_STATUS)
        else:
            self.assertEqual(
                summary["status"],
                "VERIFIED_MAJORANA_P1_RESULT_UNPINNED_PRECOMMIT_INPUTS",
            )
            self.assertEqual(summary["scope_ceiling"], CHECKER.MAXIMUM_STATUS)


if __name__ == "__main__":
    unittest.main()
