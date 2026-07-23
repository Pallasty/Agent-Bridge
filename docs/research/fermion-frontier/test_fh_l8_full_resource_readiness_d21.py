import copy
import importlib.util
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d21", HERE / "fh_l8_full_resource_readiness_d21_checker.py"
)
D21 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D21)


@unittest.skipUnless(
    (HERE / "fh_l8_full_resource_readiness_d21_contract.json").exists()
    and (HERE / "fh_l8_full_resource_readiness_d21_result.json").exists(),
    "D21 contract/result not frozen yet",
)
class D21Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = D21.load_json(
            HERE / "fh_l8_full_resource_readiness_d21_contract.json"
        )
        cls.result = D21.load_json(
            HERE / "fh_l8_full_resource_readiness_d21_result.json"
        )

    def test_no_go_verifies(self):
        evidence = D21.verify(self.contract, self.result)
        self.assertEqual(evidence["status"], D21.STATUS)
        self.assertEqual(evidence["scientific_action_calls"], 0)

    def test_d20_is_plan_not_executable_consumer(self):
        findings = D21.recompute(self.contract)["d20_static_findings"]
        self.assertTrue(findings["declarative_protocol_plan_present"])
        self.assertTrue(findings["run_unconditionally_rejects_after_plan_validation"])
        self.assertFalse(findings["action_entrypoint_implemented"])
        self.assertFalse(findings["exact_53_shard_iteration_implemented"])
        self.assertFalse(findings["manifest_only_full_merge_implemented"])

    def test_planning_projection_is_exact_but_non_authoritative(self):
        projection = D21.recompute(self.contract)["planning_projection"]
        self.assertEqual(projection["linear_spill_bytes_ceiling"], 1446386155)
        self.assertEqual(projection["linear_target_bytes_ceiling"], 707025856)
        self.assertEqual(projection["linear_elapsed_ns_ceiling"], 3014449254665)
        self.assertEqual(projection["combined_margin_spill_and_target_bytes"], 2691765014)
        self.assertFalse(projection["authoritative_worst_case_disk_bound"])
        self.assertFalse(projection["authoritative_full_runtime_bound"])
        self.assertFalse(projection["authoritative_full_memory_bound"])

    def test_authorization_mutation_rejected(self):
        bad = copy.deepcopy(self.contract)
        bad["authorization_rule"]["full_53_shard_execution_authorized"] = True
        with self.assertRaises(D21.VerificationError):
            D21.recompute(bad)

    def test_executable_claim_mutation_rejected(self):
        bad = copy.deepcopy(self.contract)
        bad["d20_static_findings"]["action_entrypoint_implemented"] = True
        with self.assertRaises(D21.VerificationError):
            D21.recompute(bad)

    def test_authority_mutation_rejected(self):
        bad = copy.deepcopy(self.result)
        bad["authority"]["full_53_shard_execution_authorized"] = True
        with self.assertRaises(D21.VerificationError):
            D21.verify(self.contract, bad)

    def test_float_rejected(self):
        with self.assertRaises(D21.VerificationError):
            json.loads('{"x":1.5}', parse_float=D21._reject_float)

    def test_duplicate_key_rejected(self):
        with self.assertRaises(D21.VerificationError):
            json.loads('{"x":1,"x":2}', object_pairs_hook=D21._pairs)


if __name__ == "__main__":
    unittest.main()
