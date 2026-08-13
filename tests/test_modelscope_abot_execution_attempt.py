import importlib.util, sys, unittest
from pathlib import Path
ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("attempt", ROOT / "scripts" / "modelscope_abot_execution_attempt.py")
attempt = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = attempt
spec.loader.exec_module(attempt)
class ExecutionAttemptTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"schema": attempt.PLAN_SCHEMA, "provider_id": attempt.PROVIDER_ID, "plan_only": True}
        self.admission = {"schema": attempt.ADMISSION_SCHEMA, "provider_id": attempt.PROVIDER_ID, "execution_attempted": False, "runtime_admitted": False}
    def test_preflight_is_non_actuating(self):
        result = attempt.prepare_attempt(adapter_plan=self.plan, admission_receipt=self.admission, attempt_id="gate7l-attempt-0001", now_unix_ms=1786600000000, timeout_ms=30000)
        for field in ("network_request_sent", "subprocess_started", "studio_start_called", "execution_attempted", "runtime_admitted", "mcp_registered"): self.assertFalse(result[field])
    def test_open_or_malformed_inputs_fail_closed(self):
        with self.assertRaisesRegex(attempt.ExecutionAttemptError, "boundary"): attempt.prepare_attempt(adapter_plan=self.plan, admission_receipt={**self.admission, "runtime_admitted": True}, attempt_id="gate7l-attempt-0001", now_unix_ms=1, timeout_ms=1)
        with self.assertRaisesRegex(attempt.ExecutionAttemptError, "attempt id"): attempt.prepare_attempt(adapter_plan=self.plan, admission_receipt=self.admission, attempt_id="x", now_unix_ms=1, timeout_ms=1)
        with self.assertRaisesRegex(attempt.ExecutionAttemptError, "timeout"): attempt.prepare_attempt(adapter_plan=self.plan, admission_receipt=self.admission, attempt_id="gate7l-attempt-0001", now_unix_ms=1, timeout_ms=30001)
if __name__ == "__main__": unittest.main()
