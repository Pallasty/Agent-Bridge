from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
VOICE = ROOT / "docs/design/voice-scene"
RESULT = VOICE / "s638_story_render_artifact_identity_and_python_package.json"
SCHEMA = VOICE / "story_render_artifact_identity_and_python_package.schema.json"
ADR = VOICE / "S638_STORY_RENDER_ARTIFACT_IDENTITY_AND_PYTHON_PACKAGE.md"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class StoryRenderArtifactPackageContractTests(unittest.TestCase):
    def test_receipt_schema_hashes_and_authority_are_exact(self) -> None:
        result = json.loads(RESULT.read_text())
        jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text())).validate(result)
        receipt = dict(result); expected = receipt.pop("receipt_sha256")
        self.assertEqual(expected, hashlib.sha256(canonical(receipt)).hexdigest())
        for row in result["source_evidence"]:
            self.assertEqual(row["sha256"], hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest())
        self.assertTrue(all(value is False for value in result["authority"].values()))

    def test_claims_do_not_launder_control_package_into_inference_readiness(self) -> None:
        result = json.loads(RESULT.read_text())
        self.assertTrue(result["claims"]["descriptor_stable_control_launch_verified"])
        self.assertFalse(result["claims"]["real_inference_python_ready"])
        self.assertFalse(result["claims"]["real_render_executable"])
        self.assertEqual(result["next_gate"]["id"], "S639")
        adr = ADR.read_text()
        self.assertIn("offline", adr)
        self.assertIn("inference wheelhouse", adr)


if __name__ == "__main__":
    unittest.main()
