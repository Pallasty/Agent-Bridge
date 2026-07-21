import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11_g17_post_nested_source_materialization_governance_validator.py';S=importlib.util.spec_from_file_location('g17',P);M=importlib.util.module_from_spec(S);sys.modules['g17']=M;S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_pass(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_current_actions_closed(self):self.assertFalse(any(M.json.loads(M.C.read_bytes())['decision'][k] for k in ['E4R_retry_authorized','archive_open_or_metadata_reinspection_authorized','derived_root_or_receipt_root_creation_authorized']))
if __name__=='__main__':unittest.main()
