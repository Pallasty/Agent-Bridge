import importlib.util,unittest
from pathlib import Path
H=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location("d65",H/"fh_l8_closure_evidence_package_d65.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class T(unittest.TestCase):
 def test_empty_package(self):self.assertEqual(m.verify()["slot_count"],4)
