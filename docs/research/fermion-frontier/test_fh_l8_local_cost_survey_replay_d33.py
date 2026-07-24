import json,unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_replay(self):
  x=json.loads((Path(__file__).parent/'fh_l8_local_cost_survey_replay_d33_result.json').read_text());self.assertTrue(x['rows_match']);self.assertEqual(x['scientific_action_calls'],9);self.assertEqual(x['packed_q3_reads'],0);self.assertFalse(x['full_53_scientific_execution_authorized'])
if __name__=='__main__':unittest.main()
