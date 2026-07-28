import importlib.util
from pathlib import Path
import unittest
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d78",HERE/"fh_l8_owner_host_fingerprint_d78.py")
d78=importlib.util.module_from_spec(spec);spec.loader.exec_module(d78)
class D78Tests(unittest.TestCase):
    def test_unbounded_environment_stays_non_authoritative(self):
        self.assertFalse(d78.verify()["environment_frozen"])
