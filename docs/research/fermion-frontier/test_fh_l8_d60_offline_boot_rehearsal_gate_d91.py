import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("d91", HERE / "fh_l8_d60_offline_boot_rehearsal_gate_d91.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D91Tests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))
        self.receipt = copy.deepcopy(MODULE.load(HERE / self.contract["receipt"]))

    def test_committed_result_is_exact_and_closed(self):
        result = MODULE.verify()
        self.assertEqual(result, MODULE.load(MODULE.RESULT))
        self.assertTrue(result["direct_kernel_boot_pass"])
        self.assertFalse(result["uefi_grub_kernel_chain_pass"])
        self.assertFalse(result["physical_sd_boot_proven"])

    def test_uefi_failure_is_not_promoted(self):
        self.receipt["observations"]["uefi_grub_kernel_chain_pass"] = True
        result = MODULE.evaluate(self.contract, self.receipt)
        self.assertTrue(result["boot_rehearsal_complete"])
        self.assertFalse(result["physical_sd_boot_proven"])

    def test_direct_boot_failure_blocks(self):
        self.receipt["observations"]["direct_kernel_boot_pass"] = False
        self.assertFalse(MODULE.evaluate(self.contract, self.receipt)["direct_kernel_boot_pass"])

    def test_host_mutation_fails_untouched_gate(self):
        self.receipt["observations"]["host_rebooted"] = True
        self.assertFalse(MODULE.evaluate(self.contract, self.receipt)["mmc_and_host_untouched"])

    def test_authority_mutation_is_rejected(self):
        self.contract["authority"]["mmc_write_authorized"] = True
        with self.assertRaisesRegex(MODULE.D91Error, "authority opened"):
            MODULE.verify_contract(self.contract)


if __name__ == "__main__":
    unittest.main()
