import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "eval" / "qwen3_activation_capture.py"
SPEC = importlib.util.spec_from_file_location("qwen3_activation_capture", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ActivationCaptureTests(unittest.TestCase):
    def test_entropy_and_statistics_are_bounded(self):
        values = [-2.0, -1.0, 0.0, 1.0, 2.0]
        stats = MODULE.sample_stats(
            values,
            seen=9,
            calls=2,
            nonfinite=1,
            total_elements=100,
            output_signatures={'{"dtype":"float16","shape":[1,5]}'},
        )
        self.assertEqual(stats["sample_count"], 5)
        self.assertEqual(stats["finite_candidate_values_seen"], 9)
        self.assertEqual(stats["candidate_values_examined"], 10)
        self.assertEqual(stats["total_elements_seen"], 100)
        self.assertEqual(stats["nonfinite_candidates"], 1)
        self.assertEqual(stats["sample_min"], -2.0)
        self.assertEqual(stats["sample_max"], 2.0)
        self.assertEqual(stats["output_signatures"][0]["shape"], [1, 5])
        self.assertAlmostEqual(stats["mean"], 0.0)
        self.assertAlmostEqual(stats["zero_ratio"], 0.2)
        self.assertGreaterEqual(stats["normalized_entropy"]["256"], 0.0)
        self.assertLessEqual(stats["normalized_entropy"]["256"], 1.0)

    def test_case_selection_is_explicit_and_ordered(self):
        corpus = {"cases": [{"id": "a"}, {"id": "b"}]}
        self.assertEqual(
            [row["id"] for row in MODULE.selected_cases(corpus, ["b", "a"], False)],
            ["b", "a"],
        )
        self.assertEqual(
            [row["id"] for row in MODULE.selected_cases(corpus, [], True)],
            ["a", "b"],
        )
        with self.assertRaises(ValueError):
            MODULE.selected_cases(corpus, ["missing"], False)


if __name__ == "__main__":
    unittest.main()
