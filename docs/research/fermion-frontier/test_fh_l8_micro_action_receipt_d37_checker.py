import sys,tempfile,shutil,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import fh_l8_micro_action_receipt_d37_checker as c
class T(unittest.TestCase):
 def test_trace_verifies(self):self.assertEqual(c.verify()['status'],'VERIFIED_D37_MICRO_ACTION_RECEIPT_CUSTODY_AND_REPLAY')
 def test_source_drift_fails(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t)/'r';shutil.copytree(HERE,r);(r/'fh_l8_single_micro_action_d30.py').write_text('#x')
   with self.assertRaisesRegex(c.Error,'custody'):c.verify(r)
