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


review = load("enablement_review", ROOT / "scripts" / "modelscope_abot_runtime_enablement_review.py")


class RuntimeEnablementReviewTests(unittest.TestCase):
    def setUp(self):
        self.owner_review = {
            "schema": review.OWNER_REVIEW_SCHEMA,
            "provider_id": review.PROVIDER_ID,
            "packet_id": "gate7s-packet-0001",
            "status": "blocked",
            "authority_issued": False,
            "review_only": True,
        }
        self.manifest = {
            "schema": review.MANIFEST_SCHEMA,
            "provider_id": review.PROVIDER_ID,
            "manifest_id": "gate7s-manifest-0001",
            "default_off": True,
            "dry_run_only": True,
            "runtime_implementation_present": False,
            "mcp_registration_present": False,
            "network_dispatcher_present": False,
            "subprocess_executor_present": False,
            "bearer_token_custody_present": False,
            "caller_count": 0,
            "allowlist": [],
        }

    def test_static_review_passes_but_enablement_remains_blocked(self):
        result = review.review_runtime_enablement(
            owner_review=self.owner_review, manifest=self.manifest
        )
        self.assertTrue(result["implementation_review_passed"])
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["runtime_enablement_admitted"])
        self.assertFalse(result["runtime_implementation_enabled"])
        self.assertFalse(result["mcp_registered"])
        self.assertTrue(result["review_only"])

    def test_open_enablement_surfaces_fail_closed(self):
        with self.assertRaisesRegex(review.RuntimeEnablementReviewError, "surface"):
            review.review_runtime_enablement(
                owner_review=self.owner_review,
                manifest={**self.manifest, "network_dispatcher_present": True},
            )
        with self.assertRaisesRegex(review.RuntimeEnablementReviewError, "caller"):
            review.review_runtime_enablement(
                owner_review=self.owner_review,
                manifest={**self.manifest, "caller_count": 1},
            )

    def test_owner_review_and_default_off_flags_fail_closed(self):
        with self.assertRaisesRegex(review.RuntimeEnablementReviewError, "owner admission"):
            review.review_runtime_enablement(
                owner_review={**self.owner_review, "authority_issued": True},
                manifest=self.manifest,
            )
        with self.assertRaisesRegex(review.RuntimeEnablementReviewError, "manifest"):
            review.review_runtime_enablement(
                owner_review=self.owner_review,
                manifest={**self.manifest, "default_off": False},
            )


if __name__ == "__main__":
    unittest.main()
