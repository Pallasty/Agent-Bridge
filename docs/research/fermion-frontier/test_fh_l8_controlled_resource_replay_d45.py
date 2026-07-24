import unittest
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_controlled_resource_replay_d45 as d45


class TestD45(unittest.TestCase):
    def test_controlled_replay_is_structural_only(self):
        result = d45.run()
        self.assertTrue(result["structural_replays_match"])
        self.assertEqual(result["structural_rows_sha256"], "38aaeffb8f178e918e4f326888493166c21afc7fb1379e91ab965c345b4adc12")
        self.assertEqual(result["scientific_action_calls_per_replay"], 67)
        self.assertEqual(result["packed_q3_reads"], 0)
        self.assertFalse(result["full_53_scientific_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
