#!/usr/bin/env python3
import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11e3_source_unpack_read_precondition_validator.py';S=importlib.util.spec_from_file_location('e3',P);M=importlib.util.module_from_spec(S);sys.modules['e3']=M;S.loader.exec_module(M)
class TestE3(unittest.TestCase):
 def test_contract_passes(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_no_current_read_authority(self):self.assertFalse(M.load(M.CONTRACT)['current_authority']['archive_unpack_or_source_reading_authorized'])
if __name__=='__main__':unittest.main()
