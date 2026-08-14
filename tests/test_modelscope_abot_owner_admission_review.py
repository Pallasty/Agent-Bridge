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


review = load("owner_review", ROOT / "scripts" / "modelscope_abot_owner_admission_review.py")
NOW = 1_786_600_000_000


class OwnerAdmissionReviewTests(unittest.TestCase):
    def setUp(self):
        self.q_review = {
            "schema": review.Q_REVIEW_SCHEMA,
            "provider_id": review.PROVIDER_ID,
            "request_id": "gate7r-request-0001",
            "status": "blocked",
            "authority_issued": False,
            "review_only": True,
        }
        self.packet = {
            "schema": review.PACKET_SCHEMA,
            "provider_id": review.PROVIDER_ID,
            "packet_id": "gate7r-packet-0001",
            "owner_decision_id": "gate7r-decision-0001",
            "owner_decision_sha256": "12" * 32,
            "authority_review_sha256": review._digest(self.q_review),
            "scope": review.SCOPE,
            "action": review.ACTION,
            "endpoint": review.ENDPOINT,
            "issued_at_unix_ms": NOW,
            "expires_at_unix_ms": NOW + review.MAX_TTL_MS,
            "owner_authorized": True,
            "authority_issued": False,
            "bearer_token_created": False,
            "dispatch_authorized": False,
            "execution_authorized": False,
            "runtime_admitted": False,
            "network_request_sent": False,
            "subprocess_started": False,
            "studio_start_called": False,
            "mcp_registered": False,
        }

    def review(self, **changes):
        args = {"q_review": self.q_review, "admission_packet": self.packet, "now_unix_ms": NOW}
        args.update(changes)
        return review.review_owner_admission_packet(**args)

    def test_owner_packet_is_validated_but_not_admitted(self):
        result = self.review()
        self.assertTrue(result["admission_packet_valid"])
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["authority_issued"])
        self.assertFalse(result["bearer_token_created"])
        self.assertFalse(result["runtime_admitted"])
        self.assertTrue(result["review_only"])

    def test_lineage_target_and_boundary_fail_closed(self):
        with self.assertRaisesRegex(review.OwnerAdmissionReviewError, "binding"):
            self.review(admission_packet={**self.packet, "authority_review_sha256": "ff" * 32})
        with self.assertRaisesRegex(review.OwnerAdmissionReviewError, "packet"):
            self.review(admission_packet={**self.packet, "endpoint": "/other"})
        with self.assertRaisesRegex(review.OwnerAdmissionReviewError, "boundary"):
            self.review(admission_packet={**self.packet, "authority_issued": True})

    def test_expired_or_invalid_upstream_review_fails_closed(self):
        with self.assertRaisesRegex(review.OwnerAdmissionReviewError, "expired"):
            self.review(now_unix_ms=NOW + review.MAX_TTL_MS)
        with self.assertRaisesRegex(review.OwnerAdmissionReviewError, "review"):
            self.review(q_review={**self.q_review, "authority_issued": True})


if __name__ == "__main__":
    unittest.main()
