import copy,unittest
import fh_l8_reopening_contract_d63 as d
class D63Tests(unittest.TestCase):
 def test_verify(self):self.assertEqual(d.verify()["predicate_count"],5)
 def test_order_fails_closed(self):
  x=copy.deepcopy(d.load(d.CONTRACT));x["reopening_order"].pop()
  old=d.load; d.load=lambda p:x if p==d.CONTRACT else old(p)
  try:
   with self.assertRaises(d.D63Error):d.verify()
  finally:d.load=old
if __name__=="__main__":unittest.main()
