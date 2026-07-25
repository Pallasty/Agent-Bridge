#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_repro_packet_archive_d47 as d48_archive


class TestD48Archive(unittest.TestCase):
    def test_repro_packet_archive_is_read_only_locked(self):
        result = d48_archive.archive()
        self.assertEqual(result["status"], "ARCHIVED_D48_REPRO_PACKET_D47_RESULT")
        self.assertEqual(result["next_gate"], "FH_L8_REPRO_PACKET_D47_ARCHIVE_CLOSED")
        self.assertEqual(result["archive_bundle"]["selected_representatives"], 64)
        self.assertEqual(result["archive_bundle"]["records"], 8)
        self.assertEqual(result["archive_bundle"]["scientific_action_checks"], 0)
        self.assertEqual(result["archive_bundle"]["packed_q3_reads"], 0)
        self.assertFalse(result["archive_bundle"]["full_53_scientific_execution_authorized"])
        self.assertTrue(result["archive_bundle"]["full53_extrapolation_forbidden"])


if __name__ == "__main__":
    unittest.main()
