#!/usr/bin/env python3
import importlib.util,json,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11_g15_post_source_evidence_analysis_governance_validator.py';S=importlib.util.spec_from_file_location('g15',P);M=importlib.util.module_from_spec(S);sys.modules['g15']=M;S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_pass(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_authority_stays_closed(self):
  d=json.loads(M.C.read_bytes())['decision'];self.assertFalse(d['E4_retry_authorized']);self.assertFalse(d['nested_archive_materialization_authorized']);self.assertEqual(d['scientific_authority'],'NONE')
 def test_design_requirements_are_fail_closed(self):self.assertTrue(all(json.loads(M.C.read_bytes())['future_design_requirements'].values()))
if __name__=='__main__':unittest.main()
