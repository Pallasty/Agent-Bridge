import importlib.util,unittest
from pathlib import Path
H=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location("d68",H/"fh_l8_d59_page_cache_environment_request_d68.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class T(unittest.TestCase):
 def test_request(self):self.assertEqual(m.verify()["field_group_count"],4)
