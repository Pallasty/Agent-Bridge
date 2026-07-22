import copy,importlib.util,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d12",HERE/"fh_l8_q4_to_q5_cost_d12_checker.py")
d12=importlib.util.module_from_spec(spec);spec.loader.exec_module(d12)
class D12Test(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_q4_to_q5_cost_d12_contract.json").read_text());cls.result=json.loads((HERE/"fh_l8_q4_to_q5_cost_d12_result.json").read_text());cls.evidence=d12.verify(cls.contract,cls.result)
 def test_costs(self):
  self.assertEqual(self.evidence["costs"]["raw_candidate_upper_bound"],2426747625);self.assertEqual(self.evidence["costs"]["primary_spill_bytes_upper_bound"],77655924000)
 def test_current_envelope_no_go(self):
  self.assertTrue(all(self.evidence["current_d10_no_go"].values()));self.assertFalse(self.evidence["q5_executed"])
 def test_mutation_rejected(self):
  bad=copy.deepcopy(self.contract);bad["row_terms_per_source"]=224
  with self.assertRaises(d12.VerificationError):d12.recompute(bad)
 def test_authority_closed(self):
  for key in ("degree6_remainder_bounded","two_step_cumulative_error_bounded","full_R100_error_bounded","physical_reference_qualified","ready_gate_eligible"):self.assertFalse(self.evidence[key])
if __name__=="__main__":unittest.main()
