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


decision_review = load(
    "owner_runtime_enablement_decision",
    ROOT / "scripts" / "modelscope_abot_owner_runtime_enablement_decision.py",
)


class OwnerRuntimeEnablementDecisionTests(unittest.TestCase):
    def setUp(self):
        self.gate7s_review = {
            "schema": "agent_bridge.modelscope_abot_runtime_enablement_review.v0",
            "provider_id": decision_review.PROVIDER_ID,
            "packet_id": "gate7s-packet-0001",
            "status": "blocked",
            "runtime_enablement_admitted": False,
            "runtime_admitted": False,
            "review_only": True,
        }
        self.decision = {
            "schema": decision_review.DECISION_SCHEMA,
            "provider_id": decision_review.PROVIDER_ID,
            "decision_id": "gate7t-decision-0001",
            "decision": "defer",
            "authority_issued": False,
            "runtime_enablement_requested": False,
            "reason": "Keep the provider outside the executable runtime until a separate owner receipt exists.",
        }

    def test_defer_records_decision_without_runtime_admission(self):
        result = decision_review.review_owner_runtime_enablement_decision(
            gate7s_review=self.gate7s_review, decision=self.decision
        )
        self.assertEqual(result["status"], "deferred")
        self.assertTrue(result["decision_recorded"])
        self.assertTrue(result["review_only"])
        self.assertFalse(result["owner_authorization_issued"])
        self.assertFalse(result["runtime_enablement_admitted"])
        self.assertFalse(result["runtime_implementation_enabled"])
        self.assertFalse(result["execution_authorized"])

    def test_reject_is_allowed_but_approve_is_not(self):
        result = decision_review.review_owner_runtime_enablement_decision(
            gate7s_review=self.gate7s_review,
            decision={**self.decision, "decision": "reject"},
        )
        self.assertEqual(result["status"], "rejected")
        with self.assertRaisesRegex(decision_review.OwnerRuntimeEnablementDecisionError, "defer/reject"):
            decision_review.review_owner_runtime_enablement_decision(
                gate7s_review=self.gate7s_review,
                decision={**self.decision, "decision": "approve"},
            )

    def test_gate7s_or_open_request_fails_closed(self):
        with self.assertRaisesRegex(decision_review.OwnerRuntimeEnablementDecisionError, "Gate 7S"):
            decision_review.review_owner_runtime_enablement_decision(
                gate7s_review={**self.gate7s_review, "runtime_admitted": True},
                decision=self.decision,
            )
        with self.assertRaisesRegex(decision_review.OwnerRuntimeEnablementDecisionError, "defer/reject"):
            decision_review.review_owner_runtime_enablement_decision(
                gate7s_review=self.gate7s_review,
                decision={**self.decision, "runtime_enablement_requested": True},
            )


if __name__ == "__main__":
    unittest.main()
