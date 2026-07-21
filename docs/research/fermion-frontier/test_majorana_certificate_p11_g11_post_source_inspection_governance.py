#!/usr/bin/env python3
import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11_g11_post_source_inspection_governance_validator.py';S=importlib.util.spec_from_file_location('g11',P);M=importlib.util.module_from_spec(S);sys.modules['g11']=M;S.loader.exec_module(M)
class TestG11(unittest.TestCase):
 def test_governance_passes(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_retry_stays_closed(self):self.assertFalse(M.load(M.CONTRACT)['decision']['retry_or_materialization_authorized'])
if __name__=='__main__':unittest.main()
