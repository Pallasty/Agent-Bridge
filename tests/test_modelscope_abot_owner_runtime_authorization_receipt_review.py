import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


receipt_review = load(
    "owner_runtime_authorization_receipt_review",
    ROOT / "scripts" / "modelscope_abot_owner_runtime_authorization_receipt_review.py",
)


class OwnerRuntimeAuthorizationReceiptReviewTests(unittest.TestCase):
    def setUp(self):
        self.gate7t_review = {
            "schema": receipt_review.GATE7T_SCHEMA,
            "provider_id": receipt_review.PROVIDER_ID,
            "status": "deferred",
            "review_only": True,
            "runtime_admitted": False,
        }
        self.absent_receipt = {
            "schema": receipt_review.RECEIPT_SCHEMA,
            "provider_id": receipt_review.PROVIDER_ID,
            "receipt_id": "gate7u-receipt-absent-0001",
            "status": "absent",
            "authority_issued": False,
            "execution_authorized": False,
        }
        self.issued_receipt = {
            "schema": receipt_review.RECEIPT_SCHEMA,
            "provider_id": receipt_review.PROVIDER_ID,
            "receipt_id": "gate7u-receipt-issued-0001",
            "status": "issued",
            "authority_issued": True,
            "runtime_enablement_authorized": True,
            "execution_authorized": False,
            "owner_principal": "owner:explicit",
            "issued_at": "2026-08-13T20:00:00Z",
            "scope": "modelscope-abot-runtime-enable-review",
        }

    def test_missing_receipt_blocks_without_admission(self):
        result = receipt_review.review_owner_runtime_authorization_receipt(
            gate7t_review=self.gate7t_review, receipt=self.absent_receipt
        )
        self.assertEqual(result["status"], "blocked_missing_receipt")
        self.assertEqual(result["blockers"], ["owner_authorization_receipt_missing"])
        self.assertFalse(result["authorization_receipt_validated"])
        self.assertFalse(result["runtime_enablement_admitted"])
        self.assertFalse(result["execution_authorized"])

    def test_issued_receipt_still_requires_implementation_gate(self):
        result = receipt_review.review_owner_runtime_authorization_receipt(
            gate7t_review=self.gate7t_review, receipt=self.issued_receipt
        )
        self.assertEqual(result["status"], "blocked_implementation_gate")
        self.assertTrue(result["authorization_receipt_validated"])
        self.assertTrue(result["owner_authorization_issued"])
        self.assertFalse(result["runtime_admitted"])
        self.assertFalse(result["execution_authorized"])

    def test_invalid_receipts_and_open_gate_fail_closed(self):
        with self.assertRaisesRegex(receipt_review.OwnerRuntimeAuthorizationReceiptError, "never execution"):
            receipt_review.review_owner_runtime_authorization_receipt(
                gate7t_review=self.gate7t_review,
                receipt={**self.absent_receipt, "execution_authorized": True},
            )
        with self.assertRaisesRegex(receipt_review.OwnerRuntimeAuthorizationReceiptError, "issued receipt"):
            receipt_review.review_owner_runtime_authorization_receipt(
                gate7t_review=self.gate7t_review,
                receipt={**self.issued_receipt, "authority_issued": False},
            )
        with self.assertRaisesRegex(receipt_review.OwnerRuntimeAuthorizationReceiptError, "Gate 7T"):
            receipt_review.review_owner_runtime_authorization_receipt(
                gate7t_review={**self.gate7t_review, "runtime_admitted": True},
                receipt=self.absent_receipt,
            )


if __name__ == "__main__":
    unittest.main()
