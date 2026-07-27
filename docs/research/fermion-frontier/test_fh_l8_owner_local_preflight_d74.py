import importlib.util
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d74", HERE/"fh_l8_owner_local_preflight_d74.py")
d74=importlib.util.module_from_spec(spec); spec.loader.exec_module(d74)
class D74Tests(unittest.TestCase):
    def test_preflight_is_non_authoritative(self):
        self.assertFalse(d74.verify()["owner_confirmation_present"])
