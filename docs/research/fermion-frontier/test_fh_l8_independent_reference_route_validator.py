import copy, importlib.util, json, subprocess, sys, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location("route_validator",HERE/"fh_l8_independent_reference_route_validator.py"); V=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(V)
class RouteValidatorTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.c=json.loads((HERE/"fh_l8_independent_reference_route_contract.json").read_text()); cls.r=json.loads((HERE/"fh_l8_independent_reference_route_result.json").read_text())
 def test_positive(self): self.assertEqual(V.verify(self.c,self.r)["next_unit"],"FH-L8-INDEPENDENT-REFERENCE-D1")
 def test_arithmetic(self): self.assertEqual(V.verify(self.c,self.r)["arithmetic"]["double_occupancy"]["uniform_floor"],"133927/24000000")
 def test_nonzero_expectation_rejected(self):
  b=copy.deepcopy(self.c); b["observables"]["double_occupancy"]["k0_D3_Neel_expectation"]="1/1000"
  with self.assertRaises(V.ValidationError): V.verify(b,self.r)
 def test_route_relabel_rejected(self):
  b=copy.deepcopy(self.r); b["selected_route"]="ORDINARY_SUPPORT_LIGHT_CONE"
  with self.assertRaises(V.ValidationError): V.verify(self.c,b)
 def test_ready_rejected(self):
  b=copy.deepcopy(self.r); b["ready_gate_eligible"]=True
  with self.assertRaises(V.ValidationError): V.verify(self.c,b)
 def test_pin_rejected(self):
  b=copy.deepcopy(self.c); b["source_pins"][0]["sha256"]="0"*64
  with self.assertRaises(V.ValidationError): V.verify(b,self.r)
 def test_cli(self):
  p=subprocess.run([sys.executable,str(HERE/"fh_l8_independent_reference_route_validator.py")],capture_output=True,text=True); self.assertEqual(p.returncode,0,p.stderr); self.assertTrue(json.loads(p.stdout)["verified"])
if __name__=="__main__": unittest.main()
