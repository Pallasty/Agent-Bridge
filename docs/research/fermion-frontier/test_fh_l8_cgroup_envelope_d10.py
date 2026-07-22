import json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
class D10Test(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_cgroup_envelope_d10_contract.json").read_text());cls.receipt=json.loads((HERE/"fh_l8_cgroup_envelope_d10_receipt.json").read_text())
 def test_verified_envelope_and_preflight(self):
  self.assertEqual(self.receipt["memory_max"],self.contract["required"]["memory_max"]);self.assertEqual(self.receipt["memory_swap_max"],self.contract["required"]["memory_swap_max"]);self.assertTrue(self.receipt["memory_envelope_pass"])
  self.assertEqual(self.receipt["source_representatives"],4096);self.assertTrue(self.receipt["integral_amplitudes"]);self.assertLess(self.receipt["memory_current_after"],int(self.contract["required"]["memory_high"]))
 def test_no_full_action_claim(self):
  self.assertFalse(self.receipt["fourth_action_executed"]);self.assertFalse(self.receipt["full_run_authorized"])
if __name__=="__main__":unittest.main()
