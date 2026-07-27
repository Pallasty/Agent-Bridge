import importlib.util,unittest
from pathlib import Path
H=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location("d67",H/"fh_l8_d23_external_capacity_receipt_request_d67.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class T(unittest.TestCase):
 def test_request(self):self.assertEqual(m.verify()["required_bytes"],3110572064)
