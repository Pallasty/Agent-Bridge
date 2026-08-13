import importlib.util
import sys
import threading
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


admission = load("admission_commit", ROOT / "scripts" / "modelscope_abot_execution_admission.py")
attempt = load("attempt_commit", ROOT / "scripts" / "modelscope_abot_execution_attempt.py")
commit = load("commit", ROOT / "scripts" / "modelscope_abot_execution_commit.py")
NOW = 1_786_600_000_000


class ExecutionCommitTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store = commit.ExecutionCommitStore(Path(self.temp.name) / "commit.sqlite3")
        plan = {
            "schema": admission.PLAN_SCHEMA,
            "provider_id": admission.PROVIDER_ID,
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
        admitted = admission.admit_execution(
            adapter_plan=plan,
            owner_confirmation=True,
            runtime_opt_in=True,
            now_unix_ms=NOW,
        )
        self.receipt = attempt.prepare_attempt(
            adapter_plan=plan,
            admission_receipt=admitted,
            attempt_id="gate7m-attempt-0001",
            now_unix_ms=NOW,
            timeout_ms=30_000,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_commit_is_single_use_and_non_actuating(self):
        result = self.store.commit(attempt_receipt=self.receipt, now_unix_ms=NOW)
        self.assertTrue(result["commit_recorded"])
        for field in (
            "execution_attempted",
            "network_request_sent",
            "subprocess_started",
            "studio_start_called",
            "runtime_admitted",
            "mcp_registered",
        ):
            self.assertFalse(result[field])
        self.assertEqual(self.store.snapshot()["commit_count"], 1)
        with self.assertRaisesRegex(commit.ExecutionCommitError, "already committed"):
            self.store.commit(attempt_receipt=self.receipt, now_unix_ms=NOW)

    def test_attempt_receipt_binding_and_boundary_are_validated(self):
        with self.assertRaisesRegex(commit.ExecutionCommitError, "invalid"):
            self.store.commit(
                attempt_receipt={**self.receipt, "adapter_plan_sha256": "not-a-digest"},
                now_unix_ms=NOW,
            )
        with self.assertRaisesRegex(commit.ExecutionCommitError, "boundary"):
            self.store.commit(
                attempt_receipt={**self.receipt, "execution_authorized": True},
                now_unix_ms=NOW,
            )
        with self.assertRaisesRegex(commit.ExecutionCommitError, "expired"):
            self.store.commit(
                attempt_receipt={
                    **self.receipt,
                    "prepared_at_unix_ms": NOW,
                    "expires_at_unix_ms": NOW + 30_001,
                },
                now_unix_ms=NOW,
            )
        with self.assertRaisesRegex(commit.ExecutionCommitError, "expired"):
            self.store.commit(
                attempt_receipt={
                    **self.receipt,
                    "prepared_at_unix_ms": NOW + 1,
                    "expires_at_unix_ms": NOW + 30_000,
                },
                now_unix_ms=NOW,
            )

    def test_concurrent_commit_has_exactly_one_winner(self):
        barrier = threading.Barrier(2)
        outcomes = []

        def run():
            barrier.wait()
            try:
                self.store.commit(attempt_receipt=self.receipt, now_unix_ms=NOW)
                outcomes.append("won")
            except commit.ExecutionCommitError:
                outcomes.append("rejected")

        threads = [threading.Thread(target=run), threading.Thread(target=run)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertCountEqual(outcomes, ["won", "rejected"])
        self.assertEqual(self.store.snapshot()["commit_count"], 1)

    def test_interruption_rolls_back_and_expiry_fails_closed(self):
        with self.assertRaisesRegex(commit.ExecutionCommitError, "rejected"):
            self.store.commit(
                attempt_receipt=self.receipt,
                now_unix_ms=NOW,
                fault_after_insert=True,
            )
        self.assertEqual(self.store.snapshot()["commit_count"], 0)
        self.store.commit(attempt_receipt=self.receipt, now_unix_ms=NOW)
        other = {**self.receipt, "attempt_id": "gate7m-attempt-0002"}
        with self.assertRaisesRegex(commit.ExecutionCommitError, "expired"):
            self.store.commit(attempt_receipt=other, now_unix_ms=NOW + 30_000)


if __name__ == "__main__":
    unittest.main()
