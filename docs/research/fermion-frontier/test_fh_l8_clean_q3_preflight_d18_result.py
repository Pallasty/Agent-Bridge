import hashlib,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
class D18ResultTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.result=json.loads((HERE/"fh_l8_clean_q3_preflight_d18_result.json").read_text());cls.contract=json.loads((HERE/"fh_l8_clean_q3_preflight_d18_contract.json").read_text())
 def test_pinned_clean_preflight_outcome(self):
  self.assertEqual(self.result["status"],"VERIFIED_D18_FRESH_EXCLUSIVE_PACKED_Q3_BOUNDED_PREFLIGHT");self.assertEqual(self.result["source"]["records"],4096);self.assertEqual(self.result["merge"]["target_records"],424682);self.assertTrue(self.result["merge"]["naive_equivalence"])
 def test_resource_envelope(self):
  r=self.result["resource"];self.assertEqual(r["memory_max_bytes"],1073741824);self.assertEqual(r["memory_swap_max_bytes"],0);self.assertLessEqual(r["memory_peak_bytes"],r["memory_high_bytes"])
 def test_source_and_authority_boundaries(self):
  self.assertEqual(self.result["source"]["checkpoint_sha256"],self.contract["source_pins"]["packed_q3_checkpoint"]);self.assertFalse(any(self.result["authority"].values()))
 def test_runner_pin(self):
  self.assertEqual(hashlib.sha256((HERE/"fh_l8_clean_q3_preflight_d18_runner.py").read_bytes()).hexdigest(),self.contract["runner_self_sha256"])
if __name__=="__main__":unittest.main()
