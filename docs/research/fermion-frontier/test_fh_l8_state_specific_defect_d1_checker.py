import copy, importlib.util, json, unittest
from fractions import Fraction
from pathlib import Path
HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location("d1",HERE/"fh_l8_state_specific_defect_d1_checker.py"); D1=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(D1)
class D1CheckerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_state_specific_defect_d1_contract.json").read_text()); cls.result=json.loads((HERE/"fh_l8_state_specific_defect_d1_result.json").read_text()); cls.evidence=D1.verify(cls.contract,cls.result)
 def test_positive_dual_observable_result(self):
  self.assertTrue(self.evidence["verified"]); self.assertEqual(set(self.evidence["observables"]),{"staggered_magnetization","double_occupancy"})
 def test_both_bounds_are_below_allocation(self):
  for record in self.evidence["observables"].values(): self.assertLess(Fraction(record["single_step"]["total_bound"]),Fraction(1,400000))
 def test_degree_four_state_specific_cancellation_is_retained(self):
  self.assertEqual(self.evidence["observables"]["staggered_magnetization"]["D4"]["Neel_expectation"],"115/6"); self.assertEqual(self.evidence["observables"]["double_occupancy"]["D4"]["Neel_expectation"],"-115/12")
 def test_result_mutation_is_rejected(self):
  bad=copy.deepcopy(self.result); bad["observables"]["double_occupancy"]["single_step"]["total_bound"]="0/1"
  with self.assertRaises(D1.VerificationError): D1.verify(self.contract,bad)
 def test_authority_escalation_is_rejected(self):
  bad=copy.deepcopy(self.result); bad["ready_gate_eligible"]=True
  with self.assertRaises(D1.VerificationError): D1.verify(self.contract,bad)
 def test_resource_usage_stays_below_caps(self):
  caps=self.contract["resource_limits"]
  for record in self.evidence["observables"].values():
   self.assertLessEqual(record["resource_usage"]["pair_products"],caps["max_pair_products_per_observable"]); self.assertLessEqual(record["resource_usage"]["peak_expansion_terms"],caps["max_expansion_terms"])
if __name__=="__main__": unittest.main()
