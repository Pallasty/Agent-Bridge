import sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import fh_l8_local_cost_survey_d38 as d
class T(unittest.TestCase):
 def test_fixed32_has_per_row_timing_and_zero_q3(self):
  x=d.run();self.assertEqual(x['selected_representatives'],32);self.assertEqual(x['scientific_action_calls'],33+x['selection_collector_calls']);self.assertEqual(x['packed_q3_reads'],0);self.assertTrue(all(r['elapsed_ns']>0 for r in x['rows']));self.assertTrue(x['full53_extrapolation_forbidden'])
