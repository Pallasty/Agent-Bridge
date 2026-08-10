import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "eval" / "qwen3_emotion_reference.py"
SPEC = importlib.util.spec_from_file_location("qwen3_emotion_reference", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class EmotionReferenceTests(unittest.TestCase):
    def test_classification_result_selects_highest_score(self):
        result = MODULE.classify_result([{"labels": ["neutral", "happy"], "scores": [0.2, 0.8]}])
        self.assertEqual(result["top_label"], "happy")
        self.assertEqual(result["top_score"], 0.8)

    def test_classification_result_rejects_misaligned_data(self):
        with self.assertRaises(ValueError):
            MODULE.classify_result([{"labels": ["neutral"], "scores": []}])


if __name__ == "__main__":
    unittest.main()
