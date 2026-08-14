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


implementation_review = load(
    "independent_runtime_implementation_review",
    ROOT / "scripts" / "modelscope_abot_independent_runtime_implementation_review.py",
)


class IndependentRuntimeImplementationReviewTests(unittest.TestCase):
    def setUp(self):
        self.gate7u_review = {
            "schema": implementation_review.GATE7U_SCHEMA,
            "provider_id": implementation_review.PROVIDER_ID,
            "status": "blocked_missing_receipt",
            "review_only": True,
            "runtime_admitted": False,
        }
        self.candidate = {
            "schema": implementation_review.IMPLEMENTATION_SCHEMA,
            "provider_id": implementation_review.PROVIDER_ID,
            "implementation_id": "gate7v-candidate-0001",
            "implementation_present": True,
            "runtime_admission_present": False,
            **{control: True for control in implementation_review.REQUIRED_CONTROLS},
        }

    def test_absent_implementation_is_blocked(self):
        result = implementation_review.review_independent_runtime_implementation(
            gate7u_review=self.gate7u_review,
            candidate={**self.candidate, "implementation_present": False},
        )
        self.assertEqual(result["status"], "blocked_implementation_absent")
        self.assertFalse(result["implementation_review_passed"])
        self.assertFalse(result["runtime_admitted"])

    def test_incomplete_controls_fail_closed(self):
        result = implementation_review.review_independent_runtime_implementation(
            gate7u_review=self.gate7u_review,
            candidate={**self.candidate, "rollback_plan": False, "audit_receipts": False},
        )
        self.assertEqual(result["status"], "blocked_controls_incomplete")
        self.assertEqual(
            result["blockers"],
            ["runtime_control_missing:audit_receipts", "runtime_control_missing:rollback_plan"],
        )

    def test_complete_candidate_remains_blocked_at_admission_boundary(self):
        result = implementation_review.review_independent_runtime_implementation(
            gate7u_review=self.gate7u_review, candidate=self.candidate
        )
        self.assertEqual(result["status"], "review_passed_blocked")
        self.assertTrue(result["implementation_review_passed"])
        self.assertFalse(result["runtime_admission_present"])
        self.assertFalse(result["runtime_implementation_enabled"])
        self.assertFalse(result["execution_authorized"])

    def test_open_admission_or_gate_fails_closed(self):
        with self.assertRaisesRegex(implementation_review.IndependentRuntimeImplementationReviewError, "candidate"):
            implementation_review.review_independent_runtime_implementation(
                gate7u_review=self.gate7u_review,
                candidate={**self.candidate, "runtime_admission_present": True},
            )
        with self.assertRaisesRegex(implementation_review.IndependentRuntimeImplementationReviewError, "Gate 7U"):
            implementation_review.review_independent_runtime_implementation(
                gate7u_review={**self.gate7u_review, "runtime_admitted": True},
                candidate=self.candidate,
            )


if __name__ == "__main__":
    unittest.main()
