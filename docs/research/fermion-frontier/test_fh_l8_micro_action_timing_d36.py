import json,unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_receipt_keeps_micro_boundary(self):
  x=json.loads((Path(__file__).parent/'fh_l8_micro_action_timing_d36_result.json').read_text());self.assertGreater(x['elapsed_seconds'],0);self.assertEqual(x['scientific_action_calls'],1);self.assertEqual(x['packed_q3_reads'],0);self.assertFalse(x['full_53_scientific_execution_authorized']);self.assertEqual(len(x['source_sha256']),4)
