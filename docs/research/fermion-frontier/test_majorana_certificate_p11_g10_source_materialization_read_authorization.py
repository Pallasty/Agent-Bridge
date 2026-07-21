#!/usr/bin/env python3
import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11_g10_source_materialization_read_authorization_validator.py';S=importlib.util.spec_from_file_location('g10',P);M=importlib.util.module_from_spec(S);sys.modules['g10']=M;S.loader.exec_module(M)
class TestG10(unittest.TestCase):
 def test_review_passes(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_science_and_execution_closed(self):
  d=M.load(M.CONTRACT)['decision'];self.assertFalse(d['source_patch_build_configure_compile_link_execute_or_measure_authorized']);self.assertEqual(d['scientific_authority'],'NONE')
if __name__=='__main__':unittest.main()
