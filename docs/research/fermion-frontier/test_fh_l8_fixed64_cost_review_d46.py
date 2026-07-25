import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_fixed64_cost_review_d46 as d46


class TestD46(unittest.TestCase):
    def test_reconciles_fixed64_without_expanding_claims(self):
        result = d46.review()
        self.assertTrue(result["structural_chain_verified"])
        self.assertEqual(result["structural_rows_sha256"], "38aaeffb8f178e918e4f326888493166c21afc7fb1379e91ab965c345b4adc12")
        self.assertEqual(result["scientific_action_calls"], 67)
        self.assertEqual(result["controlled_rss_span_kib"], 28)
        self.assertEqual(result["packed_q3_reads"], 0)
        self.assertFalse(result["full_53_scientific_execution_authorized"])
        self.assertTrue(result["full53_extrapolation_forbidden"])


if __name__ == "__main__":
    unittest.main()
