import copy,importlib.util,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d17",HERE/"fh_l8_vector_custody_d17_checker.py");d17=importlib.util.module_from_spec(spec);spec.loader.exec_module(d17)
class D17Test(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_vector_custody_d17_contract.json").read_text());cls.result=json.loads((HERE/"fh_l8_vector_custody_d17_result.json").read_text());cls.evidence=d17.verify(cls.contract,cls.result)
 def test_custody_no_go(self):self.assertTrue(self.evidence["q3_source_admissible"]);self.assertFalse(self.evidence["q4_vector_admissible"]);self.assertFalse(self.evidence["dual_vector_contraction_protocol_materializable"])
 def test_preflight_is_design_only(self):self.assertTrue(self.evidence["fresh_bounded_4096_preflight_design_eligible"]);self.assertFalse(self.evidence["fresh_bounded_4096_preflight_execution_authorized"])
 def test_quarantine_mutation_rejected(self):
  bad=copy.deepcopy(self.contract);bad["vector_custody"]["q4_payload_admitted"]=True
  with self.assertRaises(d17.VerificationError):d17.recompute(bad)
 def test_execution_mutation_rejected(self):
  bad=copy.deepcopy(self.contract);bad["fresh_successor_protocol"]["bounded_preflight_execution_authorized"]=True
  with self.assertRaises(d17.VerificationError):d17.recompute(bad)
if __name__=="__main__":unittest.main()
