import copy,importlib.util,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d20",HERE/"fh_l8_full_consumer_d20.py");d20=importlib.util.module_from_spec(spec);spec.loader.exec_module(d20)
class D20Test(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_full_consumer_d20_contract.json").read_text());cls.result=json.loads((HERE/"fh_l8_full_consumer_d20_result.json").read_text())
 def test_frozen_full_plan(self):self.assertEqual(d20.build_plan(self.contract),self.result)
 def test_action_rejected(self):
  with self.assertRaises(d20.ConsumerError):d20.run(self.contract)
 def test_authorization_mutation_rejected(self):
  bad=copy.deepcopy(self.contract);bad["execution_authorization"]["full_53_shard_execution_authorized"]=True
  with self.assertRaises(d20.ConsumerError):d20.build_plan(bad)
 def test_frontier_mutation_rejected(self):
  bad=copy.deepcopy(self.contract);bad["source"]["shard_count"]=52
  with self.assertRaises(d20.ConsumerError):d20.build_plan(bad)
if __name__=="__main__":unittest.main()
