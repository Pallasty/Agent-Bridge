import copy
import importlib.util
import json
import unittest
from unittest import mock
from pathlib import Path


HERE = Path(__file__).resolve().parent
CHECKER = HERE / "fh_l8_symmetry_orbit_quotient_d5_checker.py"
CONTRACT = HERE / "fh_l8_symmetry_orbit_quotient_d5_contract.json"
SPEC = importlib.util.spec_from_file_location("fh_l8_d5", CHECKER)
D5 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(D5)


class D5ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_is_design_only_and_result_unpinned(self):
        self.assertEqual(self.contract["contract_id"], D5.CONTRACT_ID)
        self.assertEqual(
            self.contract["workload"]["neel_basis_hex"],
            "0x66669999666699996666999966669999",
        )
        self.assertFalse(self.contract["workload"]["fourth_hamiltonian_action_authorized"])
        self.assertNotIn("observed_orbit_counts", self.contract)
        D5._validate_contract(self.contract)

    def test_checker_self_hash_and_coordinate_convention_are_bound(self):
        import hashlib

        self.assertEqual(
            hashlib.sha256(CHECKER.read_bytes()).hexdigest(),
            self.contract["checker_self_sha256"],
        )
        mutated = copy.deepcopy(self.contract)
        mutated["quotient_coordinates"]["orbit_average_coefficients_used"] = True
        with self.assertRaises(D5.VerificationError):
            D5._validate_contract(mutated)

    def test_bitboard_round_trip_and_one_hot_spatial_maps(self):
        fixtures = (0, 1, (1 << 64) - 1, 0x0123456789ABCDEF)
        for value in fixtures:
            self.assertEqual(D5._compact_even(D5._spread_even(value)), value)
        symmetries, record = D5._build_symmetries(self.contract)
        self.assertTrue(record["closure_pass"])
        self.assertEqual(len(symmetries), 8)

    def test_car_formula_matches_generic_wedge_action(self):
        symmetries, _ = D5._build_symmetries(self.contract)
        neel = int(self.contract["workload"]["neel_basis_hex"], 16)
        record = D5._verify_car_sign_rule(symmetries, neel)
        self.assertTrue(record["pass"])
        self.assertEqual(record["quadratic_pair_checks"], 8 * (128 * 127 // 2))
        self.assertTrue(record["spin_swap_doublon_phase_fixture_pass"])
        self.assertTrue(record["negative_stabilizer_projection_fixture_pass"])
        self.assertEqual(record["cocycle_checks"], 7 * 8 * 8)

    def test_all_apparent_gates_only_authorize_d6_design(self):
        gates = {"semantic": True, "equivalence": True}
        metrics = {
            "orbit_representatives": 100,
            "next_action_upper_bound": 22500,
            "audit_group_actions": 800,
        }
        decision = D5.decide(gates, metrics, self.contract["resource_limits"])
        self.assertEqual(decision["status"], D5.PASS_STATUS)
        self.assertTrue(decision["d6_design_eligible"])
        self.assertFalse(decision["d6_execution_authorized"])

    def test_every_semantic_gate_fails_closed(self):
        base = {"group": True, "car": True, "equivalence": True}
        metrics = {
            "orbit_representatives": 100,
            "next_action_upper_bound": 22500,
            "audit_group_actions": 800,
        }
        for key in base:
            gates = copy.deepcopy(base)
            gates[key] = False
            self.assertEqual(
                D5.decide(gates, metrics, self.contract["resource_limits"])["status"],
                D5.SEMANTIC_NO_GO,
            )

    def test_each_resource_cap_fails_closed(self):
        gates = {"semantic": True}
        limits = self.contract["resource_limits"]
        cases = (
            {"orbit_representatives": limits["max_orbit_representatives"] + 1, "next_action_upper_bound": 1, "audit_group_actions": 1},
            {"orbit_representatives": 1, "next_action_upper_bound": limits["max_next_action_candidates"] + 1, "audit_group_actions": 1},
            {"orbit_representatives": 1, "next_action_upper_bound": 1, "audit_group_actions": limits["max_audit_group_actions"] + 1},
        )
        for metrics in cases:
            self.assertEqual(D5.decide(gates, metrics, limits)["status"], D5.RESOURCE_NO_GO)

    def test_unbounded_outer_envelope_is_rejected(self):
        with self.assertRaises(D5.VerificationError):
            D5._parse_cgroup_limit("max", "memory.max")
        self.assertEqual(D5._parse_cgroup_limit("1073741824", "memory.max"), 1073741824)

    def test_semantic_no_go_is_reachable_from_official_evaluate_path(self):
        failure = D5.SemanticNoGo("fixture_gate", "fixture semantic failure")
        expected = {"status": D5.SEMANTIC_NO_GO}
        with mock.patch.object(D5, "recompute", side_effect=failure), mock.patch.object(
            D5, "_failure_evidence", return_value=expected
        ):
            self.assertEqual(D5.evaluate(self.contract, "0" * 40), expected)

    def test_parent_source_pin_mutation_fails_closed(self):
        mutated = copy.deepcopy(self.contract)
        mutated["source_pins"][0]["sha256"] = "0" * 64
        with self.assertRaises(D5.VerificationError):
            D5._verify_parent_sources(mutated)


if __name__ == "__main__":
    unittest.main()
