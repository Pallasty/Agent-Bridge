#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_full_resource_envelope_d23 as d23


class D23ResourceEnvelopeTests(unittest.TestCase):
    def test_file_and_byte_envelope(self):
        model = d23.envelope()
        self.assertEqual(model["max_spill_files"], 53 * 256)
        self.assertEqual(model["max_files"], 53 * 256 + 53 + 1)
        self.assertEqual(model["required_free_scratch_bytes"], 2_750_812_950)

    def test_missing_memory_and_runtime_is_no_go_even_with_disk(self):
        model = d23.envelope()
        snap = {"scratch": "/tmp", "free_bytes": model["required_free_scratch_bytes"], "free_inodes": model["max_files"], "memory_max_bytes": None, "memory_current_bytes": None, "runtime_upper_bound_ns": None}
        result = d23.decide(snap, model)
        self.assertTrue(result["disk_capacity_guardrail_satisfied"])
        self.assertTrue(result["file_count_guardrail_satisfied"])
        self.assertFalse(result["full_53_scientific_execution_authorized"])

    def test_insufficient_disk_is_no_go(self):
        model = d23.envelope()
        snap = {"scratch": "/tmp", "free_bytes": 0, "free_inodes": 0, "memory_max_bytes": 9, "memory_current_bytes": 1, "runtime_upper_bound_ns": 1}
        result = d23.decide(snap, model)
        self.assertFalse(result["disk_capacity_guardrail_satisfied"])
        self.assertFalse(result["file_count_guardrail_satisfied"])
        self.assertFalse(result["full_53_scientific_execution_authorized"])

    def test_even_all_fields_cannot_grant_d23_execution(self):
        model = d23.envelope()
        snap = {"scratch": "/tmp", "free_bytes": model["required_free_scratch_bytes"] + 1, "free_inodes": model["max_files"] + 1, "memory_max_bytes": 10, "memory_current_bytes": 1, "runtime_upper_bound_ns": 1}
        result = d23.decide(snap, model)
        self.assertEqual(result["status"], "UNREACHABLE_D23_AUTHORIZATION_ERROR")
        self.assertFalse(result["full_53_scientific_execution_authorized"])


if __name__ == "__main__": unittest.main()
