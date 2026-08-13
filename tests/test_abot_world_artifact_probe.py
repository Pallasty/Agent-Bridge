import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "probe_abot_world_artifact.py"
SPEC = importlib.util.spec_from_file_location("abot_probe", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AbotWorldArtifactProbeTests(unittest.TestCase):
    def test_inventory_is_metadata_only_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text('{"model_type":"ti2v"}', encoding="utf-8")
            (root / "weights.safetensors").write_bytes(b"not loaded")

            result = MODULE.inventory(root)

            self.assertEqual(result["schema"], "agent_bridge.abot_world_artifact_probe.v0")
            self.assertFalse(result["probe"]["model_loaded"])
            self.assertFalse(result["probe"]["inference_executed"])
            self.assertFalse(result["probe"]["weights_content_hashed"])
            self.assertNotIn("sha256", result["files"][1])
            self.assertEqual(result["model"]["metadata"]["config.json"]["model_type"], "ti2v")

    def test_content_hash_is_explicit_and_manifest_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "configuration.json").write_text('{"task":"any-to-any"}', encoding="utf-8")
            (root / "weights.bin").write_bytes(b"weights")

            first = MODULE.inventory(root, hash_content=True)
            second = MODULE.inventory(root, hash_content=True)

            self.assertTrue(first["probe"]["weights_content_hashed"])
            self.assertEqual(first["artifact_manifest_sha256"], second["artifact_manifest_sha256"])
            weights = next(item for item in first["files"] if item["path"] == "weights.bin")
            self.assertEqual(weights["sha256"], MODULE.sha256_bytes(b"weights"))

    def test_json_output_is_serializable(self):
        with tempfile.TemporaryDirectory() as directory:
            result = MODULE.inventory(Path(directory))
            json.dumps(result)


if __name__ == "__main__":
    unittest.main()
