import copy, importlib.util, json, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location("d3",HERE/"fh_l8_degree6_streaming_d3_checker.py"); D3=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(D3)
class D3CheckerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_degree6_streaming_d3_contract.json").read_text()); cls.result=json.loads((HERE/"fh_l8_degree6_streaming_d3_result.json").read_text()); cls.evidence=D3.verify(cls.contract,cls.result)
 def test_terminal_status(self): self.assertEqual(self.evidence["status"],"VERIFIED_D3_STREAMING_PAIR_CAP_AND_MITM_COMPOSITION_GAP")
 def test_streaming_solves_memory_not_work(self):
  candidate=self.evidence["candidates"]["DEPTH_FIRST_STREAMING"]; self.assertTrue(candidate["memory_architecture_feasible"]); self.assertEqual(candidate["decision"],"PAIR_CAP_EXCEEDED")
  for item in candidate["observables"].values(): self.assertFalse(item["streaming_threshold"]["degree6_children_materialized"]); self.assertGreater(item["streaming_threshold"]["degree6_floor_after"],2_000_000_000)
 def test_mitm_claim_is_narrow(self):
  mitm=self.evidence["candidates"]["PAULI_L1_MEET_IN_THE_MIDDLE"]; self.assertEqual(mitm["decision"],"BLOCKED_MISSING_COMPOSITION_PROOF"); self.assertFalse(mitm["numerically_executed"]); self.assertIn("No general MITM no-go",self.evidence["limitations"][1])
 def test_result_mutation_rejected(self):
  bad=copy.deepcopy(self.result); bad["degree6_remainder_bounded"]=True
  with self.assertRaises(D3.VerificationError): D3.verify(self.contract,bad)
 def test_authority_escalation_rejected(self):
  bad=copy.deepcopy(self.result); bad["ready_gate_eligible"]=True
  with self.assertRaises(D3.VerificationError): D3.verify(self.contract,bad)
 def test_exact_threshold_prefixes(self):
  obs=self.evidence["candidates"]["DEPTH_FIRST_STREAMING"]["observables"]; self.assertEqual(obs["staggered_magnetization"]["streaming_threshold"]["terminal_prefix"],[0,6,7,13,15]); self.assertEqual(obs["double_occupancy"]["streaming_threshold"]["terminal_prefix"],[0,1,2,2,4])
if __name__=="__main__": unittest.main()
