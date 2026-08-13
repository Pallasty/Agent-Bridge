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


admission = load(
    "admission", ROOT / "scripts" / "modelscope_abot_execution_admission.py"
)
attempt = load("attempt", ROOT / "scripts" / "modelscope_abot_execution_attempt.py")
NOW = 1_786_600_000_000


class ExecutionAttemptTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "schema": attempt.PLAN_SCHEMA,
            "provider_id": attempt.PROVIDER_ID,
            "activation_id": "gate7k-activation-0001",
            "capability_id": "gate7k-capability-0001",
            "capability_sha256": "12" * 32,
            "capability_digest_bound": True,
            "plan_only": True,
            "adapter": {
                "action": admission.ACTION,
                "endpoint": admission.ENDPOINT,
                "timeout_ms": admission.MAX_TTL_MS,
                "network_allowed": False,
                "subprocess_allowed": False,
            },
            "execution_capability_issued": False,
            "studio_start_called": False,
            "execution_authorized": False,
            "runtime_admitted": False,
            "mcp_registered": False,
        }
        self.admission = admission.admit_execution(
            adapter_plan=self.plan,
            owner_confirmation=True,
            runtime_opt_in=True,
            now_unix_ms=NOW,
        )

    def prepare(self, **changes):
        args = {
            "adapter_plan": self.plan,
            "admission_receipt": self.admission,
            "attempt_id": "gate7l-attempt-0001",
            "now_unix_ms": NOW,
            "timeout_ms": 30_000,
        }
        args.update(changes)
        return attempt.prepare_attempt(**args)

    def test_preflight_is_non_actuating_and_expiry_bounded(self):
        result = self.prepare()
        self.assertEqual(result["expires_at_unix_ms"], NOW + 30_000)
        for field in (
            "network_request_sent",
            "subprocess_started",
            "studio_start_called",
            "execution_attempted",
            "runtime_admitted",
            "mcp_registered",
        ):
            self.assertFalse(result[field])

    def test_plan_digest_mismatch_and_expiry_fail_closed(self):
        changed_plan = {**self.plan, "plan_only": False}
        with self.assertRaisesRegex(attempt.ExecutionAttemptError, "adapter plan"):
            self.prepare(adapter_plan=changed_plan)
        changed_plan = {**self.plan, "capability_id": "different-capability"}
        with self.assertRaisesRegex(attempt.ExecutionAttemptError, "admission receipt"):
            self.prepare(adapter_plan=changed_plan)
        with self.assertRaisesRegex(attempt.ExecutionAttemptError, "expired"):
            self.prepare(now_unix_ms=NOW + 30_000, timeout_ms=1)

    def test_open_or_malformed_inputs_fail_closed(self):
        opened = {**self.admission, "runtime_admitted": True}
        with self.assertRaisesRegex(attempt.ExecutionAttemptError, "boundary"):
            self.prepare(admission_receipt=opened)
        with self.assertRaisesRegex(attempt.ExecutionAttemptError, "attempt id"):
            self.prepare(attempt_id="x")
        with self.assertRaisesRegex(attempt.ExecutionAttemptError, "timeout"):
            self.prepare(timeout_ms=30_001)


if __name__ == "__main__":
    unittest.main()
