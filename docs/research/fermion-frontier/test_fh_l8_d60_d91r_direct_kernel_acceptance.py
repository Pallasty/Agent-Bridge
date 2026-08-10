import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("d91r", HERE / "fh_l8_d60_d91r_direct_kernel_acceptance.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D91RAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))
        self.receipt = copy.deepcopy(MODULE.load(HERE / self.contract["receipt"]))

    def test_committed_result_is_exact_and_closed(self):
        result = MODULE.verify()
        self.assertEqual(result, MODULE.load(MODULE.RESULT))
        self.assertTrue(result["direct_kernel_evidence_accepted"])
        self.assertTrue(result["uefi_chain_open"])
        self.assertFalse(result["physical_media_execution_ready"])

    def test_uefi_failure_cannot_revoke_direct_evidence(self):
        self.receipt["rejected_or_open"]["uefi_grub_kernel_chain_pass"] = False
        self.assertTrue(MODULE.evaluate(self.receipt)["direct_kernel_evidence_accepted"])

    def test_scope_mutation_invalidates_acceptance(self):
        self.receipt["scope"]["mmc_touched"] = True
        self.assertFalse(MODULE.evaluate(self.receipt)["direct_kernel_evidence_accepted"])

    def test_authority_mutation_is_rejected(self):
        self.contract["authority"]["physical_boot_authorized"] = True
        with self.assertRaisesRegex(MODULE.D91RError, "authority opened"):
            MODULE.verify_contract(self.contract)


if __name__ == "__main__":
    unittest.main()
