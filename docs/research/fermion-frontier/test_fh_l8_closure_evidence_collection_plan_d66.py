import importlib.util,unittest
from pathlib import Path
H=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location("d66",H/"fh_l8_closure_evidence_collection_plan_d66.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class T(unittest.TestCase):
 def test_plan(self):self.assertEqual(m.verify()["collection_step_count"],4)
