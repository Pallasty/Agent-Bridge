#!/usr/bin/env python3
import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11e3r_source_inspection_validator.py';S=importlib.util.spec_from_file_location('v',P);V=importlib.util.module_from_spec(S);sys.modules['v']=V;S.loader.exec_module(V)
class T(unittest.TestCase):
 def test_result(self):self.assertEqual(V.verify()['status'],'PASS')
if __name__=='__main__':unittest.main()
