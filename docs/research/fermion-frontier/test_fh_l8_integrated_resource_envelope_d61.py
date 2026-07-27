import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d61",HERE/"fh_l8_integrated_resource_envelope_d61.py")
assert spec and spec.loader
d61=importlib.util.module_from_spec(spec)
spec.loader.exec_module(d61)
def contract(): return json.loads((HERE/"fh_l8_integrated_resource_envelope_d61_contract.json").read_text())
class D61Tests(unittest.TestCase):
    def test_committed_contract_verifies(self): self.assertEqual(d61.verify()["scratch_shortfall_bytes"],359759114)
    def test_pin_drift_fails_closed(self):
        x=copy.deepcopy(contract()); x["source_pins"]["fh_l8_runtime_rule_d60_result.json"]="0"*64
        with self.assertRaisesRegex(d61.D61Error,"pin drift"): d61.validate(x)
    def test_scratch_or_authority_drift_fails_closed(self):
        x=copy.deepcopy(contract()); x["scratch_reconciliation"]["shortfall_bytes"]=0
        with self.assertRaisesRegex(d61.D61Error,"scratch"): d61.validate(x)
        x=copy.deepcopy(contract()); x["authority"]["production_io_executed"]=True
        with self.assertRaisesRegex(d61.D61Error,"authority"): d61.validate(x)
