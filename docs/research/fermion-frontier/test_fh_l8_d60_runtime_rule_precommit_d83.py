import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("d83", HERE / "fh_l8_d60_runtime_rule_precommit_d83.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D83Tests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))

    def receipt(self):
        admission = self.contract["fresh_admission"]
        return {
            "contract_id": admission["receipt_contract_id"], "fresh_after_boot": True,
            "target_cpu": 15, "service_cgroup_path": admission["target_service_cgroup_path"],
            "predicates": {name: True for name in admission["required_green_predicates"]},
        }

    def environment(self):
        return {"captured_inside_receipt_service": True,
                "identity_except_cgroup_matches_d81": True,
                "cgroup_path": self.contract["fresh_admission"]["target_service_cgroup_path"]}

    def test_committed_state_is_blocked_and_authority_closed(self):
        self.assertEqual(MODULE.verify(), MODULE.load(MODULE.RESULT))
        result = MODULE.verify()
        self.assertFalse(result["runtime_lock_precommitted"])
        self.assertFalse(result["measurement_authorized"])
        self.assertFalse(result["full53_execution_authorized"])

    def test_rule_population_and_timeout_are_frozen(self):
        MODULE.verify_contract(self.contract)
        rule = self.contract["frozen_runtime_rule"]
        self.assertEqual(rule["total_confirmatory_samples"], 2295)
        self.assertEqual(rule["confirmatory_sample_timeout_seconds"], 240)

    def test_service_only_observation_cannot_substitute_for_receipt(self):
        result = MODULE.evaluate(self.contract, {"service_memory_limits_observed": True}, self.environment())
        self.assertFalse(result["fresh_isolation_receipt_admitted"])
        self.assertFalse(result["service_only_d79_observation_admitted_as_scope_proof"])

    def test_green_synthetic_inputs_only_route_to_separate_review(self):
        result = MODULE.evaluate(self.contract, self.receipt(), self.environment())
        self.assertTrue(result["premeasurement_inputs_complete"])
        self.assertFalse(result["runtime_lock_precommitted"])
        self.assertFalse(result["measurement_authorized"])
        self.assertEqual(result["next_gate"], "SEPARATE_OWNER_CONFIRMATORY_MEASUREMENT_AUTHORIZATION")

    def test_irq_or_environment_drift_fails_closed(self):
        receipt = self.receipt()
        receipt["predicates"]["irq_affinity_excludes_target"] = False
        environment = self.environment()
        environment["identity_except_cgroup_matches_d81"] = False
        result = MODULE.evaluate(self.contract, receipt, environment)
        self.assertFalse(result["premeasurement_inputs_complete"])

    def test_authority_mutation_is_rejected(self):
        self.contract["authority"]["runtime_lock_precommitted"] = True
        with self.assertRaisesRegex(MODULE.D83Error, "authority opened"):
            MODULE.verify_contract(self.contract)


if __name__ == "__main__":
    unittest.main()
