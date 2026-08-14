import hashlib
import importlib.util
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


receipt_validator = load(
    "live_activation_receipt",
    ROOT / "scripts" / "modelscope_abot_live_activation_receipt.py",
)


class LiveActivationReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 2, 3)
        (self.root / "frame.png").write_bytes(self.png)
        self.receipt_path = self.root / "receipt.json"
        self.receipt = {
            "schema": receipt_validator.RECEIPT_SCHEMA,
            "provider_id": receipt_validator.PROVIDER_ID,
            "authorization": {
                "source": "interactive_user_instruction",
                "owner_confirmed": True,
                "scope": "one_shot_browser_smoke",
                "persistent_registration_authorized": False,
            },
            "observations": {
                "start_observed": True,
                "gpu_allocated": True,
                "stream_observed": True,
                "max_observed_fps": 2.0,
                "stop_requested": True,
                "stop_observed": True,
                "post_stop_ready": True,
                "post_stop_iframe_count": 0,
            },
            "execution": {
                "network_request_sent": True,
                "studio_start_called": True,
                "execution_attempted": True,
                "runtime_admitted": False,
                "mcp_registered": False,
                "persistent_runtime": False,
            },
            "artifact": {
                "ref": "frame.png",
                "sha256": hashlib.sha256(self.png).hexdigest(),
                "bytes": len(self.png),
                "width": 2,
                "height": 3,
                "content_type": "image/png",
                "evidence_type": "presentation_screenshot",
            },
        }
        self.receipt_path.write_text(json.dumps(self.receipt))

    def tearDown(self):
        self.temp.cleanup()

    def validate(self, receipt=None):
        value = self.receipt if receipt is None else receipt
        self.receipt_path.write_text(json.dumps(value))
        return receipt_validator.validate_live_activation_receipt(value, self.receipt_path)

    def test_valid_bounded_live_activation_receipt(self):
        result = self.validate()
        self.assertTrue(result["valid"])
        self.assertTrue(result["live_activation_verified"])
        self.assertTrue(result["lifecycle_closed"])
        self.assertFalse(result["runtime_admitted"])

    def test_open_persistence_or_incomplete_stop_fails_closed(self):
        receipt = json.loads(json.dumps(self.receipt))
        receipt["execution"]["persistent_runtime"] = True
        receipt["observations"]["stop_observed"] = False
        result = self.validate(receipt)
        self.assertIn("persistent_runtime_must_be_false", result["violations"])
        self.assertIn("stop_observed_not_true", result["violations"])

    def test_artifact_tampering_and_path_escape_fail_closed(self):
        (self.root / "frame.png").write_bytes(self.png + b"tampered")
        self.assertIn("artifact_sha256_mismatch", self.validate()["violations"])
        receipt = json.loads(json.dumps(self.receipt))
        receipt["artifact"]["ref"] = "../frame.png"
        self.assertIn("artifact_ref_outside_evidence_root", self.validate(receipt)["violations"])


if __name__ == "__main__":
    unittest.main()
