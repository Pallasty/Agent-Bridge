import importlib.util,unittest
from pathlib import Path
H=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d76",H/"fh_l8_owner_local_capacity_admission_d76.py")
d76=importlib.util.module_from_spec(spec);spec.loader.exec_module(d76)
class D76Tests(unittest.TestCase):
    def test_admits_only_owner_local_capacity(self):
        result=d76.verify()
        self.assertTrue(result["owner_local_capacity_admitted"])
        self.assertFalse(result["full53_execution_authorized"])
