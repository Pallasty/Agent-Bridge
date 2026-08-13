import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dispatch = load("dispatch", ROOT / "scripts" / "modelscope_abot_external_dispatch.py")
admission = load("admission_dispatch", ROOT / "scripts" / "modelscope_abot_execution_admission.py")
attempt = load("attempt_dispatch", ROOT / "scripts" / "modelscope_abot_execution_attempt.py")
commit = load("commit_dispatch", ROOT / "scripts" / "modelscope_abot_execution_commit.py")
NOW = 1_786_600_000_000


class ExternalDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.plan = {
            "schema": dispatch.PLAN_SCHEMA,
            "provider_id": dispatch.PROVIDER_ID,
            "activation_id": "gate7n-activation-0001",
            "capability_id": "gate7n-capability-0001",
            "capability_sha256": "12" * 32,
            "capability_digest_bound": True,
            "plan_only": True,
            "adapter": {
                "action": dispatch.ACTION,
                "endpoint": dispatch.ENDPOINT,
                "timeout_ms": dispatch.MAX_TIMEOUT_MS,
                "network_allowed": False,
                "subprocess_allowed": False,
            },
            "execution_capability_issued": False,
            "studio_start_called": False,
            "execution_authorized": False,
            "runtime_admitted": False,
            "mcp_registered": False,
        }
        admitted = admission.admit_execution(
            adapter_plan=self.plan, owner_confirmation=True, runtime_opt_in=True, now_unix_ms=NOW
        )
        self.attempt = attempt.prepare_attempt(
            adapter_plan=self.plan,
            admission_receipt=admitted,
            attempt_id="gate7n-attempt-0001",
            now_unix_ms=NOW,
            timeout_ms=dispatch.MAX_TIMEOUT_MS,
        )
        self.store = commit.ExecutionCommitStore(Path(self.temp.name) / "commit.sqlite3")
        self.commit_receipt = self.store.commit(attempt_receipt=self.attempt, now_unix_ms=NOW)

    def tearDown(self):
        self.temp.cleanup()

    def test_envelope_is_bound_and_non_actuating(self):
        result = dispatch.prepare_dispatch_envelope(
            adapter_plan=self.plan,
            attempt_receipt=self.attempt,
            commit_receipt=self.commit_receipt,
            now_unix_ms=NOW,
            timeout_ms=dispatch.MAX_TIMEOUT_MS,
        )
        self.assertFalse(result["dispatch_ready"])
        self.assertFalse(result["dispatch_performed"])
        self.assertFalse(result["network_request_sent"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(result["attempt_sha256"], commit._digest(self.attempt))

    def test_commit_and_attempt_binding_fail_closed(self):
        with self.assertRaisesRegex(dispatch.ExternalDispatchError, "commit"):
            dispatch.prepare_dispatch_envelope(
                adapter_plan=self.plan,
                attempt_receipt=self.attempt,
                commit_receipt={**self.commit_receipt, "attempt_id": "other-attempt-0001"},
                now_unix_ms=NOW,
                timeout_ms=1,
            )
        with self.assertRaisesRegex(dispatch.ExternalDispatchError, "attempt"):
            dispatch.prepare_dispatch_envelope(
                adapter_plan={**self.plan, "capability_id": "other"},
                attempt_receipt=self.attempt,
                commit_receipt=self.commit_receipt,
                now_unix_ms=NOW,
                timeout_ms=1,
            )

    def test_open_flags_and_timeout_fail_closed(self):
        with self.assertRaisesRegex(dispatch.ExternalDispatchError, "boundary"):
            dispatch.prepare_dispatch_envelope(
                adapter_plan=self.plan,
                attempt_receipt={**self.attempt, "execution_attempted": True},
                commit_receipt=self.commit_receipt,
                now_unix_ms=NOW,
                timeout_ms=1,
            )
        with self.assertRaisesRegex(dispatch.ExternalDispatchError, "timeout"):
            dispatch.prepare_dispatch_envelope(
                adapter_plan=self.plan,
                attempt_receipt=self.attempt,
                commit_receipt=self.commit_receipt,
                now_unix_ms=NOW,
                timeout_ms=30_001,
            )


if __name__ == "__main__":
    unittest.main()
