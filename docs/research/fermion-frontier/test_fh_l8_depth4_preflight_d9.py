import json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
class D9ReceiptTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_depth4_preflight_d9_contract.json").read_text());cls.receipt=json.loads((HERE/"fh_l8_depth4_preflight_d9_receipt.json").read_text())
 def test_bounded_semantic_measurements(self):
  self.assertEqual(self.receipt["source_representatives"],4096);self.assertEqual(self.receipt["raw_terms"],877976);self.assertEqual(self.receipt["reduced_terms"],864300);self.assertEqual(self.receipt["nonzero_targets"],317124);self.assertTrue(self.receipt["integral_amplitudes"])
  self.assertLessEqual(self.receipt["raw_terms"],self.contract["limits"]["max_raw_terms"]);self.assertLessEqual(self.receipt["elapsed_seconds"],self.contract["limits"]["max_shard_seconds"])
 def test_cgroup_envelope_failure_closes_full_run_authority(self):
  self.assertTrue(self.receipt["memory_probe_available"]);self.assertFalse(self.receipt["memory_envelope_pass"]);self.assertEqual(self.receipt["memory_max"],"max");self.assertEqual(self.receipt["memory_swap_max"],"max")
  self.assertFalse(self.receipt["full_run_authorized"]);self.assertFalse(self.receipt["fourth_action_executed"]);self.assertEqual(self.receipt["next_gate"],"ONE_GIB_ZERO_SWAP_CGROUP_REQUIRED_FOR_FULL_RUN_AUTHORIZATION")
if __name__=="__main__":unittest.main()
