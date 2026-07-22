import copy
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
CHECKER = HERE / "fh_l8_d5_dual_track_reconciliation_checker.py"
MANIFEST = HERE / "fh_l8_d5_dual_track_reconciliation.json"
MANIFEST_SHA256 = "8274a8771f9c744e7392c1af28f7b997febc3b76bbf91813672f005c64004ce9"
SPEC = importlib.util.spec_from_file_location("fh_l8_d5_reconciliation", CHECKER)
R1 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(R1)


class D5DualTrackReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.evidence = R1.recompute(cls.manifest)

    def test_checker_identity_and_reconciliation_status(self):
        raw_manifest = MANIFEST.read_bytes()
        self.assertEqual(len(raw_manifest), 6232)
        self.assertEqual(hashlib.sha256(raw_manifest).hexdigest(), MANIFEST_SHA256)
        self.assertEqual(
            hashlib.sha256(CHECKER.read_bytes()).hexdigest(),
            self.manifest["checker_self_sha256"],
        )
        self.assertEqual(self.evidence["status"], R1.STATUS)
        self.assertTrue(self.evidence["verified"])

    def test_parallel_history_and_preregistration_are_explicit(self):
        prefix, full = self.manifest["routes"]
        self.assertEqual(prefix["outcome"]["parents"], [self.manifest["common_base"]["commit"]])
        self.assertEqual(full["protocol_freeze"]["parents"], [self.manifest["common_base"]["commit"]])
        self.assertEqual(full["outcome"]["parents"], [full["protocol_freeze"]["commit"]])
        self.assertFalse(prefix["preregistration_evidence"])
        self.assertTrue(full["preregistration_evidence"])
        self.assertEqual(
            self.manifest["integration"]["parents"],
            ["64438c47be710835626dea0ceb2521b6634951dc", full["outcome"]["commit"]],
        )

    def test_legacy_id_requires_unique_lane_alias_and_full_artifact_identity(self):
        self.assertEqual(
            {route["legacy_contract_id"] for route in self.manifest["routes"]},
            {R1.LEGACY_ID},
        )
        self.assertEqual(
            self.evidence["route_aliases"],
            [R1.PREFIX_ALIAS, R1.FULL_ALIAS],
        )
        collision = self.manifest["identity_collision"]
        self.assertTrue(collision["bare_legacy_contract_id_forbidden"])
        self.assertEqual(
            collision["required_lookup_identity"],
            "route_alias+artifact_path+git_blob+raw_sha256+bytes+commit",
        )
        for route in self.manifest["routes"]:
            self.assertEqual(len(route["artifacts"]), 3)
            for artifact in route["artifacts"]:
                self.assertEqual(set(artifact), {"path", "mode", "blob", "bytes", "sha256"})

    def test_full_lane_closes_only_the_unmeasured_scope(self):
        prefix, full = self.manifest["routes"]
        self.assertEqual(prefix["authority_ceiling"], "HISTORICAL_PARTIAL_PREFIX_AND_CUSTODY")
        self.assertFalse(prefix["downstream_design_selected"])
        self.assertEqual(full["authority_ceiling"], "D6_DESIGN_ELIGIBLE_ONLY")
        self.assertTrue(full["downstream_design_selected"])
        self.assertFalse(self.manifest["selection"]["evidence_is_additive"])
        self.assertEqual(
            self.manifest["selection"]["relation"],
            "full_lane_closes_unmeasured_full_depth3_and_quotient_transition_gaps_without_retroactive_prefix_validation",
        )
        self.assertEqual(len(self.manifest["non_equivalences"]), 3)

    def test_reconciled_authority_stays_design_only(self):
        authority = self.evidence["authority"]
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

    def test_identity_selection_and_authority_mutations_fail_closed(self):
        mutations = []
        bare = copy.deepcopy(self.manifest)
        bare["identity_collision"]["bare_legacy_contract_id_forbidden"] = False
        mutations.append(bare)
        selected = copy.deepcopy(self.manifest)
        selected["selection"]["downstream_design_route_alias"] = R1.PREFIX_ALIAS
        mutations.append(selected)
        uplifted = copy.deepcopy(self.manifest)
        uplifted["authority"]["d6_execution_authorized"] = True
        mutations.append(uplifted)
        drifted = copy.deepcopy(self.manifest)
        drifted["routes"][1]["artifacts"][2]["sha256"] = "0" * 64
        mutations.append(drifted)
        duplicated = copy.deepcopy(self.manifest)
        duplicated["routes"][0]["artifacts"][0] = copy.deepcopy(
            duplicated["routes"][0]["artifacts"][1]
        )
        mutations.append(duplicated)
        for mutation in mutations:
            with self.assertRaises(R1.VerificationError):
                R1.recompute(mutation)


if __name__ == "__main__":
    unittest.main()
