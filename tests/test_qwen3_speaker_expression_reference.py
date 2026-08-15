import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "eval" / "qwen3_speaker_expression_reference.py"
SPEC = importlib.util.spec_from_file_location("qwen3_speaker_expression_reference", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SpeakerExpressionReferenceTests(unittest.TestCase):
    def test_sha256_is_stable(self):
        fixture = Path(__file__)
        self.assertEqual(MODULE.sha256(fixture), MODULE.sha256(fixture))


if __name__ == "__main__":
    unittest.main()
