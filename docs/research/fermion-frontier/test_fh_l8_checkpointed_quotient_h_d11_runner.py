import hashlib,importlib.util,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d11",HERE/"fh_l8_checkpointed_quotient_h_d11_runner.py")
d11=importlib.util.module_from_spec(spec);spec.loader.exec_module(d11)
class D11SourceCheckpointTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_checkpointed_quotient_h_d11_contract.json").read_text());cls.receipt=json.loads((HERE/"fh_l8_checkpointed_quotient_h_d11_receipt.json").read_text())
 def test_fixed_record_and_receipt(self):
  self.assertEqual(d11.RECORD.size,32);self.assertEqual(self.receipt["payload_bytes"],6819168);self.assertEqual(self.receipt["shard_count"],53);self.assertFalse(self.receipt["fourth_action_executed"])
 def test_d5_pin_and_cgroup_predicate(self):
  self.assertEqual(hashlib.sha256((HERE/"fh_l8_symmetry_orbit_quotient_d5_checker.py").read_bytes()).hexdigest(),self.contract["d5_checker_sha256"])
  self.assertIsInstance(d11._cgroup_ok(),bool)
if __name__=="__main__":unittest.main()
