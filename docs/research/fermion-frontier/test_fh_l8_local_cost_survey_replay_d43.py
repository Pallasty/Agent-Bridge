import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_local_cost_survey_replay_d43 as d43


class TestD43Replay(unittest.TestCase):
    def test_replay_matches_d42_without_expanding_authority(self):
        command = [sys.executable, str(HERE / "fh_l8_local_cost_survey_replay_d43.py")]
        first = json.loads(subprocess.check_output(command, text=True))
        second = json.loads(subprocess.check_output(command, text=True))
        self.assertTrue(first["structural_rows_match"])
        self.assertEqual(first["d43_structural_rows_sha256"], second["d43_structural_rows_sha256"])
        self.assertEqual(first["selected_representatives"], 64)
        self.assertEqual(first["scientific_action_calls"], 67)
        self.assertGreater(first["d43_peak_rss_kib"], 0)
        self.assertEqual(first["packed_q3_reads"], 0)
        self.assertFalse(first["full_53_scientific_execution_authorized"])
        self.assertTrue(first["full53_extrapolation_forbidden"])


if __name__ == "__main__":
    unittest.main()
