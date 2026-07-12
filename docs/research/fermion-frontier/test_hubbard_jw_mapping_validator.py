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


VALIDATOR = load_module(
    "hubbard_jw_mapping_validator", "hubbard_jw_mapping_validator.py"
)
L2_WITNESS = load_module(
    "hubbard_jw_mapping_test_l2_witness", "operator_propagation_l2_witness.py"
)


def load_json(name):
    with (HERE / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class HubbardJWMappingValidatorTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_json("hubbard_jw_mapping_contract.json")
        self.certificate = load_json("hubbard_jw_mapping_template.json")

    def verify(self, contract=None, certificate=None):
        return VALIDATOR.verify_certificate(
            self.contract if contract is None else contract,
            self.certificate if certificate is None else certificate,
        )

    def test_template_verifies_only_canonical_mapping_scope(self):
        result = self.verify()
        self.assertEqual(
            result["status"], "VERIFIED_CANONICAL_JW_MAPPING_SUBCERTIFICATE"
        )
        self.assertTrue(result["verified"])
        self.assertFalse(result["ready_gate_eligible"])
        self.assertEqual(result["profile_count"], 2)
        self.assertTrue(
            result["scope_claims"][
                "source_pinned_L2_witness_gate_sequence_verified"
            ]
        )
        self.assertEqual(
            result["scope_claims"]["product_formula_to_exact_hamiltonian"],
            "NOT_ASSESSED",
        )
        self.assertEqual(
            result["scope_claims"]["physical_L8_instance_identity"],
            "NOT_ASSESSED",
        )

    def test_positive_result_recomputes_fixed_counts_not_certificate_counts(self):
        result = self.verify()
        l2, l3 = result["recomputed_profiles"]
        self.assertEqual(
            (l2["canonical_term_count"], l3["canonical_term_count"]), (32, 84)
        )
        self.assertEqual(
            (l2["raw_term_rotation_count_including_identity"],
             l3["raw_term_rotation_count_including_identity"]),
            (128, 336),
        )
        self.assertEqual(
            (l2["selected_sign_witness_count"], l3["selected_sign_witness_count"]),
            (64, 192),
        )
        self.assertEqual(
            (l2["onsite_basis_witness_count"], l3["onsite_basis_witness_count"]),
            (16, 36),
        )

    def test_cli_verified_subcertificate_still_exits_one(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(HERE / "hubbard_jw_mapping_validator.py"),
                str(HERE / "hubbard_jw_mapping_contract.json"),
                str(HERE / "hubbard_jw_mapping_template.json"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("VERIFIED_CANONICAL_JW_MAPPING_SUBCERTIFICATE", completed.stdout)
        self.assertIn('"ready_gate_eligible": false', completed.stdout)

    def test_contract_pins_exact_checker_and_all_cross_source_dependencies(self):
        self.assertEqual(VALIDATOR.validate_contract(self.contract), [])
        self.assertEqual(
            self.contract["checker_source_sha256"],
            hashlib.sha256(
                (HERE / "hubbard_jw_mapping_validator.py").read_bytes()
            ).hexdigest(),
        )
        pinned_paths = {pin["relative_path"] for pin in self.contract["source_pins"]}
        self.assertEqual(
            pinned_paths,
            {
                "fermi_hubbard_l2_pilot.py",
                "term_order_contract.json",
                "operator_propagation_l2_witness.py",
                "operator_propagation_certificate_checker.py",
            },
        )
        for pin in self.contract["source_pins"]:
            self.assertEqual(
                pin["sha256"], hashlib.sha256((HERE / pin["relative_path"]).read_bytes()).hexdigest()
            )

    def test_checker_source_hash_drift_is_invalid_contract(self):
        bad = copy.deepcopy(self.contract)
        bad["checker_source_sha256"] = "0" * 64
        result = self.verify(contract=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("checker_source_sha256" in error for error in result["errors"]))
        with mock.patch.object(
            VALIDATOR, "checker_source_sha256", side_effect=OSError("source missing")
        ):
            result = self.verify()
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["verified"])
        self.assertFalse(result["ready_gate_eligible"])

    def test_cross_source_pin_drift_is_invalid_contract(self):
        bad = copy.deepcopy(self.contract)
        bad["source_pins"][2]["sha256"] = "0" * 64
        result = self.verify(contract=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("source_pins" in error for error in result["errors"]))

    def test_l2_gate_sequence_exactly_matches_existing_pinned_witness(self):
        canonical = VALIDATOR.canonical_nonidentity_gate_sequence(2)
        existing = L2_WITNESS.build_forward_gate_sequence()
        self.assertEqual(canonical, existing)
        self.assertEqual(len(canonical), 112)
        digest = VALIDATOR.verify_pinned_l2_witness_sequence()
        self.assertEqual(
            digest,
            self.contract["expected_profiles"][0][
                "nonidentity_gate_sequence_sha256"
            ],
        )

    def test_l2_cross_source_difference_is_runtime_hard_failure(self):
        with mock.patch.object(
            VALIDATOR, "canonical_nonidentity_gate_sequence", return_value=[]
        ):
            with self.assertRaisesRegex(
                VALIDATOR.VerificationError, "disagrees"
            ):
                VALIDATOR.verify_pinned_l2_witness_sequence()

    def test_late_cross_source_failure_returns_cleared_api_result_not_exception(self):
        digest = self.contract["expected_profiles"][0][
            "nonidentity_gate_sequence_sha256"
        ]
        with mock.patch.object(
            VALIDATOR,
            "verify_pinned_l2_witness_sequence",
            side_effect=[digest, VALIDATOR.VerificationError("late pinned mismatch")],
        ):
            result = self.verify()
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertFalse(result["verified"])
        self.assertFalse(result["ready_gate_eligible"])
        self.assertFalse(
            result["scope_claims"][
                "source_pinned_L2_witness_gate_sequence_verified"
            ]
        )
        self.assertIn("late pinned mismatch", result["errors"])

    def test_group_matching_sizes_cover_l2_and_nonempty_l3_odd_groups(self):
        l2 = VALIDATOR.canonical_bonds(2)
        l3 = VALIDATOR.canonical_bonds(3)
        counts2 = {
            group: sum(bond["group"] == group for bond in l2)
            for group in ("H1", "H2", "H3", "H4")
        }
        counts3 = {
            group: sum(bond["group"] == group for bond in l3)
            for group in ("H1", "H2", "H3", "H4")
        }
        self.assertEqual(counts2, {"H1": 4, "H2": 0, "H3": 0, "H4": 4})
        self.assertEqual(counts3, {"H1": 6, "H2": 6, "H3": 6, "H4": 6})
        self.assertGreater(counts3["H2"], 0)
        self.assertGreater(counts3["H3"], 0)

    def test_bonds_are_obc_site_major_spin_minor_and_never_wrap(self):
        for linear_size in (2, 3):
            for bond in VALIDATOR.canonical_bonds(linear_size):
                (r1, c1), (r2, c2) = bond["left_site"], bond["right_site"]
                self.assertEqual(abs(r1 - r2) + abs(c1 - c2), 1)
                spin = 0 if bond["spin"] == "up" else 1
                self.assertEqual(
                    bond["modes"],
                    [
                        2 * (r1 * linear_size + c1) + spin,
                        2 * (r2 * linear_size + c2) + spin,
                    ],
                )
                self.assertTrue(0 <= r1 < linear_size and 0 <= c1 < linear_size)
                self.assertTrue(0 <= r2 < linear_size and 0 <= c2 < linear_size)

    def test_hopping_terms_have_minus_half_xx_yy_and_interior_z_string(self):
        bond = next(
            bond
            for bond in VALIDATOR.canonical_bonds(3)
            if bond["group"] == "H4" and bond["spin"] == "up"
        )
        terms = VALIDATOR._hopping_terms(3, bond)
        self.assertEqual([term["coefficient"] for term in terms], ["-1/2", "-1/2"])
        left, right = bond["modes"]
        for axis, term in zip("XY", terms):
            self.assertEqual(term["pauli"][left], axis)
            self.assertEqual(term["pauli"][right], axis)
            self.assertEqual(term["pauli"][left + 1:right], "Z" * (right - left - 1))

    def test_unshifted_onsite_mapping_includes_identity_and_exact_coefficients(self):
        onsite = [
            term for term in VALIDATOR.canonical_terms(2)
            if term["group"] == "HU" and term["site"] == [0, 0]
        ]
        self.assertEqual(
            [(term["component"], term["coefficient"]) for term in onsite],
            [("I", "2/1"), ("Zup", "-2/1"), ("Zdown", "-2/1"), ("ZZ", "2/1")],
        )
        self.assertEqual(onsite[0]["pauli"], "I" * 8)
        self.assertEqual(onsite[3]["pauli"][:2], "ZZ")

    def test_onsite_basis_witnesses_recompute_00_10_01_11_energies(self):
        for linear_size in (2, 3):
            witnesses = VALIDATOR.onsite_basis_witnesses(linear_size)
            self.assertEqual(len(witnesses), 4 * linear_size * linear_size)
            for site in range(linear_size * linear_size):
                site_items = witnesses[4 * site:4 * site + 4]
                self.assertEqual(
                    [item["case"] for item in site_items],
                    ["empty", "up_only", "down_only", "double"],
                )
                self.assertEqual(
                    [item["recomputed_energy"] for item in site_items],
                    ["0/1", "0/1", "0/1", "8/1"],
                )
                self.assertTrue(
                    all(
                        item["recomputed_energy"] == item["expected_energy"]
                        for item in site_items
                    )
                )

    def test_onsite_coefficient_sign_tamper_fails_independent_basis_check(self):
        original = VALIDATOR._onsite_terms

        def bad_terms(linear_size):
            terms = original(linear_size)
            terms[1]["coefficient"] = "2/1"
            return terms

        with mock.patch.object(VALIDATOR, "_onsite_terms", side_effect=bad_terms):
            with self.assertRaisesRegex(
                VALIDATOR.VerificationError, "onsite occupation energy mismatch"
            ):
                VALIDATOR.onsite_basis_witnesses(2)

    def test_raw_strang_events_preserve_group_order_and_duplicate_boundaries(self):
        events = VALIDATOR.raw_strang_events(3)
        self.assertEqual(len(events), 20)
        for step in range(2):
            groups = [event["group"] for event in events[10 * step:10 * (step + 1)]]
            self.assertEqual(groups, list(VALIDATOR.GROUP_ORDER))
            self.assertEqual(groups[4:6], ["H4", "H4"])
        self.assertEqual(events[9]["group"], "H1")
        self.assertEqual(events[10]["group"], "H1")
        self.assertEqual([event["raw_event_index"] for event in events], list(range(20)))

    def test_raw_rotation_theta_is_recomputed_from_duration_and_coefficient(self):
        for event in VALIDATOR.raw_strang_events(2):
            self.assertEqual(event["duration"], "1/4")
            for term in event["terms"]:
                coefficient = VALIDATOR.parse_fraction(term["hamiltonian_coefficient"])
                self.assertEqual(
                    VALIDATOR.parse_fraction(term["rotation_theta"]),
                    2 * Fraction(1, 4) * coefficient,
                )

    def test_identity_global_phase_ledger_is_explicit_and_exact(self):
        l2, l3 = VALIDATOR.expected_profile_summaries()
        self.assertEqual(
            (l2["raw_identity_rotation_count"], l3["raw_identity_rotation_count"]),
            (16, 36),
        )
        self.assertEqual(
            l2["global_phase_ledger"],
            {
                "identity_rotation_theta_sum": "16/1",
                "phase_exponent_in_exp_minus_i_x": "8/1",
                "status": "IDENTITY_RETAINED_IN_RAW_EVENTS_NONIDENTITY_VIEW_ONLY_OMITS_GLOBAL_PHASE",
            },
        )
        self.assertEqual(l3["global_phase_ledger"]["phase_exponent_in_exp_minus_i_x"], "18/1")

    def test_nonidentity_view_only_omits_identity_and_matches_112_gate_source(self):
        raw = VALIDATOR.raw_strang_events(2)
        self.assertEqual(sum(len(event["terms"]) for event in raw), 128)
        gates = VALIDATOR.canonical_nonidentity_gate_sequence(2)
        self.assertEqual(len(gates), 112)
        self.assertTrue(all(set(gate["pauli"]) != {"I"} for gate in gates))

    def test_every_selected_car_and_pauli_action_matches_exactly(self):
        for linear_size, expected_count in ((2, 64), (3, 192)):
            witnesses = VALIDATOR.selected_sign_witnesses(linear_size)
            self.assertEqual(len(witnesses), expected_count)
            self.assertTrue(
                all(item["car_action"] == item["jw_pauli_action"] for item in witnesses)
            )

    def test_external_spectator_cases_cover_prefix_and_suffix_without_changing_hop(self):
        witnesses = VALIDATOR.selected_sign_witnesses(3)
        external = [
            item for item in witnesses if "external_spectator" in item["case"]
        ]
        self.assertEqual(len(external), 48)
        prefix_seen = suffix_seen = False
        bond_by_id = {bond["bond_id"]: bond for bond in VALIDATOR.canonical_bonds(3)}
        for item in external:
            left, right = bond_by_id[item["bond_id"]]["modes"]
            occupied = {
                index for index, bit in enumerate(item["source_bits_q0_first"])
                if bit == "1"
            }
            outside = occupied - set(range(left, right + 1))
            self.assertEqual(len(outside), 1)
            spectator = next(iter(outside))
            prefix_seen |= spectator < left
            suffix_seen |= spectator > right
            self.assertEqual(len(item["car_action"]), 1)
        self.assertTrue(prefix_seen)
        self.assertTrue(suffix_seen)

    def test_even_and_odd_jw_parity_flip_hopping_sign(self):
        bond = VALIDATOR.canonical_bonds(3)[0]
        left, right = bond["modes"]
        even = VALIDATOR.car_hopping_action(1 << right, 18, left, right)
        odd = VALIDATOR.car_hopping_action(
            (1 << right) | (1 << (left + 1)), 18, left, right
        )
        even_amplitude = next(iter(even.values()))
        odd_amplitude = next(iter(odd.values()))
        self.assertEqual(even_amplitude, (Fraction(-1), Fraction(0)))
        self.assertEqual(odd_amplitude, (Fraction(1), Fraction(0)))
        self.assertEqual(even, VALIDATOR.jw_pauli_hopping_action(1 << right, 18, left, right))
        self.assertEqual(
            odd,
            VALIDATOR.jw_pauli_hopping_action(
                (1 << right) | (1 << (left + 1)), 18, left, right
            ),
        )

    def test_empty_and_double_occupied_endpoints_cancel_exactly(self):
        left, right = 0, 2
        for source in (1 << 1, (1 << left) | (1 << 1) | (1 << right)):
            self.assertEqual(VALIDATOR.car_hopping_action(source, 8, left, right), {})
            self.assertEqual(VALIDATOR.jw_pauli_hopping_action(source, 8, left, right), {})

    def test_pauli_y_basis_phase_convention_is_exact(self):
        self.assertEqual(VALIDATOR.pauli_basis_action("Y", 0), (1, (0, 1)))
        self.assertEqual(VALIDATOR.pauli_basis_action("Y", 1), (0, (0, -1)))
        self.assertEqual(VALIDATOR.pauli_basis_action("YY", 0), (3, (-1, 0)))

    def test_public_generators_reject_bool_and_out_of_profile_size(self):
        for value in (True, 1, 4):
            with self.subTest(value=value):
                with self.assertRaises(VALIDATOR.SchemaError):
                    VALIDATOR.canonical_bonds(value)
        with self.assertRaises(VALIDATOR.SchemaError):
            VALIDATOR.car_hopping_action(True, 8, 0, 2)

    def test_claimed_count_tamper_is_verification_failure(self):
        bad = copy.deepcopy(self.certificate)
        bad["profile_claims"][0]["canonical_term_count"] = 31
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertTrue(any("recomputation" in error for error in result["errors"]))

    def test_claimed_hash_tamper_is_verification_failure(self):
        bad = copy.deepcopy(self.certificate)
        bad["profile_claims"][1]["canonical_terms_sha256"] = "0" * 64
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")

    def test_contract_cannot_repin_tampered_profile_claim(self):
        contract = copy.deepcopy(self.contract)
        certificate = copy.deepcopy(self.certificate)
        contract["expected_profiles"][0]["canonical_term_count"] = 31
        certificate["profile_claims"][0]["canonical_term_count"] = 31
        result = self.verify(contract=contract, certificate=certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("expected_profiles" in error for error in result["errors"]))

    def test_profile_omission_reorder_and_unknown_profile_fail_closed(self):
        omitted = copy.deepcopy(self.certificate)
        omitted["profile_claims"] = omitted["profile_claims"][:1]
        self.assertEqual(self.verify(certificate=omitted)["status"], "INVALID_SCHEMA")
        reordered = copy.deepcopy(self.certificate)
        reordered["profile_claims"].reverse()
        self.assertEqual(self.verify(certificate=reordered)["status"], "INVALID_SCHEMA")
        unknown = copy.deepcopy(self.certificate)
        unknown["profile_claims"][0]["profile_id"] = "L8_OBC"
        self.assertEqual(self.verify(certificate=unknown)["status"], "INVALID_SCHEMA")

    def test_bool_schema_extra_keys_and_nonobject_top_levels_fail_closed(self):
        bad = copy.deepcopy(self.certificate)
        bad["schema_version"] = True
        self.assertEqual(self.verify(certificate=bad)["status"], "INVALID_SCHEMA")
        bad = copy.deepcopy(self.certificate)
        bad["schema_version"] = 1.0
        self.assertEqual(self.verify(certificate=bad)["status"], "INVALID_SCHEMA")
        bad_contract = copy.deepcopy(self.contract)
        bad_contract["schema_version"] = 1.0
        self.assertEqual(self.verify(contract=bad_contract)["status"], "INVALID_SCHEMA")
        bad = copy.deepcopy(self.certificate)
        bad["profile_claims"][0]["canonical_term_count"] = True
        self.assertEqual(self.verify(certificate=bad)["status"], "INVALID_SCHEMA")
        bad = copy.deepcopy(self.certificate)
        bad["unexpected"] = 1
        self.assertEqual(self.verify(certificate=bad)["status"], "INVALID_SCHEMA")
        self.assertEqual(self.verify(certificate=[])["status"], "INVALID_SCHEMA")
        self.assertEqual(self.verify(contract=[], certificate={})["status"], "INVALID_SCHEMA")

    def test_scope_overclaim_is_invalid_and_failed_scope_flags_are_cleared(self):
        bad = copy.deepcopy(self.certificate)
        bad["scope_claims"]["ready_gate_eligible"] = True
        result = self.verify(certificate=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["ready_gate_eligible"])
        self.assertFalse(
            result["scope_claims"][
                "canonical_JW_hopping_selected_basis_actions_verified"
            ]
        )
        self.assertFalse(
            result["scope_claims"][
                "source_pinned_L2_witness_gate_sequence_verified"
            ]
        )

    def test_fraction_parser_requires_reduced_canonical_rationals(self):
        self.assertEqual(VALIDATOR.parse_fraction("-3/7"), Fraction(-3, 7))
        for value in (True, 1, 0.5, "2/2", "0/2", "1/-2", "1/0", "1"):
            with self.subTest(value=value):
                with self.assertRaises(VALIDATOR.SchemaError):
                    VALIDATOR.parse_fraction(value)

    def test_canonical_hash_is_deterministic_and_rejects_nonfinite(self):
        value = {"b": [2, 3], "a": 1}
        self.assertEqual(VALIDATOR.canonical_sha256(value), VALIDATOR.canonical_sha256(value))
        with self.assertRaises(VALIDATOR.SchemaError):
            VALIDATOR.canonical_sha256({"x": float("nan")})

    def test_strict_json_rejects_duplicate_nonfinite_utf8_and_oversize(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"x":1,"x":2}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                VALIDATOR.load_strict_json(duplicate)
            nonfinite = root / "nonfinite.json"
            nonfinite.write_text('{"x":NaN}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-finite"):
                VALIDATOR.load_strict_json(nonfinite)
            invalid_utf8 = root / "utf8.json"
            invalid_utf8.write_bytes(b'{"x":"\xff"}')
            with self.assertRaises(UnicodeDecodeError):
                VALIDATOR.load_strict_json(invalid_utf8)
            oversized = root / "oversized.json"
            oversized.write_bytes(b"{" + b" " * 64 + b"}")
            with self.assertRaisesRegex(ValueError, "exceeds byte cap"):
                VALIDATOR.load_strict_json(oversized, 8)
        if pathlib.Path("/dev/zero").exists():
            with self.assertRaisesRegex(ValueError, "exceeds byte cap"):
                VALIDATOR.load_strict_json(pathlib.Path("/dev/zero"), 8)


if __name__ == "__main__":
    unittest.main()
