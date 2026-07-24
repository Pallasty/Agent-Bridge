import json,unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_replay_matches_without_full_authority(self):
  x=json.loads((Path(__file__).parent/'fh_l8_local_cost_survey_replay_d39_result.json').read_text());self.assertTrue(x['structural_rows_match']);self.assertEqual(x['packed_q3_reads'],0);self.assertFalse(x['full_53_scientific_execution_authorized'])
