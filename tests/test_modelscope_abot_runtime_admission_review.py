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


admission_review = load(
    "runtime_admission_review",
    ROOT / "scripts" / "modelscope_abot_runtime_admission_review.py",
)


class RuntimeAdmissionReviewTests(unittest.TestCase):
    def setUp(self):
        self.gate7u_review = {
            "schema": admission_review.GATE7U_SCHEMA,
            "provider_id": admission_review.PROVIDER_ID,
            "status": "blocked_implementation_gate",
            "authorization_receipt_validated": True,
            "review_only": True,
            "runtime_admitted": False,
        }
        self.gate7v_review = {
            "schema": admission_review.GATE7V_SCHEMA,
            "provider_id": admission_review.PROVIDER_ID,
            "status": "review_passed_blocked",
            "implementation_review_passed": True,
            "review_only": True,
            "runtime_admitted": False,
        }
        self.request = {
            "schema": admission_review.ADMISSION_SCHEMA,
            "provider_id": admission_review.PROVIDER_ID,
            "request_id": "gate7w-request-0001",
            "admission_requested": False,
            "default_off": True,
            "dry_run_only": True,
            "runtime_admitted": False,
            "execution_authorized": False,
            "mcp_registration_enabled": False,
            "network_dispatcher_enabled": False,
            "subprocess_executor_enabled": False,
            "bearer_token_created": False,
        }

    def test_unrequested_admission_is_blocked(self):
        result = admission_review.review_runtime_admission(
            gate7u_review=self.gate7u_review,
            gate7v_review=self.gate7v_review,
            request=self.request,
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("runtime_admission_not_requested", result["blockers"])
        self.assertFalse(result["admission_review_passed"])
        self.assertFalse(result["runtime_admitted"])

    def test_complete_request_passes_review_but_not_activation(self):
        result = admission_review.review_runtime_admission(
            gate7u_review=self.gate7u_review,
            gate7v_review=self.gate7v_review,
            request={**self.request, "admission_requested": True},
        )
        self.assertEqual(result["status"], "review_passed_blocked")
        self.assertTrue(result["admission_review_passed"])
        self.assertFalse(result["runtime_enablement_admitted"])
        self.assertFalse(result["execution_authorized"])

    def test_incomplete_evidence_blocks(self):
        result = admission_review.review_runtime_admission(
            gate7u_review={**self.gate7u_review, "authorization_receipt_validated": False},
            gate7v_review={**self.gate7v_review, "implementation_review_passed": False},
            request={**self.request, "admission_requested": True},
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("owner_authorization_receipt_not_validated", result["blockers"])
        self.assertIn("runtime_implementation_review_not_passed", result["blockers"])

    def test_open_surface_or_bad_evidence_fails_closed(self):
        with self.assertRaisesRegex(admission_review.RuntimeAdmissionReviewError, "surface open"):
            admission_review.review_runtime_admission(
                gate7u_review=self.gate7u_review,
                gate7v_review=self.gate7v_review,
                request={**self.request, "network_dispatcher_enabled": True},
            )
        with self.assertRaisesRegex(admission_review.RuntimeAdmissionReviewError, "Gate 7V"):
            admission_review.review_runtime_admission(
                gate7u_review=self.gate7u_review,
                gate7v_review={**self.gate7v_review, "runtime_admitted": True},
                request=self.request,
            )


if __name__ == "__main__":
    unittest.main()
