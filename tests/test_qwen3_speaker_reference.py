import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "eval" / "qwen3_speaker_reference.py"
SPEC = importlib.util.spec_from_file_location("qwen3_speaker_reference", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SpeakerReferenceTests(unittest.TestCase):
    def test_cosine_is_one_for_same_vector(self):
        self.assertAlmostEqual(MODULE.cosine([3.0, 4.0], [3.0, 4.0]), 1.0)

    def test_cosine_rejects_invalid_vectors(self):
        with self.assertRaises(ValueError):
            MODULE.cosine([], [])
        with self.assertRaises(ValueError):
            MODULE.cosine([1.0], [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
