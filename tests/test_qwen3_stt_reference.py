import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "eval" / "qwen3_stt_reference.py"
SPEC = importlib.util.spec_from_file_location("qwen3_stt_reference", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SttReferenceTests(unittest.TestCase):
    def test_normalization_removes_punctuation_and_folds_width_case(self):
        self.assertEqual(MODULE.normalize("Agent，Ｂridge！"), "agentbridge")

    def test_edit_distance(self):
        self.assertEqual(MODULE.edit_distance("语音系统", "语音系統"), 1)
        self.assertEqual(MODULE.edit_distance("abc", "abc"), 0)


if __name__ == "__main__":
    unittest.main()
