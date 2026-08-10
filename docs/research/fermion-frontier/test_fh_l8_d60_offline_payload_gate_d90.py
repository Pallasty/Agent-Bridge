import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("d90", HERE / "fh_l8_d60_offline_payload_gate_d90.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D90Tests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))
        self.receipt = copy.deepcopy(MODULE.load(HERE / self.contract["receipt"]))

    def test_committed_result_is_exact_and_closed(self):
        result = MODULE.verify()
        self.assertEqual(result, MODULE.load(MODULE.RESULT))
        self.assertTrue(result["payload_assembly_complete"])
        self.assertFalse(result["physical_media_execution_ready"])
        self.assertFalse(result["mmc_write_authorized"])

    def test_missing_matching_modules_fails_assembly(self):
        self.receipt["static_checks"]["sdhci_pci_module_present"] = False
        self.assertFalse(MODULE.evaluate(self.contract, self.receipt)["payload_assembly_complete"])

    def test_unresolved_uuids_keep_materialization_false(self):
        result = MODULE.evaluate(self.contract, self.receipt)
        self.assertTrue(result["payload_assembly_complete"])
        self.assertFalse(result["boot_configuration_materialized"])

    def test_mmc_mount_fails_assembly(self):
        self.receipt["mmc_post_state"]["mountpoints"] = ["/mnt/mmc"]
        self.assertFalse(MODULE.evaluate(self.contract, self.receipt)["payload_assembly_complete"])

    def test_authority_mutation_is_rejected(self):
        self.contract["authority"]["mmc_write_authorized"] = True
        with self.assertRaisesRegex(MODULE.D90Error, "authority opened"):
            MODULE.verify_contract(self.contract)


if __name__ == "__main__":
    unittest.main()
