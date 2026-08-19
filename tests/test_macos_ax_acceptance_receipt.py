import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "macos_accept"))

from macos_ax_acceptance_receipt import build_receipt, validate_receipt


def _probe():
    return {
        "schema": "macos_ax_probe/v0",
        "read_only": True,
        "status": "ready",
        "permission": {"ax_trusted": True, "prompted": False},
        "frontmost_app": {"name": "Example", "pid": 42},
        "windows": [
            {
                "index": 0,
                "ax_identifier": "main",
                "role": "AXWindow",
                "identity": {
                    "kind": "ax_identifier",
                    "value": "main",
                    "stable_across_samples": True,
                },
            },
            {
                "index": 1,
                "ax_identifier": None,
                "role": "AXWindow",
                "identity": {
                    "kind": "sample_index",
                    "value": "1",
                    "stable_across_samples": False,
                },
            },
        ],
        "limits": {"max_windows": 8, "truncated": False},
        "errors": [],
    }


def _verified(expect):
    return {"schema": "macos_ax_verify/v0", "expect": expect, "verdict": "verified", "recover": "proceed"}


class MacosAxAcceptanceReceiptTests(unittest.TestCase):
    def _receipt(self):
        return build_receipt(
            source_commit="a" * 40,
            probe_script=ROOT / "scripts" / "macos_ax_probe.py",
            verify_script=ROOT / "scripts" / "macos_ax_verify.py",
            probe=_probe(),
            trust_verify=_verified("ax_trusted_is"),
            app_verify=_verified("frontmost_app_is"),
            window_verify=_verified("window_appeared"),
        )

    def test_valid_receipt_passes_with_mixed_identity_coverage(self):
        receipt = self._receipt()
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["identity_coverage"]["stable_ax_identifier_count"], 1)
        self.assertEqual(receipt["identity_coverage"]["sample_local_index_count"], 1)
        self.assertEqual(validate_receipt(receipt), [])

    def test_failed_postcondition_is_rejected(self):
        receipt = self._receipt()
        receipt["checks"][-1]["passed"] = False
        receipt["status"] = "failed"
        errors = validate_receipt(receipt)
        self.assertIn("required_check_failed", errors)
        self.assertIn("status_not_passed", errors)

    def test_payload_tampering_is_rejected(self):
        receipt = self._receipt()
        tampered = copy.deepcopy(receipt)
        tampered["phases"]["probe"]["payload"]["status"] = "degraded"
        self.assertIn("probe_payload_digest_invalid", validate_receipt(tampered))


if __name__ == "__main__":
    unittest.main()
