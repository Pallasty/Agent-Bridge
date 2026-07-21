#!/usr/bin/env python3
import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/"majorana_certificate_p11_g8_remedial_operational_authorization_validator.py";S=importlib.util.spec_from_file_location("g8",P);M=importlib.util.module_from_spec(S);sys.modules["g8"]=M;S.loader.exec_module(M)
class TestG8(unittest.TestCase):
 def test_review_passes(self):self.assertEqual(M.verify()["status"],"PASS")
 def test_run_stays_scientifically_closed(self):
  d=M.load(M.CONTRACT)["decision"];self.assertFalse(d["archive_unpack_or_source_reading_authorized"]);self.assertEqual(d["scientific_authority"],"NONE")
if __name__=="__main__":unittest.main()
