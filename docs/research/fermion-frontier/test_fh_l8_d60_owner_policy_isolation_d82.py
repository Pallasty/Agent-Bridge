import copy
import importlib.util
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d82", HERE / "fh_l8_d60_owner_policy_isolation_d82.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D82Tests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))

    def admitted_snapshot(self):
        return {
            "d81_environment_identity_except_cgroup_path_matches": True,
            "root_cpuset_controller_available": True,
            "root_cpuset_subtree_enabled": True,
            "current_cgroup_path": "/fh-l8-d60-isolated.slice/fh-l8-d82-measurement.service",
            "current_partition_state": "isolated",
            "current_effective_cpus": "15",
            "current_exclusive_effective_cpus": "15",
            "root_isolated_cpus": "15",
            "process_affinity": "15",
            "target_cpu_online": True,
            "target_cpu_thread_siblings": "15",
            "irq_affinity_target_conflict_count": 0,
        }

    def test_current_host_fails_closed_after_owner_policy_freeze(self):
        result = MODULE.verify()
        self.assertTrue(result["owner_numeric_policy_frozen"])
        self.assertFalse(result["load_isolation_admitted"])
        self.assertEqual(result["missing_inputs"], ["concurrent_load_exclusion_mechanism"])
        self.assertFalse(result["full53_execution_authorized"])

    def test_confirmatory_population_is_459_per_class(self):
        MODULE.verify_contract(self.contract)
        margin = self.contract["measurement_margin"]
        self.assertEqual(margin["confirmatory_samples_per_operation_class"], 459)
        self.assertEqual(margin["total_confirmatory_samples"], 2295)

    def test_scalar_margin_is_rejected(self):
        self.contract["measurement_margin"]["scalar_margin_multiplier"] = "2.0x"
        with self.assertRaisesRegex(MODULE.D82Error, "scalar margin multiplier forbidden"):
            MODULE.verify_contract(self.contract)

    def test_posthoc_sample_exclusion_is_rejected(self):
        self.contract["measurement_margin"]["posthoc_sample_exclusion_allowed"] = True
        with self.assertRaisesRegex(MODULE.D82Error, "posthoc sample exclusion opened"):
            MODULE.verify_contract(self.contract)

    def test_exact_isolated_snapshot_is_admitted_but_does_not_authorize_measurement(self):
        result = MODULE.build_result(self.contract, self.admitted_snapshot())
        self.assertTrue(result["load_isolation_admitted"])
        self.assertEqual(result["missing_inputs"], [])
        self.assertEqual(result["next_gate"], "D83_SEALED_PREMEASUREMENT_PACKET_GENERATION")
        self.assertEqual(result["timing_measurements_executed"], 0)
        self.assertFalse(result["numeric_runtime_seconds_proven"])
        self.assertFalse(result["full53_execution_authorized"])

    def test_smt_or_irq_drift_fails_isolation(self):
        snapshot = self.admitted_snapshot()
        snapshot["target_cpu_thread_siblings"] = "14-15"
        snapshot["irq_affinity_target_conflict_count"] = 1
        isolation = MODULE.evaluate_isolation(
            snapshot, self.contract["load_isolation_requirement"]
        )
        self.assertFalse(isolation["admitted"])
        self.assertIn("target_cpu_has_no_smt_sibling", isolation["failed_predicates"])
        self.assertIn("irq_affinity_excludes_target", isolation["failed_predicates"])

    def test_timeout_never_promotes_to_numeric_proof(self):
        MODULE.verify_contract(self.contract)
        timeout = self.contract["timeout_policy"]
        self.assertFalse(timeout["automatic_retry_allowed"])
        self.assertFalse(timeout["deadline_extension_allowed"])
        self.assertFalse(self.contract["owner_decision"]["numeric_runtime_seconds_proven"])


if __name__ == "__main__":
    unittest.main()
