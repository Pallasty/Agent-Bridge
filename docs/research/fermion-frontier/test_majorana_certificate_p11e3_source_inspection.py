#!/usr/bin/env python3
import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11e3_source_inspection_validator.py';S=importlib.util.spec_from_file_location('e3v',P);M=importlib.util.module_from_spec(S);sys.modules['e3v']=M;S.loader.exec_module(M)
class TestE3Result(unittest.TestCase):
 def test_failure_is_verified(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_no_source_read(self):self.assertFalse(M.load(M.REPORT)['source_text_read'])
if __name__=='__main__':unittest.main()
