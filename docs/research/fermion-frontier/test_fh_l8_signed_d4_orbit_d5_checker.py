import json, hashlib, importlib.util
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d5", HERE/"fh_l8_signed_d4_orbit_d5_checker.py")
d5=importlib.util.module_from_spec(spec);spec.loader.exec_module(d5)

class D5Test(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.contract=json.loads((HERE/"fh_l8_signed_d4_orbit_d5_contract.json").read_text())
  cls.result=json.loads((HERE/"fh_l8_signed_d4_orbit_d5_result.json").read_text())
  cls.evidence=d5.verify(cls.contract,cls.result)
 def test_status_and_characters(self):
  self.assertEqual(self.evidence["status"],d5.STATUS);self.assertEqual(self.evidence["Neel_characters"],[1]*8)
  self.assertTrue(self.evidence["hamiltonian_equivariance"]);self.assertTrue(self.evidence["observable_invariance"])
 def test_exact_orbits(self):
  self.assertEqual((self.evidence["orbit_records"]["depth1"]["state_count"],self.evidence["orbit_records"]["depth1"]["orbit_measurement"]["orbits"]),(225,29))
  self.assertEqual((self.evidence["orbit_records"]["depth2"]["state_count"],self.evidence["orbit_records"]["depth2"]["orbit_measurement"]["orbits"]),(24421,3116))
 def test_prefix_boundary(self):
  r=self.evidence["orbit_records"]["depth3"];self.assertEqual(r["state_count"],1704285);self.assertEqual(r["orbit_measurement"]["processed"],100000);self.assertFalse(self.evidence["depth3_full_orbit_count_certified"])
 def test_mutation_rejected(self):
  bad=dict(self.result);bad["signed_group_order"]=7
  with self.assertRaises(d5.VerificationError): d5.verify(self.contract,bad)
 def test_authority_flags(self):
  for key in ("degree6_remainder_bounded","two_step_cumulative_error_bounded","full_R100_error_bounded","physical_reference_qualified","ready_gate_eligible"): self.assertFalse(self.evidence[key])

if __name__=="__main__": unittest.main()
