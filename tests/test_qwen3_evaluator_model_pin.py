import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "eval" / "qwen3_evaluator_model_pin.py"
SPEC = importlib.util.spec_from_file_location("qwen3_evaluator_model_pin", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class EvaluatorModelPinTests(unittest.TestCase):
    def test_missing_or_partial_snapshots_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(MODULE.pin_snapshot("emotion", root / "missing")["status"], "MISSING_SNAPSHOT")
            partial = root / "partial"
            partial.mkdir()
            (partial / "model.pt").write_bytes(b"not-a-model")
            result = MODULE.pin_snapshot("emotion", partial)
            self.assertEqual(result["status"], "INCOMPLETE_SNAPSHOT")
            self.assertEqual(result["missing_anchors"], ["configuration.json"])

    def test_complete_snapshot_is_hashed_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "configuration.json").write_text("{}")
            (root / "campplus_cn_common.bin").write_bytes(b"model")
            first = MODULE.pin_snapshot("speaker", root)
            second = MODULE.pin_snapshot("speaker", root)
            self.assertEqual(first, second)
            self.assertEqual(first["status"], "PINNED_LOCAL_SNAPSHOT")
            self.assertFalse(first.get("allows_candidate_generation", False))


if __name__ == "__main__":
    unittest.main()
