#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_kernel_fixture_boundary_d26 as d26


class D26KernelBoundaryTests(unittest.TestCase):
    def test_source_bound_kernel_is_detected_without_action(self):
        result = d26.audit()
        self.assertEqual(result["kernel_name"], "_reduced_column")
        self.assertEqual(result["kernel_parameters"], ["d4", "backend", "bonds", "representative", "symmetries"])
        self.assertTrue(result["kernel_invokes_sector_action"])
        self.assertTrue(result["d18c_binds_kernel"])
        self.assertEqual(result["scientific_action_calls"], 0)

    def test_structural_bound_is_not_a_cost_proof(self):
        result = d26.audit()
        self.assertEqual(result["structural_candidate_action_upper_bound"], 225)
        self.assertFalse(result["per_record_runtime_proven"])
        self.assertFalse(result["peak_memory_composition_proven"])
        self.assertFalse(result["full_53_scientific_execution_authorized"])


if __name__ == "__main__": unittest.main()
