import importlib.util, json, unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d6",HERE/"fh_l8_byte_table_orbit_d6_checker.py")
d6=importlib.util.module_from_spec(spec);spec.loader.exec_module(d6)

class D6Test(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_byte_table_orbit_d6_contract.json").read_text())
  cls.result=json.loads((HERE/"fh_l8_byte_table_orbit_d6_result.json").read_text())
  cls.evidence=d6.verify(cls.contract,cls.result)
 def test_exact_depth3_orbits(self):
  record=self.evidence["depth3_orbit"]
  self.assertEqual((record["states"],record["orbits"]),(1704285,213099))
  self.assertEqual(record["digest"],"7e4f0d2526b49c786b124a8b45dc82cc8892a7798e7c4c362cd4aa15db74ca26")
 def test_fast_path_is_within_cap(self):
  self.assertTrue(self.evidence["canonicalization_within_seconds_cap"])
  self.assertEqual(self.evidence["signed_support_equivalence_samples"],4096)
 def test_mutation_rejected(self):
  bad=dict(self.result);bad["compression_ratio_denominator"]=1
  with self.assertRaises(d6.VerificationError): d6.verify(self.contract,bad)
 def test_authority_closure(self):
  self.assertEqual(self.evidence["fourth_layer_feasibility"],"NOT_EXECUTED_OR_CERTIFIED")
  for key in ("degree6_remainder_bounded","two_step_cumulative_error_bounded","full_R100_error_bounded","physical_reference_qualified","ready_gate_eligible"): self.assertFalse(self.evidence[key])

if __name__=="__main__": unittest.main()
