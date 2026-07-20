#!/usr/bin/env python3
import importlib.util, sys, unittest
from pathlib import Path
P=Path(__file__).resolve().parent/"majorana_certificate_p11e1r_remedial_acquisition_governance_design_validator.py"
S=importlib.util.spec_from_file_location("e1r",P); M=importlib.util.module_from_spec(S);sys.modules["e1r"]=M;S.loader.exec_module(M)
class TestE1R(unittest.TestCase):
 def test_design_passes(self):self.assertEqual(M.verify()["status"],"PASS")
 def test_authorities_stay_closed(self):
  a=M.load(M.CONTRACT)["authority"];self.assertFalse(a["network_or_archive_acquisition_authorized"]);self.assertEqual(a["scientific_authority"],"NONE")
if __name__=="__main__":unittest.main()
