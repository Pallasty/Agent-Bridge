import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("d84", HERE / "fh_l8_d60_managed_irq_reboot_outcome_d84.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D84Tests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))

    def test_committed_reboot_outcome_is_exact_and_closed(self):
        result = MODULE.verify()
        self.assertEqual(result, MODULE.load(MODULE.RESULT))
        self.assertTrue(result["boot_parameter_admitted"])
        self.assertFalse(result["reboot_acceptance_admitted"])
        self.assertFalse(result["fresh_d82r_receipt_authorized"])
        self.assertFalse(result["full53_execution_authorized"])

    def test_cmdline_token_alone_never_admits_reboot(self):
        result = MODULE.evaluate(self.contract, self.contract["observed_snapshot"])
        self.assertTrue(result["boot_parameter_admitted"])
        self.assertFalse(result["effective_affinity_excludes_target"])

    def test_synthetic_irq_exclusion_only_opens_d82r_transaction_gate(self):
        snapshot = copy.deepcopy(self.contract["observed_snapshot"])
        snapshot["configured_affinity_list"] = "0-14"
        snapshot["effective_affinity_list"] = "0-14"
        result = MODULE.evaluate(self.contract, snapshot)
        self.assertTrue(result["fresh_d82r_receipt_authorized"])
        self.assertFalse(result["measurement_authorized"])
        self.assertFalse(result["runtime_lock_precommitted"])
        self.assertEqual(result["next_gate"], "HOST_ADMIN_D82R_APPLY_VERIFY_RECEIPT_ROLLBACK")

    def test_residue_blocks_transaction_even_with_irq_exclusion(self):
        snapshot = copy.deepcopy(self.contract["observed_snapshot"])
        snapshot["configured_affinity_list"] = "0-14"
        snapshot["effective_affinity_list"] = "0-14"
        snapshot["transaction_state_absent"] = False
        self.assertFalse(MODULE.evaluate(self.contract, snapshot)["fresh_d82r_receipt_authorized"])

    def test_authority_mutation_is_rejected(self):
        self.contract["authority"]["measurement_authorized"] = True
        with self.assertRaisesRegex(MODULE.D84Error, "authority opened"):
            MODULE.verify_contract(self.contract)


if __name__ == "__main__":
    unittest.main()
