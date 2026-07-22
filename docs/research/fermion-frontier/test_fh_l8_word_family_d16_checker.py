import copy,importlib.util,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d16",HERE/"fh_l8_word_family_d16_checker.py");d16=importlib.util.module_from_spec(spec);spec.loader.exec_module(d16)
class D16Test(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_word_family_d16_contract.json").read_text());cls.result=json.loads((HERE/"fh_l8_word_family_d16_result.json").read_text());cls.evidence=d16.verify(cls.contract,cls.result)
 def test_atomic_words_rejected(self):self.assertFalse(self.evidence["atomic_product_formula_word_family_accepted"])
 def test_moment_family_is_design_only(self):self.assertTrue(self.evidence["full_H_moment_word_family_design_eligible"]);self.assertFalse(self.evidence["contraction_execution_authorized"])
 def test_atomic_mutation_rejected(self):
  bad=copy.deepcopy(self.contract);bad["atomic_gate_symmetry_audit"]["current_atomic_product_formula_word_eligible"]=True
  with self.assertRaises(d16.VerificationError):d16.recompute(bad)
 def test_q5_mutation_rejected(self):
  bad=copy.deepcopy(self.contract);bad["resource_accounting"]["q5_authorized"]=True
  with self.assertRaises(d16.VerificationError):d16.recompute(bad)
if __name__=="__main__":unittest.main()
