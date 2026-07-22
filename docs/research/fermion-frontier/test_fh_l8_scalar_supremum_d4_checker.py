import copy, importlib.util, json, unittest
from fractions import Fraction
from pathlib import Path
HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location("d4",HERE/"fh_l8_scalar_supremum_d4_checker.py"); D4=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(D4)
class D4CheckerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_scalar_supremum_d4_contract.json").read_text()); cls.result=json.loads((HERE/"fh_l8_scalar_supremum_d4_result.json").read_text()); cls.evidence=D4.verify(cls.contract,cls.result)
 def test_status(self): self.assertEqual(self.evidence["status"],"VERIFIED_D4_SCALAR_SUPREMUM_CANDIDATE_FAILURE_THRESHOLDS")
 def test_required_M6_ceilings(self): self.assertEqual(self.evidence["budget_gate"]["staggered_magnetization"]["M6_ceiling"],"3048000000/1"); self.assertEqual(self.evidence["budget_gate"]["double_occupancy"]["M6_ceiling"],"3324000000/1")
 def test_generic_bound_is_inadequate(self):
  m=Fraction(self.evidence["candidates"]["GENERIC_DERIVATIVE"]["M6_bound"])
  for item in self.evidence["budget_gate"].values(): self.assertGreater(m,Fraction(item["M6_ceiling"]))
 def test_cauchy_claim_is_narrow(self): self.assertEqual(self.evidence["candidates"]["COMPLEX_CAUCHY"]["decision"],"NUMERICALLY_INADEQUATE"); self.assertIn("current global-norm",self.evidence["limitations"][1])
 def test_krylov_stops_before_next_action(self):
  k=self.evidence["candidates"]["EXACT_SECTOR_KRYLOV"]; self.assertFalse(k["next_action_executed"]); self.assertGreater(k["next_action_candidate_floor"],k["next_action_cap"])
 def test_result_mutation_rejected(self):
  bad=copy.deepcopy(self.result); bad["degree6_remainder_bounded"]=True
  with self.assertRaises(D4.VerificationError): D4.verify(self.contract,bad)
 def test_authority_escalation_rejected(self):
  bad=copy.deepcopy(self.result); bad["ready_gate_eligible"]=True
  with self.assertRaises(D4.VerificationError): D4.verify(self.contract,bad)
if __name__=="__main__": unittest.main()
