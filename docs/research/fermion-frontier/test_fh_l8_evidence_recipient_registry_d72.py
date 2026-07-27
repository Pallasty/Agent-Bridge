import importlib.util,unittest
from pathlib import Path
H=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location("d72",H/"fh_l8_evidence_recipient_registry_d72.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class T(unittest.TestCase):
 def test_template(self):self.assertEqual(m.verify()["channel_count"],4)
