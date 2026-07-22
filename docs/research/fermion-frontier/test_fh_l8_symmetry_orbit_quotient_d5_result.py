import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
CHECKER = HERE / "fh_l8_symmetry_orbit_quotient_d5_checker.py"
CONTRACT = HERE / "fh_l8_symmetry_orbit_quotient_d5_contract.json"
RESULT = HERE / "fh_l8_symmetry_orbit_quotient_d5_result.json"
PROTOCOL_COMMIT = "6daf30daeeb375962b9986af5df91517d8a4a8ec"
PROTOCOL_TREE = "9c7096bca41a1da8c440f37d93a08a4f51e5cef0"
RESULT_SHA256 = "a04a4d0be6265dcaf9d39c7937fc133d19c7a2050e1434c7cb24be88b795baed"

SPEC = importlib.util.spec_from_file_location("fh_l8_d5_result", CHECKER)
D5 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(D5)


class D5FrozenResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.raw_result = RESULT.read_bytes()
        cls.result = json.loads(cls.raw_result)

    def test_frozen_result_identity_and_chronology(self):
        self.assertEqual(len(self.raw_result), 9319)
        self.assertEqual(hashlib.sha256(self.raw_result).hexdigest(), RESULT_SHA256)
        self.assertEqual(self.result["contract_id"], D5.CONTRACT_ID)
        self.assertEqual(self.result["status"], D5.PASS_STATUS)
        self.assertTrue(self.result["verified"])
        self.assertEqual(
            self.result["protocol_freeze"],
            {"commit": PROTOCOL_COMMIT, "tree": PROTOCOL_TREE},
        )
        self.assertEqual(
            D5._verify_protocol_commit(self.contract, PROTOCOL_COMMIT),
            self.result["protocol_freeze"],
        )
        self.assertEqual(
            self.result["parent"],
            {
                "contract_id": "FH-L8-INDEPENDENT-REFERENCE-D4",
                "integration_commit": "6ff83b850ee4e2995d1bec89c7519d01c9c92e47",
                "integration_tree": "17ac5ffb333878312ecf59cffc83c045e2e761fd",
                "source_pins_pass": True,
            },
        )

    def test_frozen_result_counts_and_resources(self):
        depth_records = self.result["krylov_prefix"]["depth_records"]
        self.assertEqual(
            [
                (
                    item["depth"],
                    item["full_state_count"],
                    item["orbit_representative_count"],
                    item["deterministic_insertion_order_quotient_sha256"],
                )
                for item in depth_records
            ],
            [
                (0, 1, 1, "431986141713c9cb8e6f4852a6a72b9b189bfe403156b1878561901f2dee0e59"),
                (1, 225, 29, "73c176baffbd66ddb01949011660d97f8a0aaaa4549986dd9df04a55b6a23e98"),
                (2, 24421, 3116, "3cfea6381641bea908a486a04af793faab676f35f046de6815f5da2b26f4f3f3"),
                (3, 1704285, 213099, "7230d8bd0e726535cb5da01bc191313b25e38b83a6b809a7e6e39823a418757e"),
            ],
        )
        for item in depth_records:
            self.assertEqual(item["amplitude_relation_checks"], 8 * item["full_state_count"])
            self.assertEqual(item["coverage_sum"], item["full_state_count"])
            self.assertEqual(item["projected_zero_nonzero_states"], 0)

        transitions = self.result["krylov_prefix"]["quotient_transition_records"]
        self.assertEqual(
            [
                (
                    item["source_depth"],
                    item["target_depth"],
                    item["source_representative_count"],
                    item["candidate_action_upper_bound"],
                    item["nonzero_reduced_column_outputs"],
                    item["projected_zero_action_outputs"],
                )
                for item in transitions
            ],
            [
                (0, 1, 1, 225, 29, 0),
                (1, 2, 29, 6525, 6142, 13),
                (2, 3, 3116, 701100, 655449, 13),
            ],
        )
        self.assertTrue(all(item["matches_next_full_quotient"] for item in transitions))
        for item in transitions:
            self.assertEqual(
                item["candidate_action_upper_bound"],
                225 * item["source_representative_count"],
            )

        resources = self.result["resource_projection"]
        self.assertEqual(resources["orbit_representatives"], 213099)
        self.assertEqual(resources["next_action_upper_bound"], 213099 * 225)
        self.assertEqual(
            resources["next_action_orbit_transform_upper_bound"],
            8 * resources["next_action_upper_bound"],
        )
        self.assertEqual(resources["audit_group_actions"], 13831456)
        self.assertEqual(resources["limits"], self.contract["resource_limits"])
        self.assertLessEqual(
            resources["next_action_upper_bound"],
            resources["limits"]["max_next_action_candidates"],
        )
        self.assertGreater(
            resources["next_action_orbit_transform_upper_bound"],
            resources["limits"]["max_next_action_candidates"],
        )
        self.assertEqual(
            self.result["resource_envelope"],
            {
                "cgroup_v2_enforced": True,
                "internal_deadline_seconds": 600,
                "memory_max_bytes": 1073741824,
                "memory_swap_max_bytes": 0,
                "pass": True,
            },
        )
        self.assertTrue(all(self.result["decision"]["resource_gates"].values()))

    def test_frozen_result_authority_and_nonclaims(self):
        self.assertEqual(
            self.result["semantic_gates"],
            {
                "car_sign_rule": True,
                "fourth_action_not_executed": True,
                "full_orbit_relations": True,
                "group_closure": True,
                "hamiltonian_equivariance": True,
                "initial_and_observable_characters": True,
                "quotient_transition_equivalence_depths_0_1_2": True,
            },
        )
        authority = self.result["authority"]
        self.assertTrue(authority["d6_design_eligible"])
        for claim in (
            "d6_execution_authorized",
            "fourth_hamiltonian_action_executed",
            "degree6_remainder_bounded",
            "two_step_cumulative_error_bounded",
            "full_R100_error_bounded",
            "physical_reference_qualified",
            "ready_gate_eligible",
        ):
            self.assertFalse(authority[claim])
        self.assertFalse(self.result["decision"]["d6_execution_authorized"])
        self.assertEqual(self.result["limitations"], self.contract["forbidden_claims"])


if __name__ == "__main__":
    unittest.main()
