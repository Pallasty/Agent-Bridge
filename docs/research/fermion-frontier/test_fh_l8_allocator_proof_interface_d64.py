import importlib.util,unittest
from pathlib import Path
H=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location("d64",H/"fh_l8_allocator_proof_interface_d64.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class T(unittest.TestCase):
 def test_verify(self):self.assertEqual(m.verify()["covered_variable_count"],8)
