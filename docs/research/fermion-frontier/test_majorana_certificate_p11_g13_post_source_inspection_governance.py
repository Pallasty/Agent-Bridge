#!/usr/bin/env python3
import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11_g13_post_source_inspection_governance_validator.py';S=importlib.util.spec_from_file_location('g13',P);M=importlib.util.module_from_spec(S);sys.modules['g13']=M;S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_pass(self):self.assertEqual(M.verify()['status'],'PASS')
if __name__=='__main__':unittest.main()
