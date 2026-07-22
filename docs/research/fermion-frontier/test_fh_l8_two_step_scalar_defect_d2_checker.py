import copy, importlib.util, json, math, unittest
from fractions import Fraction
from pathlib import Path
HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location("d2",HERE/"fh_l8_two_step_scalar_defect_d2_checker.py"); D2=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(D2)
class D2CheckerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_two_step_scalar_defect_d2_contract.json").read_text()); cls.result=json.loads((HERE/"fh_l8_two_step_scalar_defect_d2_result.json").read_text()); cls.evidence=D2.verify(cls.contract,cls.result)
 def test_failure_local_status(self):
  self.assertEqual(self.evidence["status"],"VERIFIED_D2_DEGREE6_REMAINDER_RESOURCE_THRESHOLD"); self.assertFalse(self.evidence["two_step_cumulative_error_bounded"])
 def test_odd_scalar_coefficients_are_zero(self):
  for record in self.evidence["observables"].values(): self.assertEqual(record["degrees"]["3"]["Neel_expectation"],"0/1"); self.assertEqual(record["degrees"]["5"]["Neel_expectation"],"0/1")
 def test_degree_four_is_not_promoted(self):
  self.assertEqual(self.evidence["observables"]["staggered_magnetization"]["degrees"]["4"]["Neel_expectation"],"230/3"); self.assertIn("not a two-step",self.evidence["limitations"][1])
 def test_combinatorics(self):
  gate=self.evidence["degree_six_gate"]; self.assertEqual(gate["weak_composition_count"],math.comb(22,6)); self.assertEqual(gate["full_prefix_count"],math.comb(23,6)); self.assertTrue(gate["prefix_cap_exceeded"])
 def test_result_mutation_rejected(self):
  bad=copy.deepcopy(self.result); bad["degree_six_gate"]["remainder_numerically_evaluated"]=True
  with self.assertRaises(D2.VerificationError): D2.verify(self.contract,bad)
 def test_authority_escalation_rejected(self):
  bad=copy.deepcopy(self.result); bad["ready_gate_eligible"]=True
  with self.assertRaises(D2.VerificationError): D2.verify(self.contract,bad)
 def test_resource_caps(self):
  caps=self.contract["resource_limits"]
  for record in self.evidence["observables"].values(): self.assertLessEqual(record["resource_usage"]["pair_products"],caps["max_pair_products_per_observable"]); self.assertLessEqual(record["resource_usage"]["peak_expansion_terms"],caps["max_expansion_terms"])
if __name__=="__main__": unittest.main()
