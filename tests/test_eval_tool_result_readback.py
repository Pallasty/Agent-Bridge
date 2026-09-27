"""Acceptance checks for the offline comparison, not model/task-value tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/eval/eval_tool_result_readback.py"


class ReadbackComparisonTests(unittest.TestCase):
    def evaluator(self) -> ModuleType:
        self.assertTrue(SCRIPT.is_file(), "offline comparison has not been implemented")
        spec = importlib.util.spec_from_file_location("readback_comparison", SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_middle_evidence_is_reachable_with_explicit_extra_calls(self) -> None:
        evaluator = self.evaluator()
        data = ("头🙂" * 4000 + "MIDDLE_ANCHOR" + "后" * 4000 + "END_ANCHOR").encode()
        result = evaluator.evaluate_case(data, ["MIDDLE_ANCHOR", "END_ANCHOR"])
        self.assertEqual(result["inline"]["anchors_visible"], 2)
        self.assertEqual(result["head_tail"]["anchors_visible"], 1)
        self.assertEqual(result["selective"]["anchors_recovered"], 2)
        self.assertEqual(result["selective"]["response_count"], 5)
        self.assertGreater(result["selective"]["wire_bytes"], result["selective"]["content_bytes"])
        self.assertGreater(result["inline"]["wire_bytes"], len(data))
        self.assertTrue(result["roundtrip"]["sha256_matches"])
        self.assertGreater(result["roundtrip"]["wire_bytes"], len(data))
        self.assertFalse(result["task_value_proven"])

    def test_entire_result_can_cost_more_for_a_small_input(self) -> None:
        result = self.evaluator().evaluate_case(b"first last", ["first", "last"])
        self.assertGreater(result["selective"]["wire_bytes"], result["inline"]["wire_bytes"])
        self.assertLess(result["response_byte_reduction_vs_inline"], 0)

    def test_missing_or_ambiguous_ground_truth_is_rejected(self) -> None:
        evaluator = self.evaluator()
        for anchors in (["absent", "tail"], ["repeat", "tail"]):
            with self.subTest(anchors=anchors), self.assertRaises(ValueError):
                evaluator.evaluate_case(b"repeat repeat tail", anchors)

    def test_same_anchor_cannot_count_as_two_successes(self) -> None:
        with self.assertRaises(ValueError):
            self.evaluator().evaluate_case(b"one anchor end", ["anchor", "anchor"])


if __name__ == "__main__":
    unittest.main()
