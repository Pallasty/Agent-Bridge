import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_local_cost_envelope_d40 as d40


class TestD40Envelope(unittest.TestCase):
    def test_pinned_local_receipts_admit_only_a_bounded_scale64_survey(self):
        result = d40.run()
        self.assertEqual(result["verified_scales"], [8, 16, 32])
        self.assertTrue(result["structural_replays_verified"])
        self.assertEqual(result["next_bounded_survey"]["representatives"], 64)
        self.assertEqual(result["next_bounded_survey"]["max_scientific_action_calls"], 68)
        self.assertLess(result["observed_peak_rss_kib_max"], result["next_bounded_survey"]["admission_rss_cap_kib"])
        self.assertEqual(result["packed_q3_reads"], 0)
        self.assertFalse(result["full_53_scientific_execution_authorized"])
        self.assertTrue(result["full53_extrapolation_forbidden"])


if __name__ == "__main__":
    unittest.main()
