import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "admission", ROOT / "scripts" / "modelscope_abot_execution_admission.py"
)
admission = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = admission
spec.loader.exec_module(admission)
NOW = 1_786_600_000_000


class ExecutionAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "schema": admission.PLAN_SCHEMA,
            "provider_id": admission.PROVIDER_ID,
            "plan_only": True,
            "adapter": {
                "network_allowed": False,
                "subprocess_allowed": False,
            },
            "execution_capability_issued": False,
            "studio_start_called": False,
            "execution_authorized": False,
            "runtime_admitted": False,
            "mcp_registered": False,
        }

    def admit(self, **changes):
        args = {
            "adapter_plan": self.plan,
            "owner_confirmation": True,
            "runtime_opt_in": True,
            "now_unix_ms": NOW,
        }
        args.update(changes)
        return admission.admit_execution(**args)

    def test_explicit_admission_still_does_not_execute(self):
        result = self.admit()
        self.assertEqual(result["expires_at_unix_ms"], NOW + 30_000)
        for field in (
            "execution_attempted",
            "studio_start_called",
            "network_request_sent",
            "subprocess_started",
            "runtime_admitted",
        ):
            self.assertFalse(result[field])

    def test_missing_explicit_consent_fails_closed(self):
        with self.assertRaisesRegex(admission.ExecutionAdmissionError, "owner confirmation"):
            self.admit(owner_confirmation=False)
        with self.assertRaisesRegex(admission.ExecutionAdmissionError, "runtime opt-in"):
            self.admit(runtime_opt_in=False)

    def test_nested_boundary_and_ttl_are_bounded(self):
        opened = {
            **self.plan,
            "adapter": {**self.plan["adapter"], "network_allowed": True},
        }
        with self.assertRaisesRegex(admission.ExecutionAdmissionError, "boundary"):
            self.admit(adapter_plan=opened)
        with self.assertRaisesRegex(admission.ExecutionAdmissionError, "ttl"):
            self.admit(requested_ttl_ms=30_001)


if __name__ == "__main__":
    unittest.main()
