#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_owner_autonomy_d29 as d29

class D29OwnerAutonomyTests(unittest.TestCase):
    def test_minimal_reversible_policy(self):
        result = d29.policy()
        self.assertEqual(result["allowed_next_action"]["kernel_calls"], 1)
        self.assertEqual(result["allowed_next_action"]["packed_q3_reads"], 0)
        self.assertFalse(result["full_53_scientific_execution_authorized"])

if __name__ == "__main__": unittest.main()
