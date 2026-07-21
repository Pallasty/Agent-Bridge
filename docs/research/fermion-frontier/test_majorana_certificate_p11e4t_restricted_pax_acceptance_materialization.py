import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11e4t_restricted_pax_acceptance_materialization_validator.py';S=importlib.util.spec_from_file_location('e4t',P);M=importlib.util.module_from_spec(S);sys.modules['e4t']=M;S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_pass(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_only_four_keys(self):self.assertEqual(M.json.loads(M.C.read_bytes())['future_restricted_PAX_policy']['exact_required_key_set'],['atime','ctime','mtime','path'])
if __name__=='__main__':unittest.main()
