import copy
import importlib.util
import json
from pathlib import Path
import unittest
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d62",HERE/"fh_l8_external_authorization_d62.py")
assert spec and spec.loader
d62=importlib.util.module_from_spec(spec); spec.loader.exec_module(d62)
def contract():return json.loads((HERE/"fh_l8_external_authorization_d62_contract.json").read_text())
class D62Tests(unittest.TestCase):
 def test_committed_denial_verifies(self):self.assertEqual(d62.verify()["unsatisfied_predicate_count"],5)
 def test_pin_and_predicate_drift_fail_closed(self):
  x=copy.deepcopy(contract());x["source_pins"]["fh_l8_integrated_resource_envelope_d61_result.json"]="0"*64
  with self.assertRaisesRegex(d62.D62Error,"pin drift"):d62.validate(x)
  x=copy.deepcopy(contract());x["observed_predicate_values"]["D61_integrated_envelope_GO"]=True
  with self.assertRaisesRegex(d62.D62Error,"predicate"):d62.validate(x)
 def test_authority_open_fails_closed(self):
  x=copy.deepcopy(contract());x["authority"]["external_resource_reservation_attempted"]=True
  with self.assertRaisesRegex(d62.D62Error,"authority"):d62.validate(x)
