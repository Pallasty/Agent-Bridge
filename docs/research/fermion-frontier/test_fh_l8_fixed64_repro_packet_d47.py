import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_fixed64_repro_packet_d47 as d47


class TestD47(unittest.TestCase):
    def test_archive_packet_is_source_pinned_and_non_executing(self):
        result = d47.verify()
        self.assertEqual(result["receipts_verified"], ["d42", "d43", "d44", "d45", "d46"])
        self.assertEqual(result["selected_representatives"], 64)
        self.assertEqual(result["scientific_action_calls"], 67)
        self.assertEqual(result["scientific_actions_performed_by_verifier"], 0)
        self.assertEqual(result["packed_q3_reads"], 0)
        self.assertFalse(result["full_53_scientific_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
