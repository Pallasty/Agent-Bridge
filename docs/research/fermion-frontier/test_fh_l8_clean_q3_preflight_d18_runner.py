import importlib.util,json,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("d18",HERE/"fh_l8_clean_q3_preflight_d18_runner.py");d18=importlib.util.module_from_spec(spec);spec.loader.exec_module(d18)
class D18StaticTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.contract=json.loads((HERE/"fh_l8_clean_q3_preflight_d18_contract.json").read_text())
 def test_protocol_is_bounded_and_clean(self):
  self.assertEqual(self.contract["run_protocol"]["source_records"],4096);self.assertTrue(self.contract["run_protocol"]["fresh_exclusive_scratch_required"]);self.assertTrue(self.contract["run_protocol"]["shared_append_spool_forbidden"])
 def test_existing_scratch_is_rejected_before_action(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(d18.RunnerError):d18.run(self.contract,Path(tmp))
 def test_authority_ceiling(self):self.assertFalse(any(self.contract["authority_exclusions"].values()))
if __name__=="__main__":unittest.main()
