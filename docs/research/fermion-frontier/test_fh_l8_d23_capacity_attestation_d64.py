import unittest
import fh_l8_d23_capacity_attestation_d64 as d
class D64CapacityTests(unittest.TestCase):
 def test_live_reservation_is_observed_but_not_admitted(self):
  x=d.verify();self.assertEqual(x["logical_bytes"],3110572064);self.assertFalse(x["capacity_attestation_admitted"])
if __name__=="__main__":unittest.main()
