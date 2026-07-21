#!/usr/bin/env python3
import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11_g14_source_evidence_analysis_authorization_validator.py';S=importlib.util.spec_from_file_location('g14',P);M=importlib.util.module_from_spec(S);sys.modules['g14']=M;S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_pass(self):self.assertEqual(M.verify()['status'],'PASS')
if __name__=='__main__':unittest.main()
