#!/usr/bin/env python3
import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11e4_version_bound_source_evidence_analysis_validator.py';S=importlib.util.spec_from_file_location('e4',P);M=importlib.util.module_from_spec(S);sys.modules['e4']=M;S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_pass(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_bounded(self):self.assertEqual(M.json.loads(M.C.read_bytes())['future_evidence_admission']['maximum_admitted_excerpts_total'],30)
if __name__=='__main__':unittest.main()
