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


activation_review = load(
    "runtime_activation_decision",
    ROOT / "scripts" / "modelscope_abot_runtime_activation_decision.py",
)


class RuntimeActivationDecisionTests(unittest.TestCase):
    def setUp(self):
        self.gate7w_review = {
            "schema": activation_review.GATE7W_SCHEMA,
            "provider_id": activation_review.PROVIDER_ID,
            "status": "blocked",
            "review_only": True,
            "runtime_admitted": False,
            "execution_authorized": False,
        }
        self.decision = {
            "schema": activation_review.DECISION_SCHEMA,
            "provider_id": activation_review.PROVIDER_ID,
            "decision_id": "gate7x-decision-0001",
            "decision": "defer",
            "authority_issued": False,
            "activation_requested": False,
            "execution_authorized": False,
            "reason": "Keep ModelScope outside the executable runtime until an explicit activation receipt exists.",
        }

    def test_defer_records_without_activation(self):
        result = activation_review.review_runtime_activation_decision(
            gate7w_review=self.gate7w_review, decision=self.decision
        )
        self.assertEqual(result["status"], "deferred")
        self.assertTrue(result["decision_recorded"])
        self.assertTrue(result["review_only"])
        self.assertFalse(result["activation_admitted"])
        self.assertFalse(result["runtime_admitted"])

    def test_reject_is_allowed_but_approve_is_not(self):
        result = activation_review.review_runtime_activation_decision(
            gate7w_review=self.gate7w_review,
            decision={**self.decision, "decision": "reject"},
        )
        self.assertEqual(result["status"], "rejected")
        with self.assertRaisesRegex(activation_review.RuntimeActivationDecisionError, "defer/reject"):
            activation_review.review_runtime_activation_decision(
                gate7w_review=self.gate7w_review,
                decision={**self.decision, "decision": "approve"},
            )

    def test_gate7w_or_open_request_fails_closed(self):
        with self.assertRaisesRegex(activation_review.RuntimeActivationDecisionError, "Gate 7W"):
            activation_review.review_runtime_activation_decision(
                gate7w_review={**self.gate7w_review, "runtime_admitted": True},
                decision=self.decision,
            )
        with self.assertRaisesRegex(activation_review.RuntimeActivationDecisionError, "defer/reject"):
            activation_review.review_runtime_activation_decision(
                gate7w_review=self.gate7w_review,
                decision={**self.decision, "activation_requested": True},
            )


if __name__ == "__main__":
    unittest.main()
