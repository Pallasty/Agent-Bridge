import importlib.util,unittest
from pathlib import Path
H=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location("d70",H/"fh_l8_d58_allocator_proof_request_d70.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class T(unittest.TestCase):
 def test_request(self):self.assertEqual(m.verify()["field_group_count"],3)
