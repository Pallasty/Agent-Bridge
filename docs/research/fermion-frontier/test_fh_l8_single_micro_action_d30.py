#!/usr/bin/env python3
import ast
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

class D30ReceiptTests(unittest.TestCase):
    def test_receipt_preserves_single_action_boundary(self):
        result = json.loads((HERE / "fh_l8_single_micro_action_d30_result.json").read_text())
        self.assertEqual(result["scientific_action_calls"], 1)
        self.assertEqual(result["packed_q3_reads"], 0)
        self.assertFalse(result["full_53_scientific_execution_authorized"])
        self.assertEqual(result["reduced_column_entries"], 29)

    def test_runner_has_exactly_one_kernel_call_site_and_no_q3_path(self):
        text = (HERE / "fh_l8_single_micro_action_d30.py").read_text()
        tree = ast.parse(text)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "_reduced_column"]
        self.assertEqual(len(calls), 1)
        self.assertNotIn("packed_q3_checkpoint", text)

if __name__ == "__main__": unittest.main()
