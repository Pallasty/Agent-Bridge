#!/usr/bin/env python3
import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11e2r_remedial_source_archive_custody_validator.py';S=importlib.util.spec_from_file_location('e2rv',P);M=importlib.util.module_from_spec(S);sys.modules['e2rv']=M;S.loader.exec_module(M)
class TestE2R(unittest.TestCase):
 def test_offline_custody_passes(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_four_packages_are_fresh_and_final_path_bound(self):
  d=M.load(M.MANIFEST);self.assertEqual(len(d['accepted_files']),11);self.assertEqual(d['outcome'],'REMEDIAL_SOURCE_ARCHIVE_CUSTODY_ESTABLISHED_EXACT_FOUR_FRESH_PACKAGE_SET')
if __name__=='__main__':unittest.main()
