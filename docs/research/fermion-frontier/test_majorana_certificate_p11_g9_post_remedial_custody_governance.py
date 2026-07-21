#!/usr/bin/env python3
import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11_g9_post_remedial_custody_governance_validator.py';S=importlib.util.spec_from_file_location('g9',P);M=importlib.util.module_from_spec(S);sys.modules['g9']=M;S.loader.exec_module(M)
class TestG9(unittest.TestCase):
 def test_governance_passes(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_only_pre_read_design_opens(self):self.assertEqual(M.load(M.CONTRACT)['decision']['only_allowed_next_gate'],'P11-E3-SOURCE-UNPACK-READ-PRECONDITION-CONTRACT-DESIGN-V1')
if __name__=='__main__':unittest.main()
