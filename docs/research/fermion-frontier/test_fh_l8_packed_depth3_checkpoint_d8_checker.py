import copy,importlib.util,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d8",HERE/"fh_l8_packed_depth3_checkpoint_d8_checker.py")
d8=importlib.util.module_from_spec(spec);spec.loader.exec_module(d8)
class D8Test(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_packed_depth3_checkpoint_d8_contract.json").read_text());cls.result=json.loads((HERE/"fh_l8_packed_depth3_checkpoint_d8_result.json").read_text());cls.evidence=d8.verify(cls.contract,cls.result)
 def test_layout_and_schedule(self):
  self.assertEqual(self.evidence["payload_bytes"],6819168);self.assertEqual(self.evidence["shard_schedule"],{"count":53,"full_shards":52,"last_shard_records":107})
 def test_authority_closed(self):
  self.assertFalse(self.evidence["checkpoint_materialized"]);self.assertFalse(self.evidence["depth3_to_depth4_action_authorized"]);self.assertFalse(self.evidence["depth3_to_depth4_action_executed"])
 def test_mutation_rejected(self):
  bad=copy.deepcopy(self.contract);bad["record_layout"]["record_bytes"]=31
  with self.assertRaises(d8.VerificationError):d8.recompute(bad)
if __name__=="__main__":unittest.main()
