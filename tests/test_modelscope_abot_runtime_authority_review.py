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


review = load("authority_review", ROOT / "scripts" / "modelscope_abot_runtime_authority_review.py")
NOW = 1_786_600_000_000


class RuntimeAuthorityReviewTests(unittest.TestCase):
    def setUp(self):
        self.dispatch_review = {
            "schema": review.DISPATCH_REVIEW_SCHEMA,
            "provider_id": review.PROVIDER_ID,
            "authorization_id": "gate7q-auth-0001",
            "dispatch_envelope_sha256": "12" * 32,
            "status": "blocked",
            "eligible_for_execution": False,
            "dispatch_authorized": False,
            "execution_authorized": False,
            "review_only": True,
        }
        self.request = {
            "schema": review.REQUEST_SCHEMA,
            "provider_id": review.PROVIDER_ID,
            "request_id": "gate7q-request-0001",
            "scope": review.SCOPE,
            "action": review.ACTION,
            "endpoint": review.ENDPOINT,
            "dispatch_review_sha256": review._digest(self.dispatch_review),
            "requested_at_unix_ms": NOW,
            "requested_ttl_ms": review.MAX_TTL_MS,
        }

    def review(self, **changes):
        args = {
            "dispatch_review": self.dispatch_review,
            "authority_request": self.request,
            "owner_reauthorized": True,
            "runtime_sandbox_verified": True,
            "secret_custody_verified": True,
            "rollback_verified": True,
            "now_unix_ms": NOW,
        }
        args.update(changes)
        return review.review_runtime_authority(**args)

    def test_review_never_issues_authority(self):
        result = self.review()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"], ["authority_issuance_requires_separate_owner_decision"])
        self.assertFalse(result["authority_issued"])
        self.assertFalse(result["bearer_token_created"])
        self.assertFalse(result["runtime_admitted"])
        self.assertTrue(result["review_only"])

    def test_missing_evidence_fails_closed(self):
        with self.assertRaisesRegex(review.RuntimeAuthorityReviewError, "inputs"):
            self.review(secret_custody_verified=False)
        with self.assertRaisesRegex(review.RuntimeAuthorityReviewError, "inputs"):
            self.review(owner_reauthorized=False)

    def test_request_and_review_binding_fail_closed(self):
        with self.assertRaisesRegex(review.RuntimeAuthorityReviewError, "binding"):
            self.review(authority_request={**self.request, "dispatch_review_sha256": "ff" * 32})
        with self.assertRaisesRegex(review.RuntimeAuthorityReviewError, "request"):
            self.review(authority_request={**self.request, "scope": "other.scope"})
        with self.assertRaisesRegex(review.RuntimeAuthorityReviewError, "boundary"):
            self.review(dispatch_review={**self.dispatch_review, "execution_authorized": True})


if __name__ == "__main__":
    unittest.main()
