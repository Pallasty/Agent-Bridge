import copy,importlib.util,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d13",HERE/"fh_l8_q5_redesign_d13_checker.py")
d13=importlib.util.module_from_spec(spec);spec.loader.exec_module(d13)
class D13Test(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_q5_redesign_d13_contract.json").read_text());cls.result=json.loads((HERE/"fh_l8_q5_redesign_d13_result.json").read_text());cls.evidence=d13.verify(cls.contract,cls.result)
 def test_route_selection(self):
  self.assertEqual(self.evidence["route_decisions"]["observable_adjoint_contraction"],"DESIGN_ONLY_NEXT");self.assertFalse(self.evidence["q5_executed"])
 def test_commutation_shortcut_not_authorized(self):
  self.assertEqual(self.evidence["route_decisions"]["commutation_shortcut"],"SEMANTICALLY_INVALID_NO_OBSERVABLE_COMMUTES_WITH_HOPPING_H")
 def test_mutation_rejected(self):
  bad=copy.deepcopy(self.contract);bad["routes"]["resource_expansion"]["authorized"]=True
  with self.assertRaises(d13.VerificationError):d13.recompute(bad)
if __name__=="__main__":unittest.main()
