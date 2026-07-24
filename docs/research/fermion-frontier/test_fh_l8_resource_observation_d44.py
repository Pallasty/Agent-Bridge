import json,unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_structural_and_resource_fields_are_separate(self):
  x=json.loads((Path(__file__).parent/'fh_l8_resource_observation_d44_result.json').read_text());self.assertTrue(x['structural_digest_authoritative']);self.assertFalse(x['rss_stable']);self.assertEqual(x['scientific_action_calls'],0);self.assertFalse(x['full_53_scientific_execution_authorized'])
if __name__=='__main__':unittest.main()
