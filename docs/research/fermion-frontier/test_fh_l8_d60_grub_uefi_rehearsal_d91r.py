import copy, importlib.util, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("d91r", HERE / "fh_l8_d60_grub_uefi_rehearsal_d91r.py")
MODULE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)
class D91RTests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT)); self.receipt = copy.deepcopy(MODULE.load(HERE / self.contract["receipt"]))
    def test_committed_result_is_exact_and_passes_virtual_chain(self):
        result = MODULE.verify(); self.assertEqual(result, MODULE.load(MODULE.RESULT)); self.assertTrue(result["virtual_rehearsal_admitted"]); self.assertFalse(result["physical_sd_boot_proven"])
    def test_grub_prompt_fails_closed(self):
        self.receipt["observations"]["grub_prompt_observed"] = True; self.assertFalse(MODULE.evaluate(self.contract, self.receipt)["virtual_rehearsal_admitted"])
    def test_basic_target_is_required_but_multi_user_is_not(self):
        self.receipt["observations"]["systemd_basic_target_pass"] = False; self.assertFalse(MODULE.evaluate(self.contract, self.receipt)["virtual_rehearsal_admitted"])
        self.receipt["observations"]["systemd_basic_target_pass"] = True; self.assertTrue(MODULE.evaluate(self.contract, self.receipt)["virtual_rehearsal_admitted"])
    def test_physical_authority_remains_closed(self):
        result = MODULE.evaluate(self.contract, self.receipt); self.assertFalse(result["mmc_write_authorized"]); self.assertFalse(result["host_reboot_authorized"]); self.assertFalse(result["full53_execution_authorized"])
    def test_authority_mutation_rejected(self):
        self.contract["authority"]["mmc_write_authorized"] = True
        with self.assertRaisesRegex(MODULE.D91RError, "authority opened"): MODULE.verify_contract(self.contract)
if __name__ == "__main__": unittest.main()
