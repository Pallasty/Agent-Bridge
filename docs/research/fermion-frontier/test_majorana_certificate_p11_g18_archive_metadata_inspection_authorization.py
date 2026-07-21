import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11_g18_archive_metadata_inspection_authorization_validator.py';S=importlib.util.spec_from_file_location('g18',P);M=importlib.util.module_from_spec(S);sys.modules['g18']=M;S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_pass(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_payload_stays_zero(self):self.assertEqual(M.json.loads(M.C.read_bytes())['operation_limits']['member_payload_bytes_read'],0)
if __name__=='__main__':unittest.main()
