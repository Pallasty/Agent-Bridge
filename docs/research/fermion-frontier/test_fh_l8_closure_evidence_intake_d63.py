import copy, importlib.util, json
from pathlib import Path
import unittest
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d63",HERE/"fh_l8_closure_evidence_intake_d63.py");assert spec and spec.loader
d63=importlib.util.module_from_spec(spec);spec.loader.exec_module(d63)
def contract():return json.loads((HERE/"fh_l8_closure_evidence_intake_d63_contract.json").read_text())
class D63Tests(unittest.TestCase):
 def test_verify(self):self.assertEqual(d63.verify()["evidence_slot_count"],4)
 def test_open_intake_fails(self):
  x=copy.deepcopy(contract());x["authority"]["evidence_accepted"]=True
  with self.assertRaises(d63.D63Error):d63.validate(x)
