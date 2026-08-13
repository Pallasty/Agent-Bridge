import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "preflight_abot_world_runtime.py"
SPEC = importlib.util.spec_from_file_location("abot_runtime_preflight", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AbotWorldRuntimePreflightTests(unittest.TestCase):
    def test_preflight_never_attempts_load_or_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            result = MODULE.preflight(Path(directory))
            admission = result["admission"]
            self.assertFalse(admission["load_attempted"])
            self.assertFalse(admission["inference_attempted"])
            self.assertFalse(admission["runtime_admitted"])
            self.assertIn("missing_checkpoint_files", " ".join(admission["reasons"]))

    def test_checkpoint_presence_is_reported_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in MODULE.REQUIRED_CHECKPOINTS:
                (root / name).touch()
            result = MODULE.preflight(root)
            self.assertTrue(all(result["checkpoint_files"].values()))
            self.assertFalse(result["admission"]["load_attempted"])


if __name__ == "__main__":
    unittest.main()
