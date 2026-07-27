import copy
import unittest
import fh_l8_production_io_page_cache_d59 as d59

class D59Tests(unittest.TestCase):
 def setUp(self): self.contract=d59.load(d59.CONTRACT)
 def test_committed_contract_verifies(self): self.assertFalse(d59.verify()["numeric_peak_memory_proven"])
 def test_missing_two_generation_bound_fails_closed(self):
  x=copy.deepcopy(self.contract); x["fixed_policy"]["simultaneous_spill_generations"]=1
  with self.assertRaises(d59.D59Error): d59.validate(x)
 def test_page_cache_claim_fails_closed(self):
  x=copy.deepcopy(self.contract); x["fixed_policy"]["page_cache_environment_contract"]="PRESENT"
  with self.assertRaises(d59.D59Error): d59.validate(x)
 def test_production_io_authority_fails_closed(self):
  x=copy.deepcopy(self.contract); x["authority"]["production_io_executed"]=True
  with self.assertRaises(d59.D59Error): d59.validate(x)
if __name__=="__main__":unittest.main()
