import importlib.util,unittest
from pathlib import Path
H=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location("d71",H/"fh_l8_evidence_request_handoff_d71.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class T(unittest.TestCase):
 def test_bundle(self):self.assertEqual(m.verify()["handoff_count"],4)
