import copy,unittest
import fh_l8_runtime_rule_d60 as d60
class D60Tests(unittest.TestCase):
 def setUp(self):self.c=d60.load(d60.CONTRACT)
 def test_verify(self):self.assertFalse(d60.verify()["numeric_runtime_seconds_proven"])
 def test_environment_claim_fails_closed(self):
  x=copy.deepcopy(self.c);x["environment_definition"]["cpu_model_frequency_governor_fixed"]=True
  with self.assertRaises(d60.D60Error):d60.validate(x)
 def test_timing_execution_fails_closed(self):
  x=copy.deepcopy(self.c);x["authority"]["timing_measurements_executed"]=1
  with self.assertRaises(d60.D60Error):d60.validate(x)
if __name__=="__main__":unittest.main()
