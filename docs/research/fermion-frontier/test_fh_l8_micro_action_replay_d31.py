#!/usr/bin/env python3
import json
import unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
class D31Tests(unittest.TestCase):
 def test_replay_matches_but_does_not_authorize_full_run(self):
  result=json.loads((HERE/'fh_l8_micro_action_replay_d31_result.json').read_text())
  self.assertTrue(result['output_digest_match'])
  self.assertEqual(result['peak_rss_delta_kib'],8)
  self.assertEqual(result['packed_q3_reads'],0)
  self.assertFalse(result['full_53_scientific_execution_authorized'])
if __name__=='__main__':unittest.main()
