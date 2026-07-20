import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11_g19_post_archive_metadata_inspection_governance_validator.py';S=importlib.util.spec_from_file_location('g19',P);M=importlib.util.module_from_spec(S);sys.modules['g19']=M;S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_pass(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_materialization_stays_closed(self):self.assertFalse(M.json.loads(M.C.read_bytes())['decision']['PAX_acceptance_or_materialization_authorized'])
if __name__=='__main__':unittest.main()
