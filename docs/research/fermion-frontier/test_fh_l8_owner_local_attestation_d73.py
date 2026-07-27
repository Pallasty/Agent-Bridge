import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("d73", HERE / "fh_l8_owner_local_attestation_d73.py")
assert spec and spec.loader
d73 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d73)


def contract():
    return json.loads((HERE / "fh_l8_owner_local_attestation_d73_contract.json").read_text())


class D73Tests(unittest.TestCase):
    def test_template_verifies(self):
        self.assertEqual(d73.verify()["owner_role_count"], 1)

    def test_external_contact_or_attestation_claim_fails_closed(self):
        value = copy.deepcopy(contract())
        value["authority"]["external_contact_required"] = True
        with self.assertRaises(d73.D73Error):
            d73.validate(value)
        value = copy.deepcopy(contract())
        value["owner_attestation_template"]["owner_identity"] = "owner"
        with self.assertRaises(d73.D73Error):
            d73.validate(value)
