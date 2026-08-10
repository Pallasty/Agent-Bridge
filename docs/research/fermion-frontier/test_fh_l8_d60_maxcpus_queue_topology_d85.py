import copy, importlib.util, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("d85", HERE / "fh_l8_d60_maxcpus_queue_topology_d85.py")
MODULE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)
class D85Tests(unittest.TestCase):
    def setUp(self): self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))
    def test_committed_result_is_blocked(self):
        result = MODULE.verify(); self.assertEqual(result, MODULE.load(MODULE.RESULT)); self.assertFalse(result["d82r_isolation_admitted"])
    def test_missing_maxcpus_is_not_hidden_by_other_tokens(self):
        result = MODULE.evaluate(self.contract, self.contract["observed_snapshot"]); self.assertTrue(result["cmdline_tokens_admitted"] is False); self.assertEqual(result["next_gate"], "HOST_ADMIN_INSTALL_MAXCPUS_BOOT_CONFIG_THEN_RESTART")
    def test_green_synthetic_snapshot_only_opens_d82r(self):
        snap = copy.deepcopy(self.contract["observed_snapshot"]); snap["cmdline_tokens_present"].append("maxcpus=15"); snap["maxcpus_token_present"] = True; snap["d82r_plan_irq_conflict_count"] = 0
        result = MODULE.evaluate(self.contract, snap); self.assertTrue(result["d82r_isolation_admitted"]); self.assertFalse(result["measurement_authorized"])
    def test_authority_mutation_rejected(self):
        self.contract["authority"]["full53_execution_authorized"] = True
        with self.assertRaisesRegex(MODULE.D85Error, "authority opened"): MODULE.verify_contract(self.contract)
if __name__ == "__main__": unittest.main()
