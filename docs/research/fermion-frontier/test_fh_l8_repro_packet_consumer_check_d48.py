#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_repro_packet_consumer_check_d48 as d48


class TestD48(unittest.TestCase):
    def test_repro_packet_consumer_check_is_static(self):
        result = d48.consumer_check()
        self.assertEqual(result["status"], "VERIFIED_D48_REPRO_PACKET_CONSUMER_CHECK_OR_ARCHIVE")
        self.assertEqual(result["scientific_action_checks_performed"], 0)
        self.assertEqual(result["scientific_actions_performed_by_verifier"], 0)
        self.assertEqual(result["selected_representatives"], 64)
        self.assertEqual(result["structural_rows_sha256"], "38aaeffb8f178e918e4f326888493166c21afc7fb1379e91ab965c345b4adc12")
        self.assertEqual(result["packed_q3_reads"], 0)
        self.assertFalse(result["full_53_scientific_execution_authorized"])
        self.assertTrue(result["full53_extrapolation_forbidden"])
        self.assertTrue(result["archive_ready"])


if __name__ == "__main__":
    unittest.main()
