import importlib.util,json,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11e4s_archive_metadata_failure_receipt_validator.py';S=importlib.util.spec_from_file_location('e4s',P);M=importlib.util.module_from_spec(S);sys.modules['e4s']=M;S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_pass(self):self.assertEqual(M.verify()['status'],'PASS')
 def test_payload_and_materialization_closed(self):
  m=json.loads(M.C.read_bytes())['future_metadata_operation'];self.assertTrue(m['source_payload_bytes_extractfile_extraction_materialization_and_semantic_interpretation_forbidden'])
 def test_attempt_receipt_precedes_open(self):self.assertTrue(json.loads(M.C.read_bytes())['future_receipt_identity']['attempt_receipt_must_be_fsynced_before_archive_open'])
if __name__=='__main__':unittest.main()
