import copy,importlib.util,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d19",HERE/"fh_l8_full_run_decision_d19_checker.py");d19=importlib.util.module_from_spec(spec);spec.loader.exec_module(d19)
class D19Test(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_full_run_decision_d19_contract.json").read_text());cls.result=json.loads((HERE/"fh_l8_full_run_decision_d19_result.json").read_text());cls.evidence=d19.verify(cls.contract,cls.result)
 def test_full_run_not_authorized(self):self.assertTrue(self.evidence["bounded_preflight_externally_verified"]);self.assertFalse(self.evidence["full_53_shard_execution_authorized"])
 def test_authorization_mutation_rejected(self):
  bad=copy.deepcopy(self.contract);bad["full_execution_decision"]["full_53_shard_execution_authorized"]=True
  with self.assertRaises(d19.VerificationError):d19.recompute(bad)
 def test_partial_operand_mutation_rejected(self):
  bad=copy.deepcopy(self.contract);bad["full_execution_decision"]["partial_target_forbidden_as_full_q4_operand"]=False
  with self.assertRaises(d19.VerificationError):d19.recompute(bad)
if __name__=="__main__":unittest.main()
