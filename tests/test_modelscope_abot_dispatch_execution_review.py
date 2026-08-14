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


review = load("review", ROOT / "scripts" / "modelscope_abot_dispatch_execution_review.py")
NOW = 1_786_600_000_000


class DispatchExecutionReviewTests(unittest.TestCase):
    def setUp(self):
        self.proposal = {
            "schema": review.PROPOSAL_SCHEMA,
            "provider_id": review.PROVIDER_ID,
            "authorization_id": "gate7p-auth-0001",
            "attempt_id": "gate7p-attempt-0001",
            "dispatch_envelope_sha256": "12" * 32,
            "action": review.ACTION,
            "endpoint": review.ENDPOINT,
            "issued_at_unix_ms": NOW,
            "expires_at_unix_ms": NOW + review.MAX_TTL_MS,
            "authorization_proposed": True,
            "dispatch_authorized": False,
            "dispatch_performed": False,
            "network_request_sent": False,
            "subprocess_started": False,
            "studio_start_called": False,
            "execution_authorized": False,
            "runtime_admitted": False,
            "mcp_registered": False,
            "plan_only": True,
        }

    def review(self, **changes):
        args = {
            "authorization_proposal": self.proposal,
            "provider_live_verified": True,
            "runtime_config_verified": True,
            "network_policy_verified": True,
            "owner_authority_bound": True,
            "now_unix_ms": NOW,
        }
        args.update(changes)
        return review.review_dispatch_execution(**args)

    def test_review_remains_blocked_even_with_prerequisites(self):
        result = self.review()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"], ["separate_runtime_execution_authority_required"])
        self.assertFalse(result["eligible_for_execution"])
        self.assertFalse(result["dispatch_authorized"])
        self.assertFalse(result["execution_authorized"])
        self.assertTrue(result["review_only"])

    def test_incomplete_review_inputs_fail_closed(self):
        with self.assertRaisesRegex(review.DispatchExecutionReviewError, "inputs"):
            self.review(provider_live_verified=False)
        with self.assertRaisesRegex(review.DispatchExecutionReviewError, "inputs"):
            self.review(owner_authority_bound=False)

    def test_proposal_boundary_target_and_expiry_fail_closed(self):
        with self.assertRaisesRegex(review.DispatchExecutionReviewError, "boundary"):
            self.review(authorization_proposal={**self.proposal, "dispatch_authorized": True})
        with self.assertRaisesRegex(review.DispatchExecutionReviewError, "target"):
            self.review(authorization_proposal={**self.proposal, "endpoint": "/other"})
        with self.assertRaisesRegex(review.DispatchExecutionReviewError, "expired"):
            self.review(now_unix_ms=NOW + review.MAX_TTL_MS)


if __name__ == "__main__":
    unittest.main()
