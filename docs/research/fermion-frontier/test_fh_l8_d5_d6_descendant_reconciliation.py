import copy
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
CHECKER = HERE / "fh_l8_d5_d6_descendant_reconciliation_checker.py"
MANIFEST = HERE / "fh_l8_d5_d6_descendant_reconciliation.json"
CHECKER_SHA256 = "4133a98f19f55db95b213fc6df8f4f0127b090152d1c1acd51e98794508a4fed"
MANIFEST_SHA256 = "4f169897212704091b120d1380782cc2a61c17de0d01611259e97a7cb99e852e"
SPEC = importlib.util.spec_from_file_location("fh_l8_d5_d6_r2", CHECKER)
R2 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(R2)


class D5D6DescendantReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = MANIFEST.read_bytes()
        cls.manifest = json.loads(cls.raw)
        cls.evidence = R2.recompute(cls.manifest)

    def test_frozen_identity_and_status(self):
        self.assertEqual(len(self.raw), 5537)
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), MANIFEST_SHA256)
        self.assertEqual(hashlib.sha256(CHECKER.read_bytes()).hexdigest(), CHECKER_SHA256)
        self.assertEqual(self.evidence["reconciliation_id"], R2.R2_ID)
        self.assertEqual(self.evidence["status"], R2.STATUS)
        self.assertTrue(self.evidence["verified"])

    def test_r1_and_d6_topology_are_bound(self):
        self.assertEqual(
            self.manifest["r1_snapshot"]["commit_record"]["commit"],
            R2.R1_COMMIT,
        )
        descendant = self.manifest["known_descendant"]
        self.assertEqual(descendant["outcome"]["commit"], R2.D6_OUTCOME_COMMIT)
        self.assertEqual(descendant["integration"]["commit"], R2.D6_INTEGRATION_COMMIT)
        self.assertFalse(descendant["preregistration_evidence"])
        self.assertEqual(descendant["resolved_parent_evidence_lane_alias"], R2.PREFIX_ALIAS)

    def test_support_orbit_result_is_complementary_not_quotient_h(self):
        descendant = self.manifest["known_descendant"]
        self.assertEqual(descendant["scope"], "full_depth3_signed_support_orbit_enumeration_only")
        self.assertEqual(descendant["result_status"], "VERIFIED_D6_BYTE_TABLE_SIGNED_D4_DEPTH3_ORBITS")
        self.assertTrue(descendant["selected_as_complementary_support_orbit_input"])
        self.assertEqual(
            descendant["performance_record"],
            {
                "maximum_seconds": 240,
                "within_cap": True,
                "exact_elapsed_seconds_retained_in_result": False,
            },
        )
        d6_result = json.loads(
            (HERE / "fh_l8_byte_table_orbit_d6_result.json").read_text(encoding="utf-8")
        )
        d5b_result = json.loads(
            (HERE / "fh_l8_symmetry_orbit_quotient_d5_result.json").read_text(encoding="utf-8")
        )
        self.assertEqual(d6_result["depth3_orbit"]["states"], 1704285)
        self.assertEqual(d6_result["depth3_orbit"]["orbits"], 213099)
        self.assertEqual(
            d6_result["depth3_orbit"]["orbits"],
            d5b_result["krylov_prefix"]["depth_records"][3]["orbit_representative_count"],
        )
        self.assertEqual(d6_result["fourth_layer_feasibility"], "NOT_EXECUTED_OR_CERTIFIED")

    def test_future_selection_requires_new_identity_and_both_scopes(self):
        selection = self.manifest["selection"]
        self.assertEqual(selection["required_full_quotient_semantics_route_alias"], R2.FULL_ALIAS)
        self.assertEqual(selection["complementary_support_orbit_route_alias"], R2.D6_ALIAS)
        self.assertEqual(
            selection["future_contract_id_policy"],
            "new_globally_unique_route_specific_id_required",
        )
        self.assertEqual(selection["occupied_legacy_contract_ids"], [R2.LEGACY_D5_ID, R2.LEGACY_D6_ID])
        self.assertFalse(selection["evidence_is_additive"])

    def test_current_authority_distinguishes_executed_support_from_unexecuted_h(self):
        authority = self.evidence["authority"]
        self.assertTrue(authority["byte_table_support_orbit_canonicalization_executed"])
        self.assertTrue(authority["full_depth3_support_orbit_count_verified"])
        self.assertTrue(authority["depth0_to_depth3_quotient_transitions_executed_and_verified"])
        self.assertTrue(authority["future_quotient_hamiltonian_design_eligible"])
        for claim in (
            "depth3_to_depth4_quotient_hamiltonian_action_executed",
            "depth3_to_depth4_execution_authorized",
            "fourth_hamiltonian_action_executed",
            "degree6_remainder_bounded",
            "two_step_cumulative_error_bounded",
            "full_R100_error_bounded",
            "physical_reference_qualified",
            "ready_gate_eligible",
        ):
            self.assertFalse(authority[claim])

    def test_parent_performance_artifact_and_authority_mutations_fail_closed(self):
        mutations = []
        parent = copy.deepcopy(self.manifest)
        parent["known_descendant"]["resolved_parent_evidence_lane_alias"] = R2.FULL_ALIAS
        mutations.append(parent)
        prereg = copy.deepcopy(self.manifest)
        prereg["known_descendant"]["preregistration_evidence"] = True
        mutations.append(prereg)
        timing = copy.deepcopy(self.manifest)
        timing["known_descendant"]["performance_record"]["exact_elapsed_seconds_retained_in_result"] = True
        mutations.append(timing)
        artifact = copy.deepcopy(self.manifest)
        artifact["known_descendant"]["artifacts"][0] = copy.deepcopy(
            artifact["known_descendant"]["artifacts"][1]
        )
        mutations.append(artifact)
        uplift = copy.deepcopy(self.manifest)
        uplift["authority"]["depth3_to_depth4_quotient_hamiltonian_action_executed"] = True
        mutations.append(uplift)
        r1 = copy.deepcopy(self.manifest)
        r1["r1_snapshot"]["artifacts"][1]["sha256"] = "0" * 64
        mutations.append(r1)
        for mutation in mutations:
            with self.assertRaises(R2.VerificationError):
                R2.recompute(mutation)


if __name__ == "__main__":
    unittest.main()
