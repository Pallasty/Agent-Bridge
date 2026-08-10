import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d86", HERE / "fh_l8_d60_alternate_storage_topology_gate_d86.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D86Tests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))

    def test_committed_result_is_exact_and_closed(self):
        result = MODULE.verify()
        self.assertEqual(result, MODULE.load(MODULE.RESULT))
        self.assertTrue(result["structural_candidate"])
        self.assertFalse(result["alternate_topology_admitted"])
        self.assertFalse(result["full53_execution_authorized"])

    def test_target_cpu_irq_blocks_structural_candidate(self):
        snapshot = copy.deepcopy(self.contract["observed_snapshot"])
        snapshot["candidate_irq_affinity"]["175"]["effective"] = "1,15"
        result = MODULE.evaluate(self.contract, snapshot)
        self.assertFalse(result["candidate_irq_excludes_target_cpu"])
        self.assertFalse(result["structural_candidate"])

    def test_boot_path_alone_does_not_remove_nvme_dependency(self):
        snapshot = copy.deepcopy(self.contract["observed_snapshot"])
        snapshot["independent_efi_partition_present"] = True
        snapshot["minimal_measurement_bundle_present"] = True
        result = MODULE.evaluate(self.contract, snapshot)
        self.assertTrue(result["independent_boot_path_proven"])
        self.assertFalse(result["nvme_dependency_absent"])
        self.assertFalse(result["alternate_topology_admitted"])

    def test_authority_mutation_is_rejected(self):
        self.contract["authority"]["format_authorized"] = True
        with self.assertRaisesRegex(MODULE.D86Error, "authority opened"):
            MODULE.verify_contract(self.contract)


if __name__ == "__main__":
    unittest.main()
